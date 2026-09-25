# -*- coding: utf-8 -*-
"""
generate_pptx_common_openai.py
================================

Módulo compartido utilizado por ``generate_presentation_vscode_openai.py``
y ``generate_presentation_cli_openai.py``.

Es la variante que utiliza la **API de OpenAI** en lugar de la API de
Anthropic para estructurar el contenido de la presentación. El resto
del pipeline (lectura de .docx, estilos, generadores de diapositivas)
es idéntico a la versión de Anthropic.

Contiene:
    1. El sistema de estilos visuales ("Editorial Noir / Automatización
       Industrial"): colores, tipografías, iconos y utilidades de bajo
       nivel para construir formas y textos con ``python-pptx``.
    2. La lectura y resumen del documento .docx de origen.
    3. La construcción del prompt para el modelo de lenguaje (LLM) y la
       llamada a la API de OpenAI.
    4. Los generadores de diapositivas ("renderers") que traducen la
       estructura JSON devuelta por el LLM en un archivo .pptx real.

Este módulo NO se ejecuta directamente: es importado por los dos
scripts de entrada (versión VS Code y versión CLI).

------------------------------------------------------------------
Dependencias (instalar con pip):

    pip install python-pptx python-docx openai

------------------------------------------------------------------
"""

from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

import docx  # python-docx
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.oxml.ns import qn
from pptx.util import Emu, Inches, Pt

try:
    from pptx.enum.line import MSO_LINE_DASH_STYLE
except ImportError:  # Compatibilidad con versiones antiguas de python-pptx
    MSO_LINE_DASH_STYLE = None

import openai
from openai import OpenAI

# ---------------------------------------------------------------------------
# 1. CONFIGURACIÓN DEL LOGGING
# ---------------------------------------------------------------------------

logger = logging.getLogger("grafcet_pptx")


def configurar_logging(nivel: int = logging.INFO) -> None:
    """Configura un logger de consola legible en español.

    Parameters
    ----------
    nivel:
        Nivel de logging (``logging.DEBUG``, ``logging.INFO``, etc.).
    """
    logging.basicConfig(
        level=nivel,
        format="%(asctime)s | %(levelname)-8s | %(message)s",
        datefmt="%H:%M:%S",
    )


# ---------------------------------------------------------------------------
# 2. SISTEMA DE ESTILOS — "EDITORIAL NOIR / AUTOMATIZACIÓN INDUSTRIAL"
# ---------------------------------------------------------------------------
# Misma paleta y tipografías utilizadas en la presentación de referencia
# sobre la práctica de GRAFCET, para que cualquier documento .docx que se
# procese mantenga la identidad visual del curso.

COLOR = {
    "dark_bg": "0B1E2C",     # Fondo casi negro (portada / cierre)
    "dark_card": "13324A",   # Tarjetas sobre fondo oscuro
    "navy": "0F2D42",        # Color primario
    "steel": "3D5C70",       # Secundario/mudo (líneas, conectores)
    "amber": "F2A541",       # Acento — luz de señalización industrial
    "teal": "4FB0C6",        # Acento secundario — paneles de estado
    "ok_green": "3FA672",    # Verde de aprobación (pieza OK)
    "nok_red": "D9584A",     # Rojo de rechazo (pieza NOK)
    "light_bg": "F6F8F9",    # Fondo de diapositivas de contenido
    "card_light": "FFFFFF",  # Tarjetas sobre fondo claro
    "text_dark": "16242E",   # Texto principal
    "text_muted": "5C7182",  # Texto secundario
    "line_gray": "D7DEE3",   # Líneas divisorias sutiles
    "white": "FFFFFF",
}

FONT_HEAD = "Cambria"   # Tipografía de titulares (con serifa, tono académico)
FONT_BODY = "Calibri"   # Tipografía de cuerpo de texto

# Tamaño de diapositiva panorámico (16:9), igual que "LAYOUT_WIDE"
SLIDE_WIDTH_IN = 13.333
SLIDE_HEIGHT_IN = 7.5

# Mapa de "iconos" simplificado: cada clave se asocia a un glifo Unicode
# que se dibuja centrado dentro de un círculo de color. Esta es una
# alternativa ligera —sin dependencias extra— a la generación de iconos
# vectoriales (p. ej. react-icons) usada en la versión Node.js del pipeline.
# Si se desea el mismo nivel de detalle gráfico, puede sustituirse esta
# función por una que renderice SVGs reales (con `cairosvg` + `Pillow`) y
# los inserte como imágenes PNG en las mismas coordenadas.
ICONOS = {
    "play": "▶", "cut": "✂", "eye": "👁", "random": "⇄", "check": "✓",
    "times": "✕", "warning": "⚠", "shield": "🛡", "clipboard": "📋",
    "sitemap": "🗂", "list": "🔢", "cogs": "⚙", "balance": "⚖",
    "book": "📖", "grad": "🎓", "clock": "🕒", "file": "📄",
    "question": "❓", "route": "🧭", "layer": "📚", "tshirt": "👕",
    "industry": "🏭", "clipboard_check": "✅", "box": "📦",
    "arrow_right": "➡", "bolt": "⚡", "lock": "🔒", "user_cog": "🛠",
    "chart": "📈", "globe": "🌐", "tachometer": "⏱", "table": "▦",
    "envelope": "✉", "calendar": "📅", "search": "🔍", "stop": "⛔",
    "ban": "🚫", "puzzle": "🧩", "flag": "🏁", "exchange": "🔀",
}


def color(nombre_o_hex: str) -> RGBColor:
    """Devuelve un ``RGBColor`` a partir de una clave de ``COLOR`` o un
    código hexadecimal directo (sin ``#``).
    """
    valor_hex = COLOR.get(nombre_o_hex, nombre_o_hex)
    return RGBColor.from_string(valor_hex)


# ---------------------------------------------------------------------------
# 3. UTILIDADES DE BAJO NIVEL PARA CONSTRUIR FORMAS Y TEXTOS
# ---------------------------------------------------------------------------

def nueva_diapositiva(prs: Presentation, fondo: str) -> Any: # type: ignore
    """Crea una diapositiva en blanco con el color de fondo indicado.

    Parameters
    ----------
    prs:
        Presentación activa.
    fondo:
        Clave de ``COLOR`` (p. ej. ``"light_bg"`` o ``"dark_bg"``).
    """
    layout_en_blanco = prs.slide_layouts[6]
    slide = prs.slides.add_slide(layout_en_blanco)
    slide.background.fill.solid()
    slide.background.fill.fore_color.rgb = color(fondo)
    return slide


