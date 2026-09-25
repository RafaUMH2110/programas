"""
docx_a_md_core.py
======================

Núcleo compartido para el pipeline de conversión:

    Word (.docx) con imágenes  -->  Markdown (.md) + diagramas Mermaid + imágenes sueltas

Este módulo NO se ejecuta directamente. Es importado tanto por la versión
"VS Code" (``convertir_docx_a_md_vscode.py``) como por la versión "CLI"
(``convertir_docx_a_md_cli.py``), de modo que la lógica de negocio vive en un único
lugar y ambos scripts solo se ocupan de la interfaz con el usuario.

Estrategia general:
    1. Pandoc convierte el .docx a Markdown, preservando la estructura
       (encabezados, párrafos, listas, tablas) y extrayendo automáticamente
       todas las imágenes incrustadas a una carpeta de medios.
    2. Se analiza cada imagen extraída con métricas de visión por
       computador (OpenCV) para estimar si "parece" un diagrama
       (organigrama, diagrama de flujo, arquitectura...) o una imagen
       fotográfica/compleja no apta para representarse como Mermaid.
    3. Para las imágenes candidatas:
         a) Si hay disponible un modelo de IA con visión (opcional, vía
            API de Anthropic), se le pide que transcriba el diagrama a
            sintaxis Mermaid real.
         b) Si no hay IA disponible, se genera un ESQUELETO Mermaid básico
            (aproximado, a partir de las formas detectadas) que el usuario
            deberá revisar y completar manualmente.
    4. Para las imágenes no candidatas, se conservan como archivos de
       imagen normales, prolijamente organizados en la carpeta de salida,
       con su referencia Markdown correspondiente.

Dependencias externas (no son paquetes de Python):
    - Pandoc: https://pandoc.org/installing.html

Dependencias de Python (ver requirements.txt):
    - opencv-python  (heurística de detección de diagramas)
    - Pillow         (lectura/gestión de imágenes)
    - numpy          (cálculos de las métricas de imagen)
    - python-docx    (extracción de textos alternativos/descripciones)
    - anthropic      (OPCIONAL: conversión real a Mermaid asistida por IA)
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from xml.etree import ElementTree as ET

import numpy as np
from PIL import Image

# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

# Espacios de nombres XML usados en los archivos internos de un .docx
NS = {
    "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "wp": "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing",
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "pkgrel": "http://schemas.openxmlformats.org/package/2006/relationships",
}

PATRON_IMAGEN_MD = re.compile(r"!\[([^\]]*)\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")

# Cuando la imagen del .docx tiene un ancho/alto explícito, Pandoc no puede
# representarla con la sintaxis Markdown estándar (que no admite tamaño) y
# recurre a una etiqueta HTML <img> en su lugar. Detectamos ambos formatos.
PATRON_IMAGEN_HTML = re.compile(r'<img\s+[^>]*?src="([^"]+)"[^>]*?/?>')

# Patrón combinado, usado para recorrer el documento respetando el orden real
# de aparición de cada imagen (ya esté en formato Markdown o en formato HTML).
PATRON_IMAGEN_COMBINADO = re.compile(
    r'(?:!\[(?P<alt_md>[^\]]*)\]\((?P<ruta_md>[^)\s]+)(?:\s+"[^"]*")?\))'
    r'|(?:<img\s+[^>]*?src="(?P<ruta_html>[^"]+)"[^>]*?/?>)'
)

EXTENSIONES_IMAGEN_VALIDAS = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".emf", ".wmf", ".tiff"}


# ---------------------------------------------------------------------------
# Excepciones propias
# ---------------------------------------------------------------------------

class HerramientaNoEncontradaError(RuntimeError):
    """Se lanza cuando falta una dependencia externa (Pandoc)."""


class ConversionPandocError(RuntimeError):
    """Se lanza cuando Pandoc falla al convertir el documento."""


# ---------------------------------------------------------------------------
# Estructuras de datos
# ---------------------------------------------------------------------------

@dataclass
class ImagenDetectada:
    """Representa una imagen encontrada en el Markdown generado por Pandoc."""

    indice: int                       # posición secuencial (1, 2, 3...)
    alt_original: str                  # texto alternativo tal cual lo dejó Pandoc
    ruta_relativa: str                  # ruta tal como aparece en el Markdown
    ruta_absoluta: Path                 # ruta resuelta en disco
    linea_markdown_completa: str        # línea "![...](...)" completa a sustituir
    descripcion_docx: Optional[str] = None   # texto alternativo real extraído del .docx
    es_candidato_mermaid: bool = False
    metricas: dict = field(default_factory=dict)
    codigo_mermaid: Optional[str] = None
    origen_mermaid: Optional[str] = None      # "ia" | "heuristica" | None


# ---------------------------------------------------------------------------
# 1. Verificación de dependencias externas
# ---------------------------------------------------------------------------

def verificar_dependencias() -> None:
    """
    Comprueba que Pandoc esté instalado y accesible en el PATH del sistema.

    Lanza:
        HerramientaNoEncontradaError con instrucciones claras de instalación
        si no se encuentra.
    """
    if shutil.which("pandoc") is None:
        raise HerramientaNoEncontradaError(
            "No se encontró Pandoc, necesario para convertir el documento.\n"
            "Instalación:\n"
            "  Windows : winget install --id JohnMacFarlane.Pandoc\n"
            "  macOS   : brew install pandoc\n"
            "  Linux   : sudo apt install pandoc\n"
            "Más información: https://pandoc.org/installing.html"
        )


# ---------------------------------------------------------------------------
# 2. Conversión inicial con Pandoc (estructura + extracción de medios)
# ---------------------------------------------------------------------------

def convertir_docx_a_markdown_pandoc(
    ruta_docx: Path,
    directorio_salida: Path,
    directorio_medios: Path,
    verbose: bool = False,
) -> str:
    """
    Invoca a Pandoc para convertir el .docx a Markdown (formato GFM),
    preservando encabezados, párrafos, listas y tablas, y extrayendo
    automáticamente todas las imágenes incrustadas a `directorio_medios`.

    Args:
        ruta_docx: documento Word de entrada.
        directorio_salida: carpeta donde Pandoc puede escribir archivos temporales.
        directorio_medios: carpeta donde se extraerán las imágenes (--extract-media).
        verbose: si True, muestra el comando ejecutado y los avisos de Pandoc.

    Returns:
        El contenido Markdown generado por Pandoc, como cadena de texto.

    Lanza:
        ConversionPandocError si Pandoc termina con un código de error.
    """
    directorio_salida.mkdir(parents=True, exist_ok=True)
    directorio_medios.mkdir(parents=True, exist_ok=True)

    comando = [
        "pandoc",
        str(ruta_docx),
        "-t", "gfm",              # GitHub-Flavored Markdown: tablas, listas, etc.
        "--wrap=none",              # evita cortes de línea artificiales
        "--extract-media", str(directorio_medios),
    ]

    if verbose:
        print(f"  → Ejecutando: {' '.join(comando)}")

    resultado = subprocess.run(comando, capture_output=True, text=True, check=False)

    if resultado.returncode != 0:
        raise ConversionPandocError(f"Pandoc finalizó con errores:\n{resultado.stderr.strip()}")

    if verbose and resultado.stderr:
        print(f"  (avisos de Pandoc): {resultado.stderr.strip()}")

    return resultado.stdout


# ---------------------------------------------------------------------------
# 2 bis. Corrección de respaldo de encabezados (cuando Pandoc no los detecta)
# ---------------------------------------------------------------------------
#
# Algunos documentos .docx (por ejemplo, los generados con ciertas librerías
# de terceros que añaden definiciones de estilo personalizadas) pueden
# terminar con estilos "Heading 1/2/3" duplicados o mal enlazados en
# word/styles.xml. Pandoc identifica los encabezados a partir de esos
# estilos, y si su detección falla, los encabezados aparecen en el Markdown
# como simple texto en negrita en lugar de líneas "# ", "## ", etc.
#
# Esta función de respaldo usa python-docx para leer directamente el estilo
# de cada párrafo del .docx original y, si Pandoc no generó NINGÚN
# encabezado Markdown (síntoma claro de este problema), reconstruye los
# encabezados correctos localizando el texto correspondiente en el Markdown
# ya generado.

def extraer_encabezados_docx(ruta_docx: Path) -> List[Tuple[int, str]]:
    """
    Lee el .docx original con python-docx y devuelve, en orden de aparición,
    los pares (nivel, texto) de todos los párrafos con estilo "Heading N"
    (o "Title", tratado como nivel 1).

    Args:
        ruta_docx: documento Word de entrada.

    Returns:
        Lista de tuplas (nivel_encabezado, texto_encabezado).
    """
    from docx import Document

    documento = Document(str(ruta_docx))
    patron_estilo = re.compile(r"^Heading (\d)$", re.IGNORECASE)
    encabezados: List[Tuple[int, str]] = []

    for parrafo in documento.paragraphs:
        nombre_estilo = parrafo.style.name if parrafo.style is not None else ""
        texto = parrafo.text.strip()
        if not texto:
            continue
        coincidencia = patron_estilo.match(nombre_estilo or "")
        if coincidencia:
            encabezados.append((int(coincidencia.group(1)), texto))
        elif nombre_estilo == "Title":
            encabezados.append((1, texto))

    return encabezados


def corregir_encabezados_si_hace_falta(
    contenido_md: str,
    ruta_docx: Path,
    verbose: bool = False,
) -> str:
    """
    Comprueba si el Markdown generado por Pandoc contiene encabezados ATX
    ("# ", "## "...). Si no contiene NINGUNO (síntoma de que Pandoc no pudo
    reconocer los estilos de encabezado del documento original), intenta
    reconstruirlos automáticamente usando `extraer_encabezados_docx`.

    Args:
        contenido_md: Markdown generado por Pandoc.
        ruta_docx: documento Word original (para leer sus estilos reales).
        verbose: si True, informa de si se aplicó la corrección.

    Returns:
        El Markdown, corregido si hizo falta, o sin cambios si Pandoc ya
        detectó los encabezados correctamente o si la corrección no fue
        posible por cualquier motivo (nunca lanza una excepción).
    """
    if re.search(r"^#{1,6}\s", contenido_md, re.MULTILINE):
        return contenido_md  # Pandoc ya detectó los encabezados correctamente; nada que hacer.

    try:
        encabezados = extraer_encabezados_docx(ruta_docx)
    except Exception as exc:  # noqa: BLE001 — esta corrección es un "extra"; nunca debe romper el pipeline
        if verbose:
            print(f"  ⚠ No se pudo aplicar la corrección de encabezados de respaldo: {exc}")
        return contenido_md

    if not encabezados:
        return contenido_md

    if verbose:
        print(
            f"  ⚠ Pandoc no detectó encabezados en el documento; aplicando corrección de "
            f"respaldo con python-docx ({len(encabezados)} encabezado(s) encontrados)."
        )

    resultado = contenido_md
    cursor = 0
    for nivel, texto in encabezados:
        nivel = min(max(nivel, 1), 6)
        # Pandoc suele conservar el texto del encabezado tal cual, aunque a
        # veces lo envuelve en marcas de negrita si el estilo aplicaba "bold".
        candidatos = [texto, f"**{texto}**", f"*{texto}*"]
        posicion, texto_encontrado = -1, None
        for candidato in candidatos:
            p = resultado.find(candidato, cursor)
            if p != -1 and (posicion == -1 or p < posicion):
                posicion, texto_encontrado = p, candidato

        if posicion == -1:
            continue  # No se encontró (texto modificado por Pandoc); se omite sin interrumpir el resto.

        marca_encabezado = ("#" * nivel) + " " + texto
        resultado = resultado[:posicion] + marca_encabezado + resultado[posicion + len(texto_encontrado):]
        cursor = posicion + len(marca_encabezado)

    return resultado


# ---------------------------------------------------------------------------
# 3. Extracción de descripciones/textos alternativos reales del .docx
# ---------------------------------------------------------------------------

def extraer_textos_alternativos(ruta_docx: Path, verbose: bool = False) -> List[str]:
    """
    Recorre el XML interno del .docx (word/document.xml) para extraer, en el
    orden en que aparecen en el documento, los textos alternativos/títulos
    (atributos `descr` o `name` de `<wp:docPr>`) de cada imagen incrustada.

    Esto permite enriquecer el Markdown final con descripciones más útiles
    que las que Pandoc genera por defecto (a menudo vacías o genéricas).

    Args:
        ruta_docx: documento Word de entrada.
        verbose: si True, informa de cuántas descripciones se encontraron.

    Returns:
        Lista de descripciones (una por imagen, en orden de aparición). Si
        una imagen no tiene descripción, se incluye una cadena vacía. Si el
        proceso falla por cualquier motivo, se devuelve una lista vacía
        (el resto del pipeline sigue funcionando sin esta mejora).
    """
    descripciones: List[str] = []
    try:
        with zipfile.ZipFile(ruta_docx) as zf:
            xml_bytes = zf.read("word/document.xml")
        raiz = ET.fromstring(xml_bytes)
        for doc_pr in raiz.iter(f"{{{NS['wp']}}}docPr"):
            descr = doc_pr.attrib.get("descr", "").strip()
            nombre = doc_pr.attrib.get("name", "").strip()
            descripciones.append(descr or nombre or "")
        if verbose:
            print(f"  ✓ Se extrajeron {len(descripciones)} descripciones de imagen del .docx original.")
    except (KeyError, ET.ParseError, zipfile.BadZipFile) as exc:
        if verbose:
            print(f"  ⚠ No se pudieron extraer descripciones alternativas del .docx: {exc}")
        return []
    return descripciones


# ---------------------------------------------------------------------------
# 4. Localización de las imágenes dentro del Markdown generado
# ---------------------------------------------------------------------------

def localizar_imagenes(
    contenido_md: str,
    directorio_base: Path,
    descripciones_docx: Optional[List[str]] = None,
) -> List[ImagenDetectada]:
    """
    Busca todas las referencias de imagen (`![alt](ruta)`) en el Markdown
    generado por Pandoc y construye la lista de objetos ImagenDetectada,
    resolviendo la ruta absoluta de cada archivo en disco.

    Args:
        contenido_md: Markdown generado por Pandoc.
        directorio_base: carpeta desde la que resolver rutas relativas.
        descripciones_docx: descripciones reales extraídas del .docx
            original (ver extraer_textos_alternativos), en el mismo orden
            en que aparecen las imágenes.

    Returns:
        Lista de ImagenDetectada en el orden en que aparecen en el documento.
    """
    imagenes: List[ImagenDetectada] = []
    for i, coincidencia in enumerate(PATRON_IMAGEN_COMBINADO.finditer(contenido_md), start=1):
        if coincidencia.group("ruta_md") is not None:
            alt, ruta_rel = coincidencia.group("alt_md"), coincidencia.group("ruta_md")
        else:
            alt, ruta_rel = "", coincidencia.group("ruta_html")

        ruta_abs = Path(ruta_rel)
        if not ruta_abs.is_absolute():
            ruta_abs = (directorio_base / ruta_rel).resolve()
        descripcion = None
        if descripciones_docx and (i - 1) < len(descripciones_docx):
            descripcion = descripciones_docx[i - 1] or None
        imagenes.append(
            ImagenDetectada(
                indice=i,
                alt_original=alt,
                ruta_relativa=ruta_rel,
                ruta_absoluta=ruta_abs,
                linea_markdown_completa=coincidencia.group(0),
                descripcion_docx=descripcion,
            )
        )
    return imagenes


# ---------------------------------------------------------------------------
# 5. Heurística de detección: ¿parece esto un diagrama?
# ---------------------------------------------------------------------------

def analizar_imagen(ruta_imagen: Path) -> dict:
    """
    Calcula un conjunto de métricas de visión por computador sobre una
    imagen para estimar si se trata de un diagrama esquemático (organigrama,
    diagrama de flujo, arquitectura, etc.) o de una imagen fotográfica /
    compleja poco apta para convertir a Mermaid.

    Métricas calculadas:
        - proporcion_fondo_claro: fracción de píxeles casi blancos/claros
          (los diagramas suelen tener fondo blanco predominante).
        - num_colores_unicos: número de colores únicos tras cuantizar la
          imagen (los diagramas usan paletas planas y reducidas; las fotos
          tienen miles de tonos).
        - densidad_bordes: fracción de píxeles detectados como borde
          (Canny). Los diagramas de líneas tienen bordes definidos, pero
          en baja densidad relativa (no textura continua).
        - num_lineas_rectas: número de segmentos de línea recta detectados
          (Hough). Los diagramas de cajas y flechas tienen muchas líneas
          horizontales/verticales.
        - proporcion_horizontal_vertical: fracción de esas líneas que son
          casi perfectamente horizontales o verticales (típico de cajas
          y organigramas, a diferencia de fotos o dibujos libres).

    Args:
        ruta_imagen: ruta al archivo de imagen a analizar.

    Returns:
        Diccionario con las métricas calculadas. Si la imagen no puede
        leerse (formato no soportado, archivo corrupto), devuelve un
        diccionario con "error" y valores por defecto conservadores.
    """
    try:
        import cv2
    except ImportError:
        return {"error": "OpenCV no disponible"}

    try:
        imagen_pil = Image.open(ruta_imagen).convert("RGB")
    except Exception as exc:  # noqa: BLE001 — cualquier imagen ilegible se descarta con seguridad
        return {"error": str(exc)}

    # Redimensionamos a un tamaño manejable para acelerar el análisis.
    imagen_pil.thumbnail((800, 800))
    imagen_np = np.array(imagen_pil)
    gris = cv2.cvtColor(imagen_np, cv2.COLOR_RGB2GRAY)

    # --- Proporción de fondo claro ---
    proporcion_fondo_claro = float(np.mean(gris > 235))

    # --- Número de colores únicos (tras cuantizar a 32 niveles por canal) ---
    cuantizada = (imagen_np // 32) * 32
    colores_unicos = len(np.unique(cuantizada.reshape(-1, 3), axis=0))

    # --- Densidad de bordes (Canny) ---
    bordes = cv2.Canny(gris, 50, 150)
    densidad_bordes = float(np.mean(bordes > 0))

    # --- Líneas rectas (Hough) y su horizontalidad/verticalidad ---
    lineas = cv2.HoughLinesP(bordes, 1, np.pi / 180, threshold=40, minLineLength=25, maxLineGap=8)
    num_lineas = 0 if lineas is None else len(lineas)
    prop_horiz_vert = 0.0
    if lineas is not None and num_lineas > 0:
        angulos = []
        for linea in lineas:
            x1, y1, x2, y2 = linea[0]
            angulo = abs(np.degrees(np.arctan2(y2 - y1, x2 - x1)))
            angulos.append(angulo)
        angulos = np.array(angulos)
        casi_horiz_o_vert = np.sum((angulos < 8) | (angulos > 82) & (angulos < 98) | (angulos > 172))
        prop_horiz_vert = float(casi_horiz_o_vert / num_lineas)

    return {
        "ancho": imagen_pil.width,
        "alto": imagen_pil.height,
        "proporcion_fondo_claro": round(proporcion_fondo_claro, 3),
        "num_colores_unicos": int(colores_unicos),
        "densidad_bordes": round(densidad_bordes, 4),
        "num_lineas_rectas": int(num_lineas),
        "proporcion_horizontal_vertical": round(prop_horiz_vert, 3),
    }


def es_candidato_a_mermaid(metricas: dict, umbral: float = 0.5) -> Tuple[bool, float]:
    """
    Combina las métricas calculadas por `analizar_imagen` en una única
    puntuación de "aspecto de diagrama" entre 0 y 1, y decide si la imagen
    es candidata a convertirse en Mermaid.

    La puntuación pondera:
        - Fondo mayoritariamente claro (típico de diagramas exportados).
        - Pocos colores únicos (paleta plana, no fotográfica).
        - Alta proporción de líneas horizontales/verticales (cajas, flechas).
        - Densidad de bordes moderada (ni una imagen vacía ni una textura
          fotográfica muy detallada).

    Args:
        metricas: diccionario devuelto por `analizar_imagen`.
        umbral: puntuación mínima (0-1) para considerar la imagen candidata.

    Returns:
        Tupla (es_candidato, puntuacion).
    """
    if "error" in metricas:
        return False, 0.0

    puntuacion = 0.0

    # Fondo claro: contribuye hasta 0.3
    puntuacion += 0.3 * min(metricas["proporcion_fondo_claro"] / 0.6, 1.0)

    # Pocos colores únicos: contribuye hasta 0.3 (menos de ~40 colores = diagrama típico)
    colores = metricas["num_colores_unicos"]
    puntuacion += 0.3 * max(0.0, 1.0 - (colores / 200))

    # Líneas horizontales/verticales: contribuye hasta 0.25
    puntuacion += 0.25 * metricas["proporcion_horizontal_vertical"]

    # Presencia de suficientes líneas rectas para ser un diagrama de cajas: hasta 0.15
    puntuacion += 0.15 * min(metricas["num_lineas_rectas"] / 15, 1.0)

    puntuacion = round(min(puntuacion, 1.0), 3)
    return puntuacion >= umbral, puntuacion


# ---------------------------------------------------------------------------
# 6. Generación de Mermaid: vía IA (opcional) o esqueleto heurístico
# ---------------------------------------------------------------------------

def generar_mermaid_con_ia(ruta_imagen: Path, descripcion: Optional[str], verbose: bool = False) -> Optional[str]:
    """
    Intenta generar sintaxis Mermaid real enviando la imagen a un modelo de
    IA con capacidad de visión (API de Anthropic / Claude), si el paquete
    `anthropic` está instalado y hay una clave de API configurada en la
    variable de entorno ANTHROPIC_API_KEY.

    Esta función es completamente opcional: si falta el paquete, la clave
    de API, o la llamada falla por cualquier motivo, devuelve None sin
    interrumpir el resto del pipeline (se recurrirá al esqueleto heurístico).

    Args:
        ruta_imagen: ruta a la imagen del diagrama.
        descripcion: descripción/alt-text original, si existe, para dar
            contexto adicional al modelo.
        verbose: si True, informa del intento y su resultado.

    Returns:
        Código Mermaid (sin las vallas ```mermaid) generado por la IA, o
        None si no fue posible obtenerlo.
    """
    import base64
    import os

    try:
        import anthropic
    except ImportError:
        if verbose:
            print("    ℹ Paquete 'anthropic' no instalado; se usará el esqueleto heurístico.")
        return None

    clave_api = os.environ.get("ANTHROPIC_API_KEY")
    if not clave_api:
        if verbose:
            print("    ℹ ANTHROPIC_API_KEY no configurada; se usará el esqueleto heurístico.")
        return None

    try:
        media_type = "image/png" if ruta_imagen.suffix.lower() == ".png" else "image/jpeg"
        datos_b64 = base64.b64encode(ruta_imagen.read_bytes()).decode("utf-8")

        cliente = anthropic.Anthropic(api_key=clave_api)
        contexto = f' La imagen se titula o describe como: "{descripcion}".' if descripcion else ""
        prompt = (
            "Observa esta imagen, que contiene un diagrama (organigrama, diagrama de flujo, "
            "arquitectura de sistema, diagrama de secuencia, etc.)." + contexto +
            " Transcribe fielmente su contenido a sintaxis Mermaid válida (usa flowchart, "
            "sequenceDiagram, classDiagram, etc., según corresponda). "
            "Responde ÚNICAMENTE con el código Mermaid, sin vallas de bloque de código, "
            "sin explicaciones adicionales, sin la palabra 'mermaid' al principio."
        )
        respuesta = cliente.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1500,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": datos_b64}},
                    {"type": "text", "text": prompt},
                ],
            }],
        )
        texto = "".join(bloque.text for bloque in respuesta.content if hasattr(bloque, "text")).strip()
        texto = re.sub(r"^```(?:mermaid)?\s*|```$", "", texto, flags=re.MULTILINE).strip()

        if verbose:
            print("    ✓ Diagrama transcrito a Mermaid mediante IA.")
        return texto or None

    except Exception as exc:  # noqa: BLE001 — cualquier fallo de la IA no debe romper el pipeline
        if verbose:
            print(f"    ⚠ Fallo al generar Mermaid con IA ({exc}); se usará el esqueleto heurístico.")
        return None


def generar_esqueleto_mermaid(imagen: ImagenDetectada) -> str:
    """
    Genera un esqueleto Mermaid básico y aproximado cuando no hay IA
    disponible, a partir del número de líneas/formas detectadas en la
    imagen. NO reconstruye el contenido real del diagrama (texto de las
    cajas, dirección exacta de las flechas): es un punto de partida
    editable, claramente marcado como tal, para que la persona usuaria lo
    complete manualmente consultando la imagen original.

    Args:
        imagen: objeto ImagenDetectada con sus métricas ya calculadas.

    Returns:
        Código Mermaid (sin las vallas ```mermaid) con un esqueleto
        genérico y comentarios explicativos.
    """
    metricas = imagen.metricas
    ancho = metricas.get("ancho", 100)
    alto = metricas.get("alto", 100)
    direccion = "LR" if ancho >= alto else "TD"

    # Estimamos un número razonable de "nodos" a partir de las líneas rectas
    # detectadas (una aproximación deliberadamente conservadora).
    num_lineas = metricas.get("num_lineas_rectas", 0)
    num_nodos = max(2, min(6, round(num_lineas / 8) + 2))

    titulo = imagen.descripcion_docx or imagen.alt_original or f"Diagrama {imagen.indice}"

    lineas_mermaid = [
        f"%% Esqueleto generado automáticamente a partir de: {imagen.ruta_relativa}",
        f"%% Título/descripción original: {titulo}",
        "%% ATENCIÓN: esto es una aproximación. Revisa la imagen original y",
        "%% sustituye las etiquetas de los nodos y las conexiones reales.",
        f"flowchart {direccion}",
    ]
    nodos = [chr(ord('A') + i) for i in range(num_nodos)]
    for n in nodos:
        lineas_mermaid.append(f'    {n}["Paso {n} (editar)"]')
    for a, b in zip(nodos, nodos[1:]):
        lineas_mermaid.append(f"    {a} --> {b}")

    return "\n".join(lineas_mermaid)


# ---------------------------------------------------------------------------
# 7. Sustitución de imágenes por bloques Mermaid u organización de archivos
# ---------------------------------------------------------------------------

def procesar_imagen(
    imagen: ImagenDetectada,
    directorio_imagenes_final: Path,
    umbral_mermaid: float,
    usar_ia: bool,
    verbose: bool = False,
) -> None:
    """
    Analiza una imagen y decide su destino:
        - Si es candidata a diagrama: intenta generar Mermaid (IA o
          heurística) y lo guarda en `imagen.codigo_mermaid`.
        - Si no lo es (o el análisis falla): se copia a la carpeta de
          imágenes final con un nombre limpio, actualizando su ruta.

    Modifica el objeto `imagen` in-place.
    """
    if not imagen.ruta_absoluta.exists():
        if verbose:
            print(f"  ⚠ Imagen no encontrada en disco, se omite: {imagen.ruta_absoluta}")
        return

    metricas = analizar_imagen(imagen.ruta_absoluta)
    imagen.metricas = metricas
    es_candidato, puntuacion = es_candidato_a_mermaid(metricas, umbral=umbral_mermaid)
    imagen.es_candidato_mermaid = es_candidato

    if verbose:
        print(f"  [{imagen.indice}] {imagen.ruta_relativa} → puntuación de diagrama: {puntuacion:.2f} "
              f"({'candidato a Mermaid' if es_candidato else 'se conserva como imagen'})")

    if es_candidato:
        codigo = None
        if usar_ia:
            codigo = generar_mermaid_con_ia(imagen.ruta_absoluta, imagen.descripcion_docx, verbose=verbose)
            if codigo:
                imagen.origen_mermaid = "ia"
        if not codigo:
            codigo = generar_esqueleto_mermaid(imagen)
            imagen.origen_mermaid = "heuristica"
        imagen.codigo_mermaid = codigo

        # Conservamos una copia de la imagen original como referencia visual,
        # ya que la carpeta temporal de Pandoc se eliminará al finalizar y el
        # Markdown final menciona esta ruta para que el usuario pueda comparar
        # el diagrama generado con la imagen de la que partió.
        directorio_originales = directorio_imagenes_final / "originales"
        directorio_originales.mkdir(parents=True, exist_ok=True)
        nombre_original = f"diagrama_{imagen.indice:02d}_original{imagen.ruta_absoluta.suffix.lower()}"
        destino_original = directorio_originales / nombre_original
        shutil.copy2(imagen.ruta_absoluta, destino_original)
        imagen.ruta_relativa = f"{directorio_imagenes_final.name}/originales/{nombre_original}"
    else:
        # Se conserva como imagen: se copia a la carpeta final con nombre limpio.
        directorio_imagenes_final.mkdir(parents=True, exist_ok=True)
        nombre_limpio = f"imagen_{imagen.indice:02d}{imagen.ruta_absoluta.suffix.lower()}"
        destino = directorio_imagenes_final / nombre_limpio
        shutil.copy2(imagen.ruta_absoluta, destino)
        imagen.ruta_relativa = f"{directorio_imagenes_final.name}/{nombre_limpio}"


def reconstruir_markdown(contenido_md: str, imagenes: List[ImagenDetectada]) -> str:
    """
    Reconstruye el contenido Markdown final, sustituyendo cada referencia
    de imagen original por:
        - Un bloque de código ```mermaid``` (si se generó Mermaid), seguido
          de una nota indicando el origen (IA o heurística) y un enlace a
          la imagen original para verificación visual.
        - O bien la referencia de imagen actualizada (si se conservó como
          imagen normal, posiblemente reubicada).

    Se procesa en orden inverso de aparición para no invalidar las
    posiciones de las coincidencias restantes.

    Args:
        contenido_md: Markdown original generado por Pandoc.
        imagenes: lista de ImagenDetectada ya procesadas.

    Returns:
        Markdown final, listo para escribirse en disco.
    """
    resultado = contenido_md

    # Se reemplaza, para cada imagen, la PRIMERA aparición no sustituida todavía de su
    # línea Markdown original (cada línea incluye la ruta de archivo, por lo que en la
    # práctica es única incluso si dos imágenes comparten el mismo texto alternativo).
    for imagen in imagenes:
        if imagen.codigo_mermaid:
            titulo = imagen.descripcion_docx or imagen.alt_original or f"Diagrama {imagen.indice}"
            nota_origen = (
                "generado automáticamente por IA a partir de la imagen original"
                if imagen.origen_mermaid == "ia"
                else "esqueleto aproximado — revisa y completa manualmente"
            )
            bloque = (
                f"\n\n**{titulo}**\n\n"
                f"```mermaid\n{imagen.codigo_mermaid}\n```\n\n"
                f"*({nota_origen}; imagen original conservada en "
                f"`{imagen.ruta_relativa}` para referencia)*\n\n"
            )
        else:
            bloque = f"\n\n![{imagen.alt_original or imagen.descripcion_docx or ''}]({imagen.ruta_relativa})\n\n"

        resultado = resultado.replace(imagen.linea_markdown_completa, bloque.strip("\n"), 1)

    return resultado


# ---------------------------------------------------------------------------
# 8. Limpieza de temporales
# ---------------------------------------------------------------------------

def limpiar_temporales(rutas: List[Path], verbose: bool = False) -> None:
    """Elimina archivos/carpetas temporales, ignorando los que ya no existan."""
    for ruta in rutas:
        try:
            if ruta.is_dir():
                shutil.rmtree(ruta, ignore_errors=True)
            elif ruta.exists():
                ruta.unlink()
            if verbose:
                print(f"  🧹 Eliminado temporal: {ruta}")
        except OSError as exc:
            print(f"  ⚠ No se pudo eliminar '{ruta}': {exc}", file=sys.stderr)


# ---------------------------------------------------------------------------
# 9. Orquestador de alto nivel (usado por ambos scripts)
# ---------------------------------------------------------------------------

def procesar_docx_a_markdown(
    ruta_docx: Path,
    ruta_md_salida: Path,
    directorio_imagenes: Path,
    umbral_mermaid: float = 0.5,
    usar_ia: bool = True,
    mantener_temporales: bool = False,
    verbose: bool = False,
) -> Path:
    """
    Ejecuta el pipeline completo:

        1. Verifica que Pandoc esté disponible.
        2. Convierte el .docx a Markdown con Pandoc, extrayendo las
           imágenes incrustadas a una carpeta temporal de medios.
        3. Extrae las descripciones/alt-text reales del .docx original.
        4. Localiza todas las imágenes en el Markdown generado.
        5. Analiza cada imagen (heurística de "aspecto de diagrama").
        6. Para las candidatas: genera Mermaid (vía IA si está disponible,
           o un esqueleto aproximado en caso contrario).
        7. Para el resto: las copia organizadamente a la carpeta de
           imágenes de salida indicada por el usuario.
        8. Reconstruye el Markdown final con las sustituciones anteriores.
        9. Escribe el Markdown final en la ruta indicada.
       10. Limpia los archivos temporales (salvo que se indique lo contrario).

    Args:
        ruta_docx: documento Word de entrada.
        ruta_md_salida: archivo Markdown de salida deseado.
        directorio_imagenes: carpeta donde guardar las imágenes que NO se
            conviertan a Mermaid.
        umbral_mermaid: sensibilidad (0-1) de la heurística de detección
            de diagramas; valores más altos son más exigentes.
        usar_ia: si True, intenta usar IA con visión (Anthropic) cuando
            esté disponible; si no lo está, recurre automáticamente al
            esqueleto heurístico.
        mantener_temporales: si True, conserva la carpeta de medios bruta
            extraída por Pandoc.
        verbose: activa mensajes detallados de depuración.

    Returns:
        Ruta del archivo Markdown final generado.
    """
    if not ruta_docx.exists():
        raise FileNotFoundError(f"El archivo .docx de entrada no existe: {ruta_docx}")

    print("→ Verificando dependencias externas (Pandoc)...")
    verificar_dependencias()
    print("  ✓ Pandoc disponible.\n")

    ruta_md_salida.parent.mkdir(parents=True, exist_ok=True)
    directorio_temporal_medios = ruta_md_salida.parent / f"_medios_temp_{ruta_docx.stem}"

    print(f"→ Convirtiendo '{ruta_docx.name}' a Markdown con Pandoc...")
    contenido_md = convertir_docx_a_markdown_pandoc(
        ruta_docx, ruta_md_salida.parent, directorio_temporal_medios, verbose=verbose
    )
    contenido_md = corregir_encabezados_si_hace_falta(contenido_md, ruta_docx, verbose=verbose)
    print("  ✓ Conversión estructural completada.\n")

    print("→ Extrayendo descripciones alternativas originales del .docx...")
    descripciones = extraer_textos_alternativos(ruta_docx, verbose=verbose)
    print()

    imagenes = localizar_imagenes(contenido_md, ruta_md_salida.parent, descripciones)
    print(f"→ Se encontraron {len(imagenes)} imagen(es) incrustada(s) en el documento.\n")

    if usar_ia:
        import os
        try:
            import anthropic  # noqa: F401
            if not os.environ.get("ANTHROPIC_API_KEY"):
                print("ℹ Variable ANTHROPIC_API_KEY no configurada: se usará el modo heurístico "
                      "(esqueletos aproximados) para los diagramas detectados.\n")
        except ImportError:
            print("ℹ Paquete 'anthropic' no instalado: se usará el modo heurístico "
                  "(esqueletos aproximados) para los diagramas detectados.\n")

    print("→ Analizando cada imagen (heurística de detección de diagramas)...")
    for imagen in imagenes:
        procesar_imagen(imagen, directorio_imagenes, umbral_mermaid, usar_ia, verbose=verbose)
    print()

    num_mermaid = sum(1 for im in imagenes if im.codigo_mermaid)
    num_imagenes = len(imagenes) - num_mermaid
    print(f"  ✓ {num_mermaid} imagen(es) convertida(s) a Mermaid; {num_imagenes} conservada(s) como imagen.\n")

    print("→ Reconstruyendo el documento Markdown final...")
    markdown_final = reconstruir_markdown(contenido_md, imagenes)
    ruta_md_salida.write_text(markdown_final, encoding="utf-8")
    print(f"  ✓ Markdown final escrito en: {ruta_md_salida}\n")

    if not mantener_temporales:
        limpiar_temporales([directorio_temporal_medios], verbose=verbose)
    else:
        print(f"ℹ Carpeta de medios bruta conservada en: {directorio_temporal_medios}")

    return ruta_md_salida