def agregar_rectangulo(
    slide,
    x: float, y: float, w: float, h: float,
    relleno: Optional[str] = None,
    linea: Optional[str] = None,
    grosor_linea_pt: float = 1.0,
    discontinua: bool = False,
):
    """Dibuja un rectángulo (sin bordes redondeados) y devuelve la forma."""
    forma = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(x), Inches(y), Inches(w), Inches(h))
    if relleno is not None:
        forma.fill.solid()
        forma.fill.fore_color.rgb = color(relleno)
    else:
        forma.fill.background()
    if linea is not None:
        forma.line.color.rgb = color(linea)
        forma.line.width = Pt(grosor_linea_pt)
        if discontinua and MSO_LINE_DASH_STYLE is not None:
            forma.line.dash_style = MSO_LINE_DASH_STYLE.DASH
    else:
        forma.line.fill.background()
    forma.shadow.inherit = False
    return forma


def agregar_ovalo(slide, x: float, y: float, w: float, h: float, relleno: str):
    """Dibuja un óvalo/círculo relleno y devuelve la forma."""
    forma = slide.shapes.add_shape(MSO_SHAPE.OVAL, Inches(x), Inches(y), Inches(w), Inches(h))
    forma.fill.solid()
    forma.fill.fore_color.rgb = color(relleno)
    forma.line.fill.background()
    forma.shadow.inherit = False
    return forma


def agregar_texto(
    slide,
    x: float, y: float, w: float, h: float,
    texto_o_runs,
    fuente: str = FONT_BODY,
    tamano: float = 12,
    color_texto: str = "text_dark",
    negrita: bool = False,
    cursiva: bool = False,
    alineacion: PP_ALIGN = PP_ALIGN.LEFT,
    v_alineacion: MSO_ANCHOR = MSO_ANCHOR.TOP,
    interlineado: Optional[float] = None,
):
    """Agrega un cuadro de texto, admitiendo texto simple o "rich text".

    ``texto_o_runs`` puede ser:
        * Una cadena de texto simple (una sola línea o con ``\\n``).
        * Una lista de párrafos, donde cada párrafo es una lista de
          fragmentos ``{"texto": str, "negrita": bool, "cursiva": bool,
          "color": str}`` (todas las claves salvo ``"texto"`` son
          opcionales).
    """
    caja = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    marco = caja.text_frame
    marco.word_wrap = True
    marco.vertical_anchor = v_alineacion
    marco.margin_left = 0
    marco.margin_right = 0
    marco.margin_top = 0
    marco.margin_bottom = 0

    # Normalizamos la entrada a una lista de párrafos con fragmentos.
    if isinstance(texto_o_runs, str):
        parrafos = [[{"texto": linea}] for linea in texto_o_runs.split("\n")]
    else:
        parrafos = texto_o_runs

    for indice, parrafo in enumerate(parrafos):
        p = marco.paragraphs[0] if indice == 0 else marco.add_paragraph()
        p.alignment = alineacion
        if interlineado:
            p.line_spacing = interlineado
        for fragmento in parrafo:
            run = p.add_run()
            run.text = fragmento.get("texto", "")
            run.font.name = fuente
            run.font.size = Pt(fragmento.get("tamano", tamano)) # type: ignore
            run.font.bold = fragmento.get("negrita", negrita)
            run.font.italic = fragmento.get("cursiva", cursiva)
            run.font.color.rgb = color(fragmento.get("color", color_texto))
    return caja


def agregar_bullets(
    slide,
    x: float, y: float, w: float, h: float,
    items: list[str],
    fuente: str = FONT_BODY,
    tamano: float = 12,
    color_texto: str = "text_dark",
    espacio_tras_parrafo_pt: float = 8,
):
    """Agrega una lista con viñetas (símbolo "•" manual, ya que
    python-pptx no expone un formato de viñetas de alto nivel sencillo).
    """
    caja = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    marco = caja.text_frame
    marco.word_wrap = True
    marco.margin_left = 0
    marco.margin_right = 0
    marco.margin_top = 0
    marco.margin_bottom = 0
    for indice, item in enumerate(items):
        p = marco.paragraphs[0] if indice == 0 else marco.add_paragraph()
        p.space_after = Pt(espacio_tras_parrafo_pt)
        run = p.add_run()
        run.text = f"•  {item}"
        run.font.name = fuente
        run.font.size = Pt(tamano)
        run.font.color.rgb = color(color_texto)
    return caja


def agregar_icono_circular(
    slide,
    icono: str,
    cx: float, cy: float, diametro: float,
    color_circulo: str,
    color_glifo: str = "white",
):
    """Dibuja un círculo de color con un glifo Unicode centrado,
    emulando el motivo visual de "icono en círculo" del diseño original.
    """
    agregar_ovalo(slide, cx - diametro / 2, cy - diametro / 2, diametro, diametro, color_circulo)
    glifo = ICONOS.get(icono, "•")
    tam_fuente = max(10, diametro * 20)
    agregar_texto(
        slide, cx - diametro / 2, cy - diametro / 2, diametro, diametro,
        glifo, fuente=FONT_BODY, tamano=tam_fuente, color_texto=color_glifo,
        alineacion=PP_ALIGN.CENTER, v_alineacion=MSO_ANCHOR.MIDDLE,
    )


def agregar_conector(
    slide, x1: float, y1: float, x2: float, y2: float,
    color_linea: str = "steel", grosor_pt: float = 1.5,
    con_flecha: bool = False,
):
    """Dibuja una línea recta entre dos puntos, con flecha final opcional.

    Nota técnica: ``python-pptx`` no expone una API pública de alto nivel
    para las puntas de flecha, así que se inserta el elemento XML
    ``<a:tailEnd>`` manualmente (técnica documentada y ampliamente usada
    por la comunidad de python-pptx).
    """
    conector = slide.shapes.add_connector(1, Inches(x1), Inches(y1), Inches(x2), Inches(y2))
    conector.line.color.rgb = color(color_linea)
    conector.line.width = Pt(grosor_pt)
    if con_flecha:
        ln = conector.line._get_or_add_ln()  # noqa: SLF001 (acceso interno documentado)
        punta = ln.makeelement(qn("a:tailEnd"), {"type": "triangle"})
        ln.append(punta)
    return conector


def kicker(slide, texto: str, color_texto: str = "amber", x: float = 0.6, y: float = 0.45):
    """Etiqueta corta en mayúsculas que indica la sección de la diapositiva."""
    agregar_texto(
        slide, x, y, 8, 0.35, texto.upper(),
        fuente=FONT_BODY, tamano=12, color_texto=color_texto, negrita=True,
    )


def titulo_diapositiva(
    slide, texto: str, x: float = 0.6, y: float = 0.78, w: float = 11.6,
    color_texto: str = "text_dark", tamano: float = 30,
):
    """Titular principal de la diapositiva (tipografía de cabecera)."""
    agregar_texto(
        slide, x, y, w, 0.9, texto,
        fuente=FONT_HEAD, tamano=tamano, color_texto=color_texto, negrita=True,
    )


def numero_pagina(slide, numero: int):
    """Número de página discreto en la esquina inferior derecha."""
    agregar_texto(
        slide, SLIDE_WIDTH_IN - 0.9, SLIDE_HEIGHT_IN - 0.42, 0.6, 0.3,
        f"{numero:02d}", fuente=FONT_BODY, tamano=9,
        color_texto="text_muted", alineacion=PP_ALIGN.RIGHT,
    )


# ---------------------------------------------------------------------------
# 4. LECTURA Y RESUMEN DEL DOCUMENTO .DOCX DE ORIGEN
# ---------------------------------------------------------------------------

def extraer_contenido_docx(ruta_docx: Path) -> str:
    """Extrae el texto completo (párrafos y tablas) de un archivo .docx.

    El resultado es una única cadena de texto plano, preservando el
    orden de lectura, que se utilizará como contexto para el LLM.
    """
    logger.info("Leyendo el documento de origen: %s", ruta_docx)
    documento = docx.Document(str(ruta_docx))
    bloques: list[str] = []

    for parrafo in documento.paragraphs:
        texto = parrafo.text.strip()
        if texto:
            estilo = parrafo.style.name if parrafo.style else ""
            if estilo.lower().startswith("heading") or estilo.lower().startswith("título"): # type: ignore
                bloques.append(f"\n### {texto}\n")
            else:
                bloques.append(texto)

    for tabla in documento.tables:
        bloques.append("\n[TABLA]")
        for fila in tabla.rows:
            celdas = [celda.text.strip() for celda in fila.cells]
            bloques.append(" | ".join(celdas))
        bloques.append("[FIN TABLA]\n")

    contenido = "\n".join(bloques)
    logger.info("Documento leído correctamente (%d caracteres).", len(contenido))
    return contenido


# ---------------------------------------------------------------------------
# 5. CONSTRUCCIÓN DEL PROMPT Y LLAMADA AL LLM (API DE OPENAI)
# ---------------------------------------------------------------------------

ESQUEMA_JSON_DESCRIPCION = """
Debes devolver EXCLUSIVAMENTE un objeto JSON (sin texto adicional, sin
bloques de código Markdown) con la siguiente forma exacta:

{
  "meta": {
    "kicker": "string breve, ej. 'Práctica de laboratorio'",
    "titulo": "string, título principal de la portada",
    "subtitulo": "string, subtítulo/descripción breve",
    "asignatura": "string",
    "grado_curso": "string",
    "departamento": "string",
    "universidad": "string",
    "docente": "string",
    "duracion": "string, ej. '2 horas'"
  },
  "slides": [
    {
      "type": "section",
      "kicker": "string",
      "title": "string",
      "subtitle": "string opcional"
    },
    {
      "type": "bullets_two_col",
      "kicker": "string", "title": "string", "intro": "string opcional",
      "col1_title": "string", "col1_icon": "clave_de_icono",
      "col1_items": ["string", "..."],
      "col2_title": "string", "col2_icon": "clave_de_icono",
      "col2_items": ["string", "..."]
    },
    {
      "type": "process_flow",
      "kicker": "string", "title": "string", "subtitle": "string opcional",
      "steps": [{"icon": "clave_de_icono", "label": "string corto", "sub": "string opcional"}],
      "safety_note": "string opcional"
    },
    {
      "type": "table",
      "kicker": "string", "title": "string", "intro": "string opcional",
      "headers": ["string", "..."],
      "rows": [["string", "..."], ["..."]]
    },
    {
      "type": "cards",
      "kicker": "string", "title": "string", "intro": "string opcional",
      "columns": 2,
      "cards": [{"icon": "clave_de_icono", "title": "string", "text": "string"}]
    },
    {
      "type": "grafcet_diagram",
      "kicker": "string", "title": "string",
      "steps": [{"n": "0", "label": "string", "initial": true}],
      "transitions": ["string", "..."],
      "divergence": {
        "left_condition": "string", "right_condition": "string",
        "left_label": "string", "right_label": "string"
      },
      "task_note": "string"
    },
    {
      "type": "closing",
      "kicker": "string", "title": "string", "subtitle": "string opcional",
      "recap": ["string", "..."],
      "contact": "string opcional",
      "references": ["string", "..."]
    }
  ]
}

Reglas obligatorias:
- Genera entre 18 y 26 diapositivas en total dentro de "slides".
- Usa exclusivamente los "type" definidos arriba.
- Las claves de icono ("icon") deben pertenecer a este vocabulario
  cerrado: play, cut, eye, random, check, times, warning, shield,
  clipboard, sitemap, list, cogs, balance, book, grad, clock, file,
  question, route, layer, tshirt, industry, clipboard_check, box,
  arrow_right, bolt, lock, user_cog, chart, globe, tachometer, table,
  envelope, calendar, search, stop, ban, puzzle, flag, exchange.
- Todo el contenido debe estar en español neutro.
- El contenido debe derivarse fielmente del documento fuente
  proporcionado; no inventes datos que lo contradigan.
- Sé exhaustivo pero conciso: cada diapositiva debe poder leerse en
  pocos segundos (frases cortas, sin párrafos largos).
- Responde EXCLUSIVAMENTE con el objeto JSON completo, comenzando por
  "{" y terminando por "}", sin texto adicional, explicaciones ni
  bloques de código Markdown (nada de ```json antes o después).
"""


@dataclass
class ConfiguracionLLM:
    """Parámetros de la llamada al modelo de lenguaje (vía la API de OpenAI).

    El nombre del modelo puede cambiar con el tiempo a medida que OpenAI
    publica nuevas versiones; algunos valores válidos en el momento de
    escribir este código son: ``"gpt-4o"`` (equilibrio entre calidad y
    coste, recomendado por defecto), ``"gpt-4.1"`` (ventana de contexto
    muy amplia, ideal para documentos largos), ``"gpt-4o-mini"`` (más
    rápido y económico) y los modelos de razonamiento ``"o3"`` /
    ``"o4-mini"`` (estos últimos no admiten ``temperature`` y usan
    ``max_completion_tokens`` en lugar de ``max_tokens``; el código de
    este módulo detecta y se adapta a ambas particularidades
    automáticamente, ver :func:`generar_estructura_presentacion`).
    """

    modelo: str = "gpt-4o"
    max_tokens: int = 16000
    temperatura: float = 0.4
    intentos_maximos: int = 3
    espera_entre_intentos_seg: float = 3.0


@dataclass
class UsoTokens:
    """Registra el consumo de tokens de la API de OpenAI a lo largo de
    una o varias llamadas (por ejemplo, cuando hay reintentos).

    La API de OpenAI devuelve, en cada respuesta, un objeto ``usage``
    con ``prompt_tokens`` (tokens de entrada) y ``completion_tokens``
    (tokens de salida). Esta clase acumula esos valores para poder
    informar, al final del proceso, del consumo total de tokens de la
    consulta.
    """

    tokens_entrada: int = 0
    tokens_salida: int = 0
    llamadas_realizadas: int = 0

    @property
    def tokens_totales(self) -> int:
        """Suma de tokens de entrada y de salida."""
        return self.tokens_entrada + self.tokens_salida

    def acumular(self, respuesta: Any) -> None:
        """Suma a los totales el uso de tokens de una respuesta de la API.

        Es seguro llamarla aunque la respuesta no incluya el atributo
        ``usage`` (en ese caso, simplemente no suma nada salvo la
        llamada realizada). Admite tanto la nomenclatura de OpenAI
        (``prompt_tokens`` / ``completion_tokens``) como, por
        robustez, la de Anthropic (``input_tokens`` / ``output_tokens``),
        por si en algún momento se reutiliza esta misma clase con otro
        proveedor de LLM.
        """
        uso = getattr(respuesta, "usage", None)
        if uso is not None:
            entrada = getattr(uso, "prompt_tokens", None)
            if entrada is None:
                entrada = getattr(uso, "input_tokens", 0)
            salida = getattr(uso, "completion_tokens", None)
            if salida is None:
                salida = getattr(uso, "output_tokens", 0)
            self.tokens_entrada += entrada or 0
            self.tokens_salida += salida or 0
        self.llamadas_realizadas += 1

    def resumen(self) -> str:
        """Devuelve una cadena legible con el consumo total de tokens."""
        return (
            f"{self.llamadas_realizadas} llamada(s) a la API · "
            f"tokens de entrada: {self.tokens_entrada} · "
            f"tokens de salida: {self.tokens_salida} · "
            f"tokens totales: {self.tokens_totales}"
        )


@dataclass
class ResultadoGeneracion:
    """Resultado devuelto por ``generar_presentacion_desde_docx``.

    Agrupa la ruta del archivo .pptx generado junto con el consumo de
    tokens de la llamada al LLM, para que los scripts de entrada puedan
    informar de ambos datos al usuario.
    """

    ruta_pptx: Path
    uso_tokens: UsoTokens


def construir_prompt_llm(contenido_docx: str) -> tuple[str, str]:
    """Construye el prompt de sistema y el prompt de usuario para el LLM.

    Se devuelven ambas partes por separado (en lugar de una única lista
    combinada) para que la función que realiza la llamada a la API
    decida cómo ensamblarlas en la lista ``messages`` (con el rol
    ``"system"`` seguido del rol ``"user"``, en el caso de la API de
    OpenAI).
    """
    sistema = (
        "Eres un diseñador instruccional experto en automatización industrial "
        "y en la creación de presentaciones académicas profesionales. "
        "Tu tarea es transformar el contenido de una práctica de laboratorio "
        "(proporcionado como texto extraído de un .docx) en la estructura "
        "JSON de una presentación de PowerPoint elegante, clara y "
        "pedagógica, manteniendo el estilo visual 'Editorial Noir / "
        "Automatización Industrial' (fondo oscuro en portada y cierre, "
        "fondo claro en el contenido, acentos en ámbar y turquesa, "
        "iconos en círculos, diagramas de proceso y diagramas GRAFCET). "
        "Respondes siempre en español neutro y únicamente con JSON válido, "
        "sin texto adicional ni bloques de código Markdown."
    )
    usuario = (
        f"{ESQUEMA_JSON_DESCRIPCION}\n\n"
        "### Contenido del documento fuente (.docx) ###\n"
        f"{contenido_docx}\n"
        "### Fin del documento fuente ###\n\n"
        "Genera ahora el JSON completo de la presentación."
    )
    return sistema, usuario


def _extraer_json(texto: str) -> dict:
    """Convierte en diccionario la respuesta de texto del modelo, siendo
    tolerante con envoltorios habituales que a veces añaden los LLM
    (vallas de código Markdown, texto sobrante antes o después del
    objeto JSON, etc.), pese a que se le pida explícitamente que no lo
    haga.
    """
    texto = texto.strip()

    # Elimina vallas de código Markdown del tipo ```json ... ``` o ``` ... ```
    if texto.startswith("```"):
        texto = re.sub(r"^```[a-zA-Z]*\s*", "", texto)
        texto = re.sub(r"```\s*$", "", texto)
        texto = texto.strip()

    try:
        return json.loads(texto)
    except json.JSONDecodeError:
        # Último recurso: nos quedamos solo con lo que hay entre la
        # primera "{" y la última "}" del texto.
        inicio, fin = texto.find("{"), texto.rfind("}")
        if inicio != -1 and fin != -1 and fin > inicio:
            return json.loads(texto[inicio:fin + 1])
        raise


def generar_estructura_presentacion(
    contenido_docx: str, config: ConfiguracionLLM
) -> tuple[dict, UsoTokens]:
    """Llama a la API de OpenAI y devuelve una tupla ``(datos, uso_tokens)``:

    * ``datos``: el diccionario JSON ya parseado con la estructura de
      la presentación.
    * ``uso_tokens``: un objeto :class:`UsoTokens` con el consumo total
      de tokens de entrada y salida a lo largo de todas las llamadas
      realizadas (incluyendo, si las hubo, las llamadas fallidas por
      incompatibilidades de parámetros o por reintentos).

    Incluye una lógica de reintentos ante fallos de red, respuestas JSON
    malformadas y, además, ante incompatibilidades conocidas y
    dependientes del modelo concreto que se use (algunos modelos de
    razonamiento como ``o3`` u ``o4-mini``):

    * No admiten el parámetro ``temperature`` (queda fijado internamente).
    * Requieren ``max_completion_tokens`` en lugar de ``max_tokens``.
    * Podrían no admitir ``response_format={"type": "json_object"}``.

    Estas incompatibilidades se detectan automáticamente a partir del
    error 400 devuelto por la API y el proceso se adapta sobre la
    marcha, sin gastar un intento de los disponibles para fallos
    genuinos ni requerir configuración manual por parte del usuario.
    """
    cliente = OpenAI()  # Lee OPENAI_API_KEY automáticamente desde el entorno
    sistema, usuario = construir_prompt_llm(contenido_docx)
    uso_tokens = UsoTokens()

    incluir_temperatura = True
    usar_max_completion_tokens = False  # algunos modelos exigen este parámetro en vez de max_tokens
    incluir_response_format = True
    ultimo_error: Optional[Exception] = None
    intento = 1
    while intento <= config.intentos_maximos:
        try:
            logger.info(
                "Solicitando al modelo '%s' la estructura de la presentación "
                "(intento %d/%d)...",
                config.modelo, intento, config.intentos_maximos,
            )
            parametros_llamada = {
                "model": config.modelo,
                "messages": [
                    {"role": "system", "content": sistema},
                    {"role": "user", "content": usuario},
                ],
            }
            if usar_max_completion_tokens:
                parametros_llamada["max_completion_tokens"] = config.max_tokens
            else:
                parametros_llamada["max_tokens"] = config.max_tokens
            if incluir_temperatura:
                parametros_llamada["temperature"] = config.temperatura
            if incluir_response_format:
                parametros_llamada["response_format"] = {"type": "json_object"}

            respuesta = cliente.chat.completions.create(**parametros_llamada)
            uso_tokens.acumular(respuesta)
            uso = respuesta.usage
            logger.info(
                "Tokens de esta llamada — entrada: %d, salida: %d",
                getattr(uso, "prompt_tokens", 0) or 0,
                getattr(uso, "completion_tokens", 0) or 0,
            )

            texto_bruto = respuesta.choices[0].message.content or ""
            datos = _extraer_json(texto_bruto)

            logger.info(
                "Estructura recibida correctamente: %d diapositivas.",
                len(datos.get("slides", [])),
            )
            logger.info("Consumo total de tokens de esta consulta — %s", uso_tokens.resumen())
            return datos, uso_tokens
        except openai.BadRequestError as error:
            mensaje_error = str(error).lower()
            if incluir_temperatura and "temperature" in mensaje_error:
                logger.warning(
                    "El modelo '%s' no admite el parámetro 'temperature'; "
                    "se reintenta sin él.",
                    config.modelo,
                )
                incluir_temperatura = False
                continue  # No se cuenta como fallo: no se incrementa "intento"
            if (
                not usar_max_completion_tokens
                and "max_tokens" in mensaje_error
                and "max_completion_tokens" in mensaje_error
            ):
                logger.warning(
                    "El modelo '%s' requiere 'max_completion_tokens' en "
                    "lugar de 'max_tokens'; se reintenta con el parámetro "
                    "correcto.",
                    config.modelo,
                )
                usar_max_completion_tokens = True
                continue  # No se cuenta como fallo: no se incrementa "intento"
            if incluir_response_format and "response_format" in mensaje_error:
                logger.warning(
                    "El modelo '%s' no admite 'response_format=json_object'; "
                    "se reintenta solicitando el JSON de forma explícita en "
                    "el mensaje del usuario.",
                    config.modelo,
                )
                incluir_response_format = False
                continue  # No se cuenta como fallo: no se incrementa "intento"
            ultimo_error = error
            logger.warning("Fallo en el intento %d: %s", intento, error)
        except (json.JSONDecodeError, Exception) as error:  # noqa: BLE001
            ultimo_error = error
            logger.warning("Fallo en el intento %d: %s", intento, error)

        if intento < config.intentos_maximos:
            time.sleep(config.espera_entre_intentos_seg)
        intento += 1

    raise RuntimeError(
        f"No se pudo obtener una estructura JSON válida tras "
        f"{config.intentos_maximos} intentos. Último error: {ultimo_error}\n"
        f"Consumo de tokens hasta el fallo — {uso_tokens.resumen()}"
    )


# ---------------------------------------------------------------------------
# 6. GENERADORES DE DIAPOSITIVAS ("RENDERERS")
# ---------------------------------------------------------------------------

def render_portada(prs: Presentation, meta: dict, numero: int) -> None: # type: ignore
    """Diapositiva 1: portada oscura con motivo de cadena GRAFCET."""
    slide = nueva_diapositiva(prs, "dark_bg")

    kicker(slide, meta.get("kicker", "Práctica de laboratorio"), x=0.7, y=0.75)
    agregar_texto(
        slide, 0.7, 1.15, 9.4, 2.4, meta.get("titulo", ""),
        fuente=FONT_HEAD, tamano=32, color_texto="white", negrita=True,
        interlineado=1.05,
    )
    agregar_texto(
        slide, 0.7, 3.6, 8.8, 0.5, meta.get("subtitulo", ""),
        fuente=FONT_BODY, tamano=15, color_texto="teal", cursiva=True,
    )
    agregar_conector(slide, 0.7, 4.35, 9.3, 4.35, color_linea="steel", grosor_pt=0.75)

    lineas_info = [
        [{"texto": meta.get("asignatura", ""), "negrita": True}],
        [{"texto": meta.get("grado_curso", "")}],
        [{"texto": meta.get("departamento", "")}],
        [{"texto": meta.get("universidad", "")}],
    ]
    agregar_texto(slide, 0.7, 4.55, 8.5, 1.3, lineas_info, tamano=13.5, color_texto="line_gray")

    agregar_texto(
        slide, 0.7, 6.05, 8.5, 0.35,
        [[{"texto": "Docente: ", "color": "steel"},
          {"texto": meta.get("docente", ""), "negrita": True, "color": "white"}]],
        tamano=12.5,
    )
    agregar_texto(
        slide, 0.7, 6.55, 7, 0.4,
        f"Duración estimada: {meta.get('duracion', '')}",
        tamano=11.5, color_texto="steel",
    )
    numero_pagina(slide, numero)


def render_section(prs: Presentation, s: dict, numero: int) -> None: # type: ignore
    """Diapositiva divisoria de sección (fondo oscuro)."""
    slide = nueva_diapositiva(prs, "dark_bg")
    kicker(slide, s.get("kicker", ""), x=0.6, y=0.6)
    agregar_texto(
        slide, 0.6, 0.95, 11.6, 0.9, s.get("title", ""),
        fuente=FONT_HEAD, tamano=27, color_texto="white", negrita=True,
    )
    if s.get("subtitle"):
        agregar_texto(
            slide, 0.6, 1.7, 10.5, 0.6, s["subtitle"],
            fuente=FONT_BODY, tamano=13, color_texto="teal", cursiva=True,
        )
    numero_pagina(slide, numero)


def render_bullets_two_col(prs: Presentation, s: dict, numero: int) -> None: # type: ignore
    """Diapositiva de dos columnas con listas de viñetas (p. ej. objetivos)."""
    slide = nueva_diapositiva(prs, "light_bg")
    kicker(slide, s.get("kicker", ""))
    titulo_diapositiva(slide, s.get("title", ""))
    if s.get("intro"):
        agregar_texto(slide, 0.6, 1.55, 11.6, 0.5, s["intro"], tamano=13, color_texto="text_muted")

    ancho_col, y_tarjeta, alto_tarjeta = 5.6, 2.3, 4.5
    for indice, prefijo in enumerate(("col1", "col2")):
        x = 0.6 + indice * (ancho_col + 0.4)
        agregar_rectangulo(slide, x, y_tarjeta, ancho_col, alto_tarjeta, relleno="card_light")
        agregar_icono_circular(
            slide, s.get(f"{prefijo}_icon", "cogs"), x + 0.55, y_tarjeta + 0.5, 0.6,
            "navy" if indice == 0 else "amber",
        )
        agregar_texto(
            slide, x + 1.0, y_tarjeta + 0.22, ancho_col - 1.2, 0.55,
            s.get(f"{prefijo}_title", ""), fuente=FONT_HEAD, tamano=17,
            negrita=True, v_alineacion=MSO_ANCHOR.MIDDLE,
        )
        agregar_bullets(
            slide, x + 0.35, y_tarjeta + 1.0, ancho_col - 0.7, alto_tarjeta - 1.25,
            s.get(f"{prefijo}_items", []), tamano=12,
        )
    numero_pagina(slide, numero)


def render_process_flow(prs: Presentation, s: dict, numero: int) -> None: # type: ignore
    """Diapositiva de flujo de proceso: iconos en círculo conectados por flechas."""
    slide = nueva_diapositiva(prs, "light_bg")
    kicker(slide, s.get("kicker", ""))
    titulo_diapositiva(slide, s.get("title", ""))
    if s.get("subtitle"):
        agregar_texto(slide, 0.6, 1.55, 11.5, 0.4, s["subtitle"], tamano=12.5, color_texto="text_muted")

    pasos = s.get("steps", [])
    n = max(len(pasos), 1)
    x_inicio, separacion, y_caja, alto_caja = 0.6, 0.28, 2.35, 2.35
    ancho_caja = (11.6 - separacion * (n - 1)) / n

    for indice, paso in enumerate(pasos):
        x = x_inicio + indice * (ancho_caja + separacion)
        agregar_rectangulo(slide, x, y_caja, ancho_caja, alto_caja, relleno="card_light", linea="line_gray")
        agregar_icono_circular(slide, paso.get("icon", "cogs"), x + ancho_caja / 2, y_caja + 0.62, 0.58, "navy")
        agregar_texto(
            slide, x + 0.08, y_caja + 1.05, ancho_caja - 0.16, 0.75,
            paso.get("label", ""), tamano=11.5, negrita=True,
            alineacion=PP_ALIGN.CENTER,
        )
        if paso.get("sub"):
            agregar_texto(
                slide, x + 0.08, y_caja + 1.85, ancho_caja - 0.16, 0.35,
                paso["sub"], tamano=10.5, negrita=True, color_texto="navy",
                alineacion=PP_ALIGN.CENTER,
            )
        if indice < n - 1:
            agregar_conector(
                slide, x + ancho_caja, y_caja + alto_caja / 2,
                x + ancho_caja + separacion, y_caja + alto_caja / 2,
                con_flecha=True,
            )

    if s.get("safety_note"):
        y_nota = y_caja + alto_caja + 0.3
        agregar_rectangulo(slide, 0.6, y_nota, 11.6, 0.8, relleno="dark_bg")
        agregar_icono_circular(slide, "warning", 1.15, y_nota + 0.4, 0.5, "amber", color_glifo="navy")
        agregar_texto(
            slide, 1.55, y_nota, 10.4, 0.8, s["safety_note"],
            tamano=11.5, color_texto="white", v_alineacion=MSO_ANCHOR.MIDDLE,
        )
    numero_pagina(slide, numero)


def render_table(prs: Presentation, s: dict, numero: int) -> None: # type: ignore
    """Diapositiva de tabla de datos (encabezado en color navy)."""
    slide = nueva_diapositiva(prs, "light_bg")
    kicker(slide, s.get("kicker", ""))
    titulo_diapositiva(slide, s.get("title", ""))
    if s.get("intro"):
        agregar_texto(slide, 0.6, 1.55, 11.6, 0.5, s["intro"], tamano=12.5, color_texto="text_muted")

    encabezados = s.get("headers", [])
    filas_datos = s.get("rows", [])
    n_filas = len(filas_datos) + 1
    n_cols = max(len(encabezados), 1)

    tabla_shape = slide.shapes.add_table(
        n_filas, n_cols, Inches(0.6), Inches(2.2), Inches(11.6), Inches(min(4.8, 0.55 * n_filas)),
    )
    tabla = tabla_shape.table

    for c, texto in enumerate(encabezados):
        celda = tabla.cell(0, c)
        celda.text = texto
        celda.fill.solid()
        celda.fill.fore_color.rgb = color("navy")
        for p in celda.text_frame.paragraphs:
            for r in p.runs:
                r.font.bold = True
                r.font.color.rgb = color("white")
                r.font.name = FONT_BODY
                r.font.size = Pt(12)

    for f, fila in enumerate(filas_datos, start=1):
        color_fondo = "card_light" if f % 2 == 1 else "F2F5F6"
        for c, texto in enumerate(fila):
            celda = tabla.cell(f, c)
            celda.text = str(texto)
            celda.fill.solid()
            try:
                celda.fill.fore_color.rgb = color(color_fondo)
            except Exception:  # noqa: BLE001 — color hexadecimal directo
                celda.fill.fore_color.rgb = RGBColor.from_string(color_fondo)
            for p in celda.text_frame.paragraphs:
                for r in p.runs:
                    r.font.name = FONT_BODY
                    r.font.size = Pt(11.5)
                    r.font.bold = c == 0
                    r.font.color.rgb = color("text_dark")
    numero_pagina(slide, numero)


def render_cards(prs: Presentation, s: dict, numero: int) -> None: # type: ignore
    """Diapositiva de tarjetas en cuadrícula (2 o 3 columnas)."""
    slide = nueva_diapositiva(prs, "light_bg")
    kicker(slide, s.get("kicker", ""))
    titulo_diapositiva(slide, s.get("title", ""))
    if s.get("intro"):
        agregar_texto(slide, 0.6, 1.55, 11.6, 0.4, s["intro"], tamano=12.5, color_texto="text_muted")

    columnas = s.get("columns", 3)
    tarjetas = s.get("cards", [])
    separacion = 0.2
    ancho_tarjeta = (11.6 - separacion * (columnas - 1)) / columnas
    alto_tarjeta = 2.15
    y_inicio = 2.15 if s.get("intro") else 1.85

    for indice, tarjeta in enumerate(tarjetas):
        col = indice % columnas
        fila = indice // columnas
        x = 0.6 + col * (ancho_tarjeta + separacion)
        y = y_inicio + fila * (alto_tarjeta + separacion)
        agregar_rectangulo(slide, x, y, ancho_tarjeta, alto_tarjeta, relleno="card_light", linea="line_gray")
        agregar_icono_circular(slide, tarjeta.get("icon", "cogs"), x + 0.5, y + 0.48, 0.5, "navy")
        agregar_texto(
            slide, x + 0.15, y + 0.85, ancho_tarjeta - 0.3, 0.35,
            tarjeta.get("title", ""), tamano=12, negrita=True, alineacion=PP_ALIGN.CENTER,
        )
        agregar_texto(
            slide, x + 0.2, y + 1.2, ancho_tarjeta - 0.4, alto_tarjeta - 1.3,
            tarjeta.get("text", ""), tamano=10.5, color_texto="text_muted",
            alineacion=PP_ALIGN.CENTER,
        )
    numero_pagina(slide, numero)


def render_grafcet_diagram(prs: Presentation, s: dict, numero: int) -> None: # type: ignore
    """Diapositiva del diagrama GRAFCET: cadena vertical de etapas y,
    opcionalmente, una divergencia en O al final.
    """
    slide = nueva_diapositiva(prs, "light_bg")
    kicker(slide, s.get("kicker", ""))
    titulo_diapositiva(slide, s.get("title", ""))

    tam_etapa = 0.55
    x_etapa = 1.3
    cx = x_etapa + tam_etapa / 2
    x_accion, ancho_accion = x_etapa + tam_etapa + 0.08, 3.55
    alto_fila = 0.80
    y = 1.6

    pasos = s.get("steps", [])
    transiciones = s.get("transitions", [])
    ultimo_fondo = y

    for indice, paso in enumerate(pasos):
        es_inicial = bool(paso.get("initial", False))
        if es_inicial:
            agregar_rectangulo(
                slide, x_etapa - 0.06, y - 0.06, tam_etapa + 0.12, tam_etapa + 0.12,
                linea="amber", grosor_linea_pt=1.5,
            )
        agregar_rectangulo(
            slide, x_etapa, y, tam_etapa, tam_etapa,
            relleno="navy" if es_inicial else "card_light", linea="navy", grosor_linea_pt=1.5,
        )
        agregar_texto(
            slide, x_etapa, y, tam_etapa, tam_etapa, str(paso.get("n", indice)),
            fuente=FONT_BODY, tamano=16, negrita=True,
            color_texto="amber" if es_inicial else "navy",
            alineacion=PP_ALIGN.CENTER, v_alineacion=MSO_ANCHOR.MIDDLE,
        )
        agregar_rectangulo(slide, x_accion, y, ancho_accion, tam_etapa, relleno="EDF2F4", linea="line_gray")
        agregar_texto(
            slide, x_accion + 0.12, y, ancho_accion - 0.24, tam_etapa,
            paso.get("label", ""), tamano=11, v_alineacion=MSO_ANCHOR.MIDDLE,
        )

        ultimo_fondo = y + tam_etapa
        if indice < len(pasos) - 1:
            y_transicion = y + tam_etapa
            agregar_conector(
                slide, cx, y_transicion, cx, y_transicion + (alto_fila - tam_etapa),
                con_flecha=True,
            )
            if indice < len(transiciones):
                agregar_texto(
                    slide, cx + 0.22, y_transicion + (alto_fila - tam_etapa) / 2 - 0.16, 1.4, 0.3,
                    transiciones[indice], tamano=11, negrita=True, color_texto="teal",
                )
        y += alto_fila

    divergencia = s.get("divergence")
    if divergencia:
        cx_izq, cx_der = cx, cx + 2.35
        y_barra = ultimo_fondo + 0.28
        agregar_conector(slide, cx, ultimo_fondo, cx, y_barra)
        agregar_conector(slide, cx_izq, y_barra, cx_der, y_barra, grosor_pt=2.25, color_linea="text_dark")
        agregar_conector(slide, cx_izq, y_barra, cx_izq, y_barra + 0.4, color_linea="ok_green", con_flecha=True)
        agregar_conector(slide, cx_der, y_barra, cx_der, y_barra + 0.4, color_linea="nok_red", con_flecha=True)
        agregar_texto(
            slide, cx_izq - 0.55, y_barra + 0.03, 1.3, 0.26,
            divergencia.get("left_condition", ""), tamano=10, negrita=True, color_texto="ok_green",
        )
        agregar_texto(
            slide, cx_der + 0.1, y_barra + 0.03, 1.3, 0.26,
            divergencia.get("right_condition", ""), tamano=10, negrita=True, color_texto="nok_red",
        )
        y_rama = y_barra + 0.42
        for cx_rama, etiqueta in ((cx_izq, divergencia.get("left_label", "")), (cx_der, divergencia.get("right_label", ""))):
            agregar_rectangulo(
                slide, cx_rama - tam_etapa / 2, y_rama, tam_etapa, tam_etapa,
                relleno="light_bg", linea="text_muted", grosor_linea_pt=1.25, discontinua=True,
            )
            agregar_texto(
                slide, cx_rama - tam_etapa / 2, y_rama, tam_etapa, tam_etapa, "?",
                tamano=16, negrita=True, color_texto="text_muted",
                alineacion=PP_ALIGN.CENTER, v_alineacion=MSO_ANCHOR.MIDDLE,
            )
            agregar_texto(
                slide, cx_rama - 0.85, y_rama + tam_etapa + 0.04, 1.7, 0.45,
                etiqueta, tamano=9, cursiva=True, color_texto="text_muted",
                alineacion=PP_ALIGN.CENTER,
            )

    if s.get("task_note"):
        agregar_rectangulo(slide, 9.0, 1.6, 3.75, 5.3, relleno="navy")
        agregar_texto(slide, 9.25, 1.85, 3.25, 0.4, "Tu tarea", fuente=FONT_BODY, tamano=13, negrita=True, color_texto="amber")
        agregar_texto(
            slide, 9.25, 2.3, 3.25, 4.4, s["task_note"],
            tamano=11, color_texto="line_gray", interlineado=1.15,
        )
    numero_pagina(slide, numero)


def render_closing(prs: Presentation, s: dict, numero: int) -> None: # type: ignore
    """Diapositiva final de cierre y preguntas (fondo oscuro)."""
    slide = nueva_diapositiva(prs, "dark_bg")
    kicker(slide, s.get("kicker", "Cierre"), x=0.6, y=0.65)
    agregar_texto(
        slide, 0.6, 1.0, 11.6, 0.75, s.get("title", ""),
        fuente=FONT_HEAD, tamano=28, color_texto="white", negrita=True,
    )
    if s.get("subtitle"):
        agregar_texto(slide, 0.6, 1.75, 9.5, 0.55, s["subtitle"], tamano=13.5, color_texto="teal", cursiva=True)

    y = 2.6
    for punto in s.get("recap", []):
        agregar_icono_circular(slide, "check", 1.0, y + 0.28, 0.55, "dark_card", color_glifo="amber")
        agregar_texto(slide, 1.5, y, 7.3, 0.56, punto, tamano=12.5, color_texto="line_gray", v_alineacion=MSO_ANCHOR.MIDDLE)
        y += 0.78

    if s.get("references") or s.get("contact"):
        agregar_rectangulo(slide, 9.3, 2.6, 3.4, 4.35, relleno="dark_card", linea="steel")
        agregar_texto(slide, 9.5, 2.85, 3.0, 0.4, "¿Preguntas?", fuente=FONT_HEAD, tamano=16, negrita=True, color_texto="white")
        if s.get("references"):
            agregar_bullets(slide, 9.5, 3.4, 3.0, 2.0, s["references"], tamano=9.5, color_texto="line_gray")
        if s.get("contact"):
            agregar_texto(slide, 9.5, 6.3, 3.0, 0.4, s["contact"], tamano=11, negrita=True, color_texto="white")
    numero_pagina(slide, numero)


# Tabla de despacho: asocia cada "type" de diapositiva con su renderer.
RENDERERS = {
    "section": render_section,
    "bullets_two_col": render_bullets_two_col,
    "process_flow": render_process_flow,
    "table": render_table,
    "cards": render_cards,
    "grafcet_diagram": render_grafcet_diagram,
    "closing": render_closing,
}


# ---------------------------------------------------------------------------
# 7. ORQUESTACIÓN: CONSTRUCCIÓN COMPLETA DEL .PPTX
# ---------------------------------------------------------------------------

def construir_presentacion(datos: dict, ruta_salida: Path) -> None:
    """Construye el archivo .pptx completo a partir del JSON del LLM."""
    prs = Presentation()
    prs.slide_width = Inches(SLIDE_WIDTH_IN)
    prs.slide_height = Inches(SLIDE_HEIGHT_IN)

    contador_diapositivas = 1
    render_portada(prs, datos.get("meta", {}), contador_diapositivas)
    contador_diapositivas += 1

    for diapositiva in datos.get("slides", []):
        tipo = diapositiva.get("type")
        renderer = RENDERERS.get(tipo)
        if renderer is None:
            logger.warning("Tipo de diapositiva desconocido, se omite: %s", tipo)
            continue
        renderer(prs, diapositiva, contador_diapositivas)
        contador_diapositivas += 1

    ruta_salida.parent.mkdir(parents=True, exist_ok=True)
    prs.save(str(ruta_salida))
    logger.info(
        "Presentación guardada correctamente: %s (%d diapositivas).",
        ruta_salida, contador_diapositivas - 1,
    )


# ---------------------------------------------------------------------------
# 8. FUNCIÓN DE ALTO NIVEL — PUNTO DE ENTRADA COMÚN
# ---------------------------------------------------------------------------

def generar_presentacion_desde_docx(
    ruta_docx: Path,
    ruta_pptx: Path,
    config_llm: Optional[ConfiguracionLLM] = None,
    guardar_json_intermedio: bool = False,
) -> ResultadoGeneracion:
    """Función de alto nivel que encadena todo el proceso:

    1. Lee y extrae el contenido del .docx.
    2. Construye el prompt y llama al LLM para obtener el JSON de la
       presentación (y registra el consumo de tokens de la consulta).
    3. Construye el archivo .pptx final con el mismo estilo visual del
       curso.

    Parameters
    ----------
    ruta_docx:
        Ruta al documento .docx de origen.
    ruta_pptx:
        Ruta donde se guardará el archivo .pptx generado.
    config_llm:
        Configuración de la llamada al modelo (modelo, tokens, etc.).
    guardar_json_intermedio:
        Si es ``True``, guarda el JSON devuelto por el LLM junto al
        .pptx (útil para depuración).

    Returns
    -------
    ResultadoGeneracion
        Objeto con la ruta final del archivo .pptx (``ruta_pptx``) y el
        consumo de tokens de la consulta al LLM (``uso_tokens``).
    """
    config_llm = config_llm or ConfiguracionLLM()

    if not ruta_docx.exists():
        raise FileNotFoundError(f"No se encontró el archivo de entrada: {ruta_docx}")

    contenido = extraer_contenido_docx(ruta_docx)
    datos, uso_tokens = generar_estructura_presentacion(contenido, config_llm)

    if guardar_json_intermedio:
        ruta_json = ruta_pptx.with_suffix(".json")
        ruta_json.write_text(json.dumps(datos, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.info("JSON intermedio guardado en: %s", ruta_json)

    construir_presentacion(datos, ruta_pptx)
    return ResultadoGeneracion(ruta_pptx=ruta_pptx, uso_tokens=uso_tokens)
