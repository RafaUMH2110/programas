#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
 GENERADOR DE PRESENTACIONES .pptx A PARTIR DE DOCUMENTOS .docx
 Estilo: "Editorial Noir" (negro/dorado, tipografía Cambria + Calibri + Courier
 New) — réplica fiel del diseño premium usado en las unidades del Grado en
 Tecnología en Moda.
================================================================================

DESCRIPCIÓN
-----------
Este script lee un documento .docx, extrae su contenido estructurado
(títulos, párrafos, listas y tablas), lo transforma en un guion de
diapositivas mediante la API de Claude (Anthropic) —con una alternativa
100% local si no hay API disponible— y genera un archivo .pptx con el
mismo lenguaje visual usado en las presentaciones anteriores del curso:
kicker en mayúsculas, títulos en Cambria, cuerpo en Calibri, bloques de
código en Courier New sobre fondo negro, tablas con cabecera oscura y
filas alternas, tarjetas de agenda, pie de página con numeración, etc.

INSTALACIÓN (Visual Studio Code)
---------------------------------
1. Abre esta carpeta en VS Code (File > Open Folder...).
2. Crea y activa un entorno virtual (recomendado):
       python -m venv .venv
       .venv\\Scripts\\activate        (Windows)
       source .venv/bin/activate       (macOS / Linux)
3. Instala las dependencias:
       pip install -r requirements.txt
4. (Opcional pero recomendado) Configura tu clave de la API de Anthropic
   como variable de entorno — nunca la escribas directamente en el código:
       Windows (PowerShell):  setx ANTHROPIC_API_KEY "tu-clave-aqui"
       macOS / Linux:         export ANTHROPIC_API_KEY="tu-clave-aqui"
   Si no defines esta variable, o si "use_api" es "false" en config.json,
   el script generará el guion de diapositivas de forma local (heurística),
   sin necesidad de conexión a internet.
5. Edita la variable DOCX_INPUT_PATH (más abajo, en la sección de
   configuración del usuario) con la ruta a tu archivo .docx.
6. Ejecuta el script:
       - Pulsando el botón "Run Python File" (▶) en la esquina superior
         derecha de VS Code, o
       - Desde la terminal integrada:  python generar_presentacion.py

SALIDA
------
El archivo .pptx resultante se guarda en la carpeta configurada en
"output.output_dir" dentro de config.json (por defecto "./output"),
con el nombre configurado en "output.filename".

================================================================================
"""

from __future__ import annotations

import os
import sys
import json
import time
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

# ------------------------------------------------------------------------
# Dependencias externas — si falta alguna, mostramos un mensaje claro en
# español en lugar de dejar que Python lance un ModuleNotFoundError crudo.
# ------------------------------------------------------------------------
_MISSING_DEPS: list[str] = []
try:
    import docx  # python-docx
except ImportError:
    _MISSING_DEPS.append("python-docx")

try:
    from pptx import Presentation
    from pptx.util import Inches, Pt, Emu
    from pptx.dml.color import RGBColor
    from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
    from pptx.enum.shapes import MSO_SHAPE
    from pptx.oxml.ns import qn
except ImportError:
    _MISSING_DEPS.append("python-pptx")

try:
    import jsonschema
    from jsonschema import validate as js_validate
    from jsonschema.exceptions import ValidationError as JsonSchemaValidationError
except ImportError:
    _MISSING_DEPS.append("jsonschema")

try:
    import anthropic
except ImportError:
    # anthropic es opcional: el script funciona sin él en modo local.
    anthropic = None  # type: ignore

if _MISSING_DEPS:
    print(
        "\n❌ ERROR: Faltan dependencias obligatorias por instalar: "
        + ", ".join(_MISSING_DEPS)
        + "\n\nInstálalas ejecutando en la terminal de VS Code:\n"
        + "    pip install -r requirements.txt\n"
    )
    sys.exit(1)


# ============================================================================
# 1. CONFIGURACIÓN DEL USUARIO — EDITA ESTAS VARIABLES SEGÚN TU CASO
# ============================================================================

# Ruta al documento .docx de entrada. Puede ser absoluta o relativa a la
# carpeta desde la que ejecutes el script en VS Code.
DOCX_INPUT_PATH: str = "./entrada/documento.docx"

# Ruta al archivo de configuración de estilo/parámetros (JSON Schema validado).
CONFIG_PATH: str = "./config.json"

# Nombre de la variable de entorno que contiene la clave de la API de
# Anthropic. NUNCA escribas la clave directamente en este archivo.
ANTHROPIC_API_KEY_ENV_VAR: str = "ANTHROPIC_API_KEY"


# ============================================================================
# 2. ESQUEMA JSON PARA VALIDAR config.json
# ============================================================================

CONFIG_JSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["style", "anthropic", "output", "logging"],
    "additionalProperties": True,
    "properties": {
        "style": {
            "type": "object",
            "required": ["colors", "fonts", "dimensions"],
            "properties": {
                "colors": {
                    "type": "object",
                    "required": [
                        "ink", "panel", "gold", "gold_deep", "white",
                        "off_light", "card_alt", "gray", "gray_light",
                        "line", "green", "amber", "red",
                    ],
                    "patternProperties": {
                        "^[a-z_]+$": {
                            "type": "string",
                            "pattern": "^[0-9A-Fa-f]{6}$",
                        }
                    },
                },
                "fonts": {
                    "type": "object",
                    "required": ["serif_titles", "sans_body", "monospace_code"],
                    "properties": {
                        "serif_titles": {"type": "string", "minLength": 1},
                        "sans_body": {"type": "string", "minLength": 1},
                        "monospace_code": {"type": "string", "minLength": 1},
                    },
                },
                "dimensions": {
                    "type": "object",
                    "required": ["slide_width_in", "slide_height_in", "margin_in"],
                    "properties": {
                        "slide_width_in": {"type": "number", "exclusiveMinimum": 0},
                        "slide_height_in": {"type": "number", "exclusiveMinimum": 0},
                        "margin_in": {"type": "number", "minimum": 0},
                    },
                },
                "footer_label": {"type": "string"},
            },
        },
        "anthropic": {
            "type": "object",
            "required": ["use_api", "model", "max_tokens"],
            "properties": {
                "use_api": {"type": "boolean"},
                "model": {"type": "string", "minLength": 1},
                "max_tokens": {"type": "integer", "minimum": 256, "maximum": 64000},
                "max_retries": {"type": "integer", "minimum": 0, "maximum": 10},
                "retry_base_delay_seconds": {"type": "number", "minimum": 0.1},
                # NOTA IMPORTANTE (léase antes de tocar esto):
                # Desde Claude Sonnet 5 / Claude Opus 4.7 en adelante, la API
                # rechaza con un error 400 cualquier valor NO-DEFAULT de
                # "temperature", "top_p" o "top_k" (son modelos de
                # razonamiento adaptativo; Anthropic recomienda guiar el
                # comportamiento mediante el propio prompt, no mediante
                # muestreo). Por eso "temperature" ya NO es obligatorio ni
                # se envía por defecto — ver "enable_sampling_params" abajo.
                "temperature": {"type": "number", "minimum": 0, "maximum": 1},
                "enable_sampling_params": {"type": "boolean"},
            },
        },
        "output": {
            "type": "object",
            "required": ["output_dir", "filename"],
            "properties": {
                "output_dir": {"type": "string", "minLength": 1},
                "filename": {
                    "type": "string",
                    "pattern": r".*\.pptx$",
                },
            },
        },
        "logging": {
            "type": "object",
            "required": ["level"],
            "properties": {
                "level": {
                    "type": "string",
                    "enum": ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
                },
                "log_file": {"type": "string"},
            },
        },
    },
}


# ============================================================================
# 3. EXCEPCIONES PROPIAS — mensajes claros y en español
# ============================================================================

class ErrorGeneracionPresentacion(Exception):
    """Excepción base para cualquier error controlado de este script."""


class ErrorConfiguracion(ErrorGeneracionPresentacion):
    """La configuración (config.json) no existe, no es JSON válido o no
    cumple el esquema requerido."""


class ErrorDocumentoEntrada(ErrorGeneracionPresentacion):
    """El archivo .docx de entrada no existe, no es accesible o está
    corrupto / no tiene el formato esperado."""


class ErrorApiAnthropic(ErrorGeneracionPresentacion):
    """Error al comunicarse con la API de Anthropic (red, límite de
    peticiones, autenticación, etc.)."""


# ============================================================================
# 4. LOGGING
# ============================================================================

def configurar_logging(nivel: str, ruta_log: Optional[str]) -> logging.Logger:
    """Configura un logger que escribe en consola y, si se indica, en un
    archivo. Todos los mensajes relevantes para el usuario final se emiten
    también mediante `print()` en español; el logger sirve sobre todo para
    depuración técnica."""
    logger = logging.getLogger("generador_presentacion")
    logger.setLevel(getattr(logging, nivel, logging.INFO))
    logger.handlers.clear()

    formato = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(message)s", datefmt="%H:%M:%S"
    )

    consola = logging.StreamHandler(sys.stdout)
    consola.setFormatter(formato)
    logger.addHandler(consola)

    if ruta_log:
        try:
            Path(ruta_log).parent.mkdir(parents=True, exist_ok=True)
            archivo = logging.FileHandler(ruta_log, encoding="utf-8")
            archivo.setFormatter(formato)
            logger.addHandler(archivo)
        except OSError as exc:
            # No es un error fatal: seguimos solo con logging en consola.
            logger.warning(
                "No se pudo crear el archivo de log en '%s' (%s). "
                "Se continuará registrando solo en la consola.",
                ruta_log, exc,
            )

    return logger


# ============================================================================
# 5. CARGA Y VALIDACIÓN DE config.json
# ============================================================================

class GestorConfiguracion:
    """Carga config.json y lo valida estrictamente contra CONFIG_JSON_SCHEMA."""

    def __init__(self, ruta_config: str):
        self.ruta_config = ruta_config
        self.datos: dict[str, Any] = {}

    def cargar_y_validar(self) -> dict[str, Any]:
        ruta = Path(self.ruta_config)

        if not ruta.exists():
            raise ErrorConfiguracion(
                f"No se encontró el archivo de configuración '{self.ruta_config}'. "
                "Asegúrate de que config.json existe junto al script, o ajusta "
                "la variable CONFIG_PATH al inicio del archivo."
            )

        try:
            with ruta.open("r", encoding="utf-8") as f:
                contenido = json.load(f)
        except json.JSONDecodeError as exc:
            raise ErrorConfiguracion(
                f"El archivo '{self.ruta_config}' no contiene JSON válido. "
                f"Detalle técnico: línea {exc.lineno}, columna {exc.colno}: {exc.msg}."
            ) from exc
        except OSError as exc:
            raise ErrorConfiguracion(
                f"No se pudo leer '{self.ruta_config}' (¿permisos de archivo?). "
                f"Detalle técnico: {exc}."
            ) from exc

        try:
            js_validate(instance=contenido, schema=CONFIG_JSON_SCHEMA) # type: ignore
        except JsonSchemaValidationError as exc: # type: ignore
            ruta_campo = " → ".join(str(p) for p in exc.absolute_path) or "(raíz)"
            raise ErrorConfiguracion(
                "El archivo config.json no cumple el formato requerido.\n"
                f"  Campo problemático : {ruta_campo}\n"
                f"  Motivo             : {exc.message}\n"
                "Corrige el archivo config.json y vuelve a ejecutar el script."
            ) from exc

        self.datos = contenido
        return contenido


# ============================================================================
# 6. TEMA VISUAL (paleta, tipografías y medidas ya validadas)
# ============================================================================

@dataclass
class TemaVisual:
    """Encapsula la paleta de colores, tipografías y medidas de la
    presentación, tal como se usaron en el diseño "Editorial Noir" original."""

    ink: RGBColor
    panel: RGBColor
    gold: RGBColor
    gold_deep: RGBColor
    white: RGBColor
    off_light: RGBColor
    card_alt: RGBColor
    gray: RGBColor
    gray_light: RGBColor
    line: RGBColor
    green: RGBColor
    amber: RGBColor
    red: RGBColor

    font_serif: str
    font_sans: str
    font_mono: str

    slide_w_in: float
    slide_h_in: float
    margin_in: float

    footer_label: str

    @staticmethod
    def _rgb(hex_str: str) -> RGBColor:
        return RGBColor.from_string(hex_str.upper()) # type: ignore

    @classmethod
    def desde_config(cls, config: dict[str, Any]) -> "TemaVisual":
        colores = config["style"]["colors"]
        fuentes = config["style"]["fonts"]
        dimensiones = config["style"]["dimensions"]
        return cls(
            ink=cls._rgb(colores["ink"]),
            panel=cls._rgb(colores["panel"]),
            gold=cls._rgb(colores["gold"]),
            gold_deep=cls._rgb(colores["gold_deep"]),
            white=cls._rgb(colores["white"]),
            off_light=cls._rgb(colores["off_light"]),
            card_alt=cls._rgb(colores["card_alt"]),
            gray=cls._rgb(colores["gray"]),
            gray_light=cls._rgb(colores["gray_light"]),
            line=cls._rgb(colores["line"]),
            green=cls._rgb(colores["green"]),
            amber=cls._rgb(colores["amber"]),
            red=cls._rgb(colores["red"]),
            font_serif=fuentes["serif_titles"],
            font_sans=fuentes["sans_body"],
            font_mono=fuentes["monospace_code"],
            slide_w_in=dimensiones["slide_width_in"],
            slide_h_in=dimensiones["slide_height_in"],
            margin_in=dimensiones["margin_in"],
            footer_label=config["style"].get("footer_label", "PRESENTACIÓN"),
        )


# ============================================================================
# 7. EXTRACCIÓN DE CONTENIDO DEL .docx
# ============================================================================

@dataclass
class BloqueContenido:
    """Unidad mínima de contenido extraída del documento: un encabezado,
    un párrafo, un elemento de lista o una tabla."""
    tipo: str  # "heading1" | "heading2" | "paragraph" | "list_item" | "table" | "code"
    texto: str = ""
    nivel: int = 0
    filas_tabla: list[list[str]] = field(default_factory=list)


class ExtractorDocx:
    """Lee un archivo .docx con python-docx y lo convierte en una lista
    plana de BloqueContenido, preservando el orden del documento original
    (incluye párrafos y tablas intercaladas)."""

    ESTILOS_CODIGO = {"Código", "Code", "HTML Code", "Macro Text"}

    def __init__(self, ruta_docx: str, logger: logging.Logger):
        self.ruta_docx = ruta_docx
        self.logger = logger

    def validar_archivo(self) -> None:
        ruta = Path(self.ruta_docx)

        if not ruta.exists():
            raise ErrorDocumentoEntrada(
                f"No se encontró el archivo de entrada '{self.ruta_docx}'.\n"
                "Comprueba la ruta indicada en la variable DOCX_INPUT_PATH, "
                "al principio del script."
            )

        if not ruta.is_file():
            raise ErrorDocumentoEntrada(
                f"La ruta '{self.ruta_docx}' existe pero no es un archivo "
                "(¿es una carpeta?)."
            )

        if ruta.suffix.lower() != ".docx":
            raise ErrorDocumentoEntrada(
                f"El archivo '{self.ruta_docx}' no tiene extensión .docx "
                f"(se encontró '{ruta.suffix}'). Este script solo admite "
                "documentos de Word en formato .docx."
            )

        if not os.access(ruta, os.R_OK):
            raise ErrorDocumentoEntrada(
                f"No tienes permisos de lectura sobre '{self.ruta_docx}'. "
                "Revisa los permisos del archivo."
            )

        if ruta.stat().st_size == 0:
            raise ErrorDocumentoEntrada(
                f"El archivo '{self.ruta_docx}' está vacío (0 bytes)."
            )

    def extraer(self) -> list[BloqueContenido]:
        self.validar_archivo()

        try:
            documento = docx.Document(self.ruta_docx) # type: ignore
        except Exception as exc:  # python-docx lanza distintos tipos según el fallo
            raise ErrorDocumentoEntrada(
                f"No se pudo abrir '{self.ruta_docx}' como documento de Word. "
                "El archivo podría estar corrupto, protegido con contraseña, "
                "o no ser realmente un .docx válido.\n"
                f"Detalle técnico: {exc}"
            ) from exc

        bloques: list[BloqueContenido] = []

        try:
            # Recorremos el cuerpo del documento en orden, distinguiendo
            # párrafos de tablas por su posición en el XML subyacente.
            cuerpo = documento.element.body
            parrafos_por_id = {p._p: p for p in documento.paragraphs}
            tablas_por_id = {t._tbl: t for t in documento.tables}

            for elemento in cuerpo.iterchildren():
                if elemento.tag == qn("w:p") and elemento in parrafos_por_id: # type: ignore
                    parrafo = parrafos_por_id[elemento]
                    bloque = self._procesar_parrafo(parrafo)
                    if bloque is not None:
                        bloques.append(bloque)
                elif elemento.tag == qn("w:tbl") and elemento in tablas_por_id: # type: ignore
                    tabla = tablas_por_id[elemento]
                    bloques.append(self._procesar_tabla(tabla))

        except Exception as exc:
            raise ErrorDocumentoEntrada(
                f"Ocurrió un error inesperado al recorrer el contenido de "
                f"'{self.ruta_docx}'. El documento podría tener una "
                f"estructura no compatible.\nDetalle técnico: {exc}"
            ) from exc

        if not bloques:
            raise ErrorDocumentoEntrada(
                f"El documento '{self.ruta_docx}' no contiene texto "
                "reconocible (¿está vacío o solo tiene imágenes?)."
            )

        self.logger.info(
            "Extracción completada: %d bloques de contenido detectados.",
            len(bloques),
        )
        return bloques

    def _procesar_parrafo(self, parrafo) -> Optional[BloqueContenido]:
        texto = parrafo.text.strip()
        if not texto:
            return None

        estilo = (parrafo.style.name if parrafo.style else "") or ""

        if estilo in self.ESTILOS_CODIGO or self._parece_codigo(texto):
            return BloqueContenido(tipo="code", texto=texto)

        if estilo.startswith("Heading 1") or estilo == "Title":
            return BloqueContenido(tipo="heading1", texto=texto, nivel=1)
        if estilo.startswith("Heading 2"):
            return BloqueContenido(tipo="heading2", texto=texto, nivel=2)
        if estilo.startswith("Heading"):
            return BloqueContenido(tipo="heading2", texto=texto, nivel=3)

        if estilo.startswith("List") or texto.lstrip().startswith(("-", "•", "*")):
            return BloqueContenido(tipo="list_item", texto=texto.lstrip("-•* \t"))

        return BloqueContenido(tipo="paragraph", texto=texto)

    @staticmethod
    def _parece_codigo(texto: str) -> bool:
        """Heurística simple para detectar fragmentos de código Python
        cuando el documento no usa un estilo de párrafo específico."""
        patrones = (r"^\s*(def |import |print\(|for .+ in |if .+:|#.*)",)
        return any(re.match(p, texto) for p in patrones)

    def _procesar_tabla(self, tabla) -> BloqueContenido:
        filas: list[list[str]] = []
        for fila in tabla.rows:
            filas.append([celda.text.strip() for celda in fila.cells])
        return BloqueContenido(tipo="table", filas_tabla=filas)


# ============================================================================
# 8. GUION DE DIAPOSITIVAS (estructura intermedia común a ambos planificadores)
# ============================================================================
#
# Un "guion" es una lista de diccionarios, cada uno describiendo una
# diapositiva. Campos reconocidos por tipo ("type"):
#
#   title        -> kicker, title, subtitle, description
#   agenda       -> title, items: [{numero, titulo, descripcion}, ...]
#   bullets      -> kicker, title, dark, bullets: [str, ...]
#   table        -> kicker, title, dark, columns: [str,...], rows: [[str,...]]
#   code         -> kicker, title, dark, filename, code (str con saltos de línea)
#   quote        -> dark, quote, attribution
#   section      -> kicker, title, dark   (separador de sección, texto grande)
#   conclusion   -> points: [str, ...]
#   references   -> links: [{text, url}, ...]
# ============================================================================


class PlanificadorLocal:
    """Convierte los BloqueContenido extraídos en un guion de diapositivas
    sin necesidad de ninguna API externa. Se usa como método principal
    cuando no hay clave de Anthropic disponible, y como respaldo si la
    llamada a la API falla."""

    MAX_BULLETS_POR_DIAPOSITIVA = 6

    def __init__(self, logger: logging.Logger):
        self.logger = logger

    def planificar(self, bloques: list[BloqueContenido], titulo_doc: str) -> dict[str, Any]:
        self.logger.info("Generando guion de diapositivas de forma local (sin API).")

        slides: list[dict[str, Any]] = []

        titulo_principal = titulo_doc
        subtitulo = ""
        for b in bloques:
            if b.tipo == "heading1":
                titulo_principal = b.texto
                break

        slides.append({
            "type": "title",
            "kicker": "Presentación generada automáticamente",
            "title": titulo_principal,
            "subtitle": subtitulo,
            "description": "Documento convertido automáticamente a partir del archivo .docx de origen.",
        })

        # Agrupamos bloques en secciones delimitadas por heading1/heading2
        secciones: list[tuple[str, list[BloqueContenido]]] = []
        seccion_actual = "Introducción"
        contenido_actual: list[BloqueContenido] = []

        for b in bloques:
            if b.tipo in ("heading1", "heading2"):
                if contenido_actual:
                    secciones.append((seccion_actual, contenido_actual))
                seccion_actual = b.texto
                contenido_actual = []
            else:
                contenido_actual.append(b)
        if contenido_actual:
            secciones.append((seccion_actual, contenido_actual))

        # Diapositiva de agenda si hay varias secciones
        if len(secciones) > 1:
            slides.append({
                "type": "agenda",
                "title": "Qué vamos a recorrer",
                "items": [
                    {
                        "numero": f"{i+1:02d}",
                        "titulo": nombre[:40],
                        "descripcion": self._resumen(contenido, 80),
                    }
                    for i, (nombre, contenido) in enumerate(secciones[:6])
                ],
            })

        dark_alterna = False
        for nombre_seccion, contenido in secciones:
            dark_alterna = not dark_alterna
            slides.extend(self._bloques_a_slides(nombre_seccion, contenido, dark_alterna))

        slides.append({
            "type": "conclusion",
            "points": self._extraer_conclusiones(bloques),
        })

        return {"title": titulo_principal, "slides": slides}

    def _bloques_a_slides(
        self, kicker: str, contenido: list[BloqueContenido], dark: bool
    ) -> list[dict[str, Any]]:
        resultado: list[dict[str, Any]] = []

        codigos = [b for b in contenido if b.tipo == "code"]
        tablas = [b for b in contenido if b.tipo == "table"]
        items = [b for b in contenido if b.tipo in ("list_item", "paragraph")]

        if items:
            texto_titulo = kicker if len(kicker) <= 60 else kicker[:57] + "..."
            bullets = [b.texto for b in items if b.texto][: self.MAX_BULLETS_POR_DIAPOSITIVA]
            if bullets:
                resultado.append({
                    "type": "bullets",
                    "kicker": kicker[:50],
                    "title": texto_titulo,
                    "dark": dark,
                    "bullets": bullets,
                })

        for tabla in tablas:
            if not tabla.filas_tabla:
                continue
            columnas = tabla.filas_tabla[0]
            filas = tabla.filas_tabla[1:]
            resultado.append({
                "type": "table",
                "kicker": kicker[:50],
                "title": "Datos: " + kicker[:40],
                "dark": False,
                "columns": columnas,
                "rows": filas[:8],
            })

        for codigo in codigos:
            resultado.append({
                "type": "code",
                "kicker": kicker[:50],
                "title": "Ejemplo de código",
                "dark": True,
                "filename": "ejemplo.py",
                "code": codigo.texto,
            })

        return resultado

    @staticmethod
    def _resumen(contenido: list[BloqueContenido], longitud: int) -> str:
        texto = " ".join(b.texto for b in contenido if b.texto)
        texto = texto.strip()
        if len(texto) <= longitud:
            return texto
        return texto[: longitud - 1].rsplit(" ", 1)[0] + "…"

    @staticmethod
    def _extraer_conclusiones(bloques: list[BloqueContenido]) -> list[str]:
        candidatos = [b.texto for b in bloques if b.tipo == "list_item"][:5]
        if candidatos:
            return candidatos
        parrafos = [b.texto for b in bloques if b.tipo == "paragraph"][-5:]
        return parrafos or ["Fin de la presentación."]


class PlanificadorClaude:
    """Usa la API de Claude (Anthropic) para transformar el contenido
    extraído del .docx en un guion de diapositivas mejor estructurado y
    redactado, devolviendo JSON estrictamente validado. Incluye reintentos
    con backoff exponencial ante errores de red o límite de peticiones.

    IMPORTANTE sobre parámetros de muestreo (temperature / top_p / top_k):
    A partir de Claude Sonnet 5 y Claude Opus 4.7, la API ya NO acepta
    valores distintos de los predeterminados para estos parámetros —
    cualquier intento de enviarlos devuelve un error 400
    ("`temperature` is deprecated for this model."), porque estos modelos
    usan razonamiento adaptativo interno en lugar de muestreo controlado
    externamente. La migración recomendada por Anthropic es NO enviar
    estos parámetros en absoluto y, si se necesita más determinismo,
    pedirlo explícitamente en el propio prompt (p. ej. "responde siempre
    con el mismo JSON estructurado, sin variaciones creativas").

    Por eso, por defecto, este planificador NO envía "temperature" a la
    API. Si necesitas usar un modelo anterior a Sonnet 4.6/Opus 4.7 que sí
    admita este parámetro, activa "anthropic.enable_sampling_params": true
    en config.json y se incluirá el valor de "anthropic.temperature"."""

    ESQUEMA_RESPUESTA: dict[str, Any] = {
        "type": "object",
        "required": ["title", "slides"],
        "properties": {
            "title": {"type": "string"},
            "slides": {
                "type": "array",
                "minItems": 1,
                "items": {
                    "type": "object",
                    "required": ["type"],
                    "properties": {
                        "type": {
                            "type": "string",
                            "enum": [
                                "title", "agenda", "bullets", "table",
                                "code", "quote", "section", "conclusion",
                                "references",
                            ],
                        }
                    },
                },
            },
        },
    }

    def __init__(self, api_key: str, config: dict[str, Any], logger: logging.Logger):
        self.logger = logger
        self.cfg = config["anthropic"]
        self.cliente = anthropic.Anthropic(api_key=api_key) # type: ignore

    def planificar(self, bloques: list[BloqueContenido], titulo_doc: str) -> dict[str, Any]:
        contenido_textual = self._serializar_bloques(bloques)
        prompt = self._construir_prompt(contenido_textual, titulo_doc)

        max_reintentos = self.cfg.get("max_retries", 4)
        espera_base = self.cfg.get("retry_base_delay_seconds", 2.0)

        kwargs_api = self._construir_kwargs_api(prompt)

        ultimo_error: Optional[Exception] = None

        for intento in range(1, max_reintentos + 1):
            try:
                self.logger.info(
                    "Llamando a la API de Anthropic (modelo=%s, intento %d/%d)...",
                    self.cfg["model"], intento, max_reintentos,
                )
                respuesta = self.cliente.messages.create(**kwargs_api)
                texto_json = self._extraer_texto(respuesta)
                guion = self._parsear_y_validar(texto_json)
                self.logger.info(
                    "Guion recibido de Claude: %d diapositivas planificadas.",
                    len(guion["slides"]),
                )
                return guion

            except (json.JSONDecodeError, JsonSchemaValidationError) as exc: # type: ignore
                # La respuesta no vino en el formato esperado: no tiene
                # sentido reintentar igual, pero probamos una vez más por
                # si fue un fallo puntual del modelo.
                ultimo_error = exc
                self.logger.warning(
                    "La respuesta de Claude no es un guion JSON válido "
                    "(intento %d/%d): %s", intento, max_reintentos, exc,
                )

            except anthropic.RateLimitError as exc: # type: ignore
                ultimo_error = exc
                espera = espera_base * (2 ** (intento - 1))
                self.logger.warning(
                    "Límite de peticiones alcanzado en la API de Anthropic. "
                    "Reintentando en %.1f segundos...", espera,
                )
                time.sleep(espera)

            except anthropic.APIConnectionError as exc: # type: ignore
                ultimo_error = exc
                espera = espera_base * (2 ** (intento - 1))
                self.logger.warning(
                    "Error de conexión con la API de Anthropic (%s). "
                    "Reintentando en %.1f segundos...", exc, espera,
                )
                time.sleep(espera)

            except anthropic.AuthenticationError as exc: # type: ignore
                # No tiene sentido reintentar: la clave es inválida.
                raise ErrorApiAnthropic(
                    "La clave de la API de Anthropic no es válida o ha "
                    f"expirado. Comprueba la variable de entorno "
                    f"'{ANTHROPIC_API_KEY_ENV_VAR}'.\nDetalle técnico: {exc}"
                ) from exc

            except anthropic.BadRequestError as exc: # type: ignore
                # Error 400: la petición está mal formada. Reintentar sin
                # cambiar nada no arreglaría el problema, así que fallamos
                # de inmediato con un diagnóstico lo más útil posible.
                mensaje_original = str(exc)
                if any(
                    palabra in mensaje_original.lower()
                    for palabra in ("temperature", "top_p", "top_k")
                ) and "deprecat" in mensaje_original.lower():
                    raise ErrorApiAnthropic(
                        "El modelo configurado "
                        f"('{self.cfg['model']}') ha dejado de aceptar los "
                        "parámetros de muestreo (temperature / top_p / "
                        "top_k): este es un modelo de razonamiento "
                        "adaptativo y Anthropic ya no permite fijar esos "
                        "valores manualmente.\n"
                        "Esto no debería ocurrir con la configuración por "
                        "defecto de este script (no se envían parámetros "
                        "de muestreo salvo que actives "
                        "'anthropic.enable_sampling_params' en config.json). "
                        "Si activaste esa opción, ponla de nuevo en "
                        "'false' para modelos recientes (Claude Sonnet 5, "
                        "Claude Opus 4.7 o posteriores).\n"
                        f"Detalle técnico: {exc}"
                    ) from exc

                raise ErrorApiAnthropic(
                    "La API de Anthropic rechazó la petición por estar mal "
                    f"formada (error 400). Revisa el modelo configurado "
                    f"('{self.cfg['model']}') y los parámetros en "
                    f"config.json.\nDetalle técnico: {exc}"
                ) from exc

            except anthropic.APIStatusError as exc: # type: ignore
                # Otros errores del servidor (5xx, etc.): sí merece la pena
                # reintentar, ya que suelen ser transitorios.
                ultimo_error = exc
                self.logger.warning(
                    "La API de Anthropic devolvió un error (código %s): %s",
                    getattr(exc, "status_code", "?"), exc,
                )
                time.sleep(espera_base)

        raise ErrorApiAnthropic(
            "No se pudo obtener un guion de diapositivas válido de la API "
            f"de Anthropic tras {max_reintentos} intentos. "
            f"Último error: {ultimo_error}"
        )

    def _construir_kwargs_api(self, prompt: str) -> dict[str, Any]:
        """Construye los argumentos de la llamada a messages.create().

        Por defecto NO incluye "temperature" (ni top_p/top_k): en Claude
        Sonnet 5 y Claude Opus 4.7+ estos parámetros de muestreo están
        deprecados y su sola presencia en la petición —con cualquier
        valor— provoca un error 400. Si necesitas usarlos porque tu
        config.json apunta a un modelo anterior compatible, activa
        "anthropic.enable_sampling_params": true.
        """
        kwargs: dict[str, Any] = {
            "model": self.cfg["model"],
            "max_tokens": self.cfg["max_tokens"],
            "messages": [{"role": "user", "content": prompt}],
        }

        if self.cfg.get("enable_sampling_params", False) and "temperature" in self.cfg:
            kwargs["temperature"] = self.cfg["temperature"]
            self.logger.info(
                "anthropic.enable_sampling_params está activo: se enviará "
                "temperature=%s. Esto solo es compatible con modelos "
                "anteriores a Claude Sonnet 5 / Claude Opus 4.7.",
                self.cfg["temperature"],
            )

        return kwargs

    @staticmethod
    def _serializar_bloques(bloques: list[BloqueContenido]) -> str:
        lineas = []
        for b in bloques:
            if b.tipo == "heading1":
                lineas.append(f"# {b.texto}")
            elif b.tipo == "heading2":
                lineas.append(f"## {b.texto}")
            elif b.tipo == "list_item":
                lineas.append(f"- {b.texto}")
            elif b.tipo == "code":
                lineas.append(f"```\n{b.texto}\n```")
            elif b.tipo == "table":
                for fila in b.filas_tabla:
                    lineas.append(" | ".join(fila))
            else:
                lineas.append(b.texto)
        return "\n".join(lineas)

    @staticmethod
    def _construir_prompt(contenido: str, titulo_doc: str) -> str:
        return f"""Eres un diseñador instruccional experto en crear presentaciones
académicas de PowerPoint. A partir del siguiente contenido extraído de un
documento de Word (título de referencia: "{titulo_doc}"), genera un guion de
diapositivas en formato JSON estricto, en español de España.

Devuelve ÚNICAMENTE un objeto JSON (sin texto adicional, sin explicaciones,
sin bloques de markdown ```), con esta forma exacta:

{{
  "title": "Título general de la presentación",
  "slides": [
    {{"type": "title", "kicker": "...", "title": "...", "subtitle": "...", "description": "..."}},
    {{"type": "agenda", "title": "...", "items": [{{"numero": "01", "titulo": "...", "descripcion": "..."}}]}},
    {{"type": "bullets", "kicker": "...", "title": "...", "dark": false, "bullets": ["...", "..."]}},
    {{"type": "table", "kicker": "...", "title": "...", "dark": false, "columns": ["...","..."], "rows": [["...","..."]]}},
    {{"type": "code", "kicker": "...", "title": "...", "dark": true, "filename": "ejemplo.py", "code": "línea1\\nlínea2"}},
    {{"type": "quote", "dark": true, "quote": "...", "attribution": "..."}},
    {{"type": "conclusion", "points": ["...", "..."]}},
    {{"type": "references", "links": [{{"text": "...", "url": "https://..."}}]}}
  ]
}}

Reglas:
- La primera diapositiva SIEMPRE debe ser de tipo "title".
- Usa entre 8 y 20 diapositivas en total, según la cantidad de contenido.
- Alterna "dark": true / false de forma razonable para dar ritmo visual.
- Los bullets deben ser concisos (máximo ~15 palabras cada uno).
- Conserva la terminología técnica y los ejemplos de código tal cual
  aparecen en el contenido original.
- La última diapositiva debe ser de tipo "references" si el documento
  original incluye enlaces o bibliografía; si no, usa "conclusion".

CONTENIDO DEL DOCUMENTO:
---
{contenido[:12000]}
---
"""

    @staticmethod
    def _extraer_texto(respuesta: Any) -> str:
        partes = [bloque.text for bloque in respuesta.content if bloque.type == "text"]
        return "\n".join(partes).strip()

    @classmethod
    def _parsear_y_validar(cls, texto_json: str) -> dict[str, Any]:
        texto_limpio = texto_json.strip()
        # Por si el modelo envuelve la respuesta en ```json ... ``` a pesar
        # de la instrucción de no hacerlo.
        texto_limpio = re.sub(r"^```(json)?", "", texto_limpio).strip()
        texto_limpio = re.sub(r"```$", "", texto_limpio).strip()

        datos = json.loads(texto_limpio)
        js_validate(instance=datos, schema=cls.ESQUEMA_RESPUESTA) # type: ignore
        return datos


# ============================================================================
# 9. CONSTRUCCIÓN DEL .pptx (réplica del estilo "Editorial Noir")
# ============================================================================

class ConstructorPptx:
    """Construye el archivo .pptx aplicando el mismo lenguaje visual usado
    en las presentaciones anteriores del curso: kicker + título en la
    cabecera, pie de página con etiqueta de sección y numeración, tarjetas
    de agenda, bloques de código estilo editor, tablas con cabecera oscura
    y filas alternas, etc."""

    def __init__(self, tema: TemaVisual, logger: logging.Logger):
        self.t = tema
        self.logger = logger
        self.prs = Presentation() # type: ignore
        self.prs.slide_width = Inches(tema.slide_w_in) # type: ignore
        self.prs.slide_height = Inches(tema.slide_h_in) # type: ignore
        self._layout_blanco = self.prs.slide_layouts[6]
        self.cw = tema.slide_w_in - 2 * tema.margin_in  # ancho de contenido

    # -- utilidades de bajo nivel -------------------------------------------------

    def _nueva_diapositiva(self, oscura: bool = False):
        slide = self.prs.slides.add_slide(self._layout_blanco)
        fondo = slide.shapes.add_shape(
            MSO_SHAPE.RECTANGLE, 0, 0, self.prs.slide_width, self.prs.slide_height # type: ignore
        )
        fondo.fill.solid()
        fondo.fill.fore_color.rgb = self.t.ink if oscura else self.t.white
        fondo.line.fill.background()
        fondo.shadow.inherit = False
        # Enviamos el fondo detrás de cualquier otro elemento futuro.
        return slide

    def _rect(self, slide, x, y, w, h, color: RGBColor):
        forma = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(x), Inches(y), Inches(w), Inches(h)) # type: ignore
        forma.fill.solid()
        forma.fill.fore_color.rgb = color
        forma.line.fill.background()
        forma.shadow.inherit = False
        return forma

    def _circulo(self, slide, x, y, d, color: RGBColor, contorno: bool = False):
        forma = slide.shapes.add_shape(MSO_SHAPE.OVAL, Inches(x), Inches(y), Inches(d), Inches(d)) # type: ignore
        if contorno:
            forma.fill.background()
            forma.line.color.rgb = color
            forma.line.width = Pt(1.2) # type: ignore
        else:
            forma.fill.solid()
            forma.fill.fore_color.rgb = color
            forma.line.fill.background()
        forma.shadow.inherit = False
        return forma

    def _texto(
        self, slide, x, y, w, h, texto: str, *, fuente: str, tam: float,
        color: RGBColor, negrita: bool = False, cursiva: bool = False,
        alineacion=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP, interlineado: float = 1.15, # type: ignore
        espaciado: Optional[float] = None,
    ):
        caja = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h)) # type: ignore
        tf = caja.text_frame
        tf.word_wrap = True
        tf.vertical_anchor = anchor
        tf.margin_left = 0
        tf.margin_right = 0
        tf.margin_top = 0
        tf.margin_bottom = 0

        lineas = texto.split("\n")
        for i, linea in enumerate(lineas):
            p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
            p.alignment = alineacion
            p.line_spacing = interlineado
            run = p.add_run()
            run.text = linea
            run.font.name = fuente
            run.font.size = Pt(tam) # type: ignore
            run.font.bold = negrita
            run.font.italic = cursiva
            run.font.color.rgb = color
            if espaciado is not None:
                self._aplicar_tracking(run, espaciado)
        return caja

    @staticmethod
    def _aplicar_tracking(run, puntos: float) -> None:
        """python-pptx no expone letter-spacing directamente; lo aplicamos
        escribiendo el atributo XML `spc` (en centésimas de punto)."""
        rPr = run._r.get_or_add_rPr()
        rPr.set("spc", str(int(puntos * 100)))

    def _kicker(self, slide, texto: str, oscuro_bg: bool = False):
        self._texto(
            slide, self.t.margin_in, 0.55, self.cw, 0.35, texto.upper(),
            fuente=self.t.font_sans, tam=12, color=self.t.gold, negrita=True,
            espaciado=1.5,
        )

    def _titulo_seccion(self, slide, texto: str, oscuro_bg: bool):
        color = self.t.white if oscuro_bg else self.t.ink
        self._texto(
            slide, self.t.margin_in, 0.88, self.cw, 0.9, texto,
            fuente=self.t.font_serif, tam=28, color=color, negrita=True,
        )

    def _pie_pagina(self, slide, numero: int, total: int, oscuro_bg: bool):
        y = self.t.slide_h_in - 0.42
        self._texto(
            slide, self.t.margin_in, y, self.cw - 1.5, 0.3, self.t.footer_label,
            fuente=self.t.font_sans, tam=8, color=self.t.gray_light,
            espaciado=1.0,
        )
        self._texto(
            slide, self.t.slide_w_in - self.t.margin_in - 1.2, y, 1.2, 0.3,
            f"{numero:02d} / {total:02d}", fuente=self.t.font_sans, tam=9,
            color=self.t.gold if oscuro_bg else self.t.gold_deep, negrita=True,
            alineacion=PP_ALIGN.RIGHT, # type: ignore
        )

    def _encabezado_contenido(self, slide, kicker: str, titulo: str, oscuro_bg: bool):
        self._kicker(slide, kicker, oscuro_bg)
        self._titulo_seccion(slide, titulo, oscuro_bg)

    # -- constructores de cada tipo de diapositiva --------------------------------

    def _slide_title(self, datos: dict[str, Any], numero: int, total: int):
        slide = self._nueva_diapositiva(oscura=True)
        # Anillos decorativos (círculos concéntricos sin relleno) en la esquina.
        self._circulo(slide, self.t.slide_w_in - 3.7, -2.2, 6.5, self.t.gold, contorno=True)
        self._circulo(slide, self.t.slide_w_in - 2.7, -1.2, 4.5, self.t.gold, contorno=True)

        self._kicker(slide, datos.get("kicker", ""), oscuro_bg=True)
        self._texto(
            slide, self.t.margin_in, 1.55, self.cw - 2.0, 1.9, datos.get("title", ""),
            fuente=self.t.font_serif, tam=38, color=self.t.white, negrita=True,
            interlineado=1.05,
        )
        if datos.get("subtitle"):
            self._texto(
                slide, self.t.margin_in, 3.35, self.cw - 2.5, 0.7, datos["subtitle"],
                fuente=self.t.font_serif, tam=22, color=self.t.gold, cursiva=True,
            )
        if datos.get("description"):
            self._texto(
                slide, self.t.margin_in, 4.25, min(self.cw, 8.8), 0.9, datos["description"],
                fuente=self.t.font_sans, tam=13.5, color=self.t.gray_light, interlineado=1.25,
            )
        self._pie_pagina(slide, numero, total, oscuro_bg=True)

    def _slide_agenda(self, datos: dict[str, Any], numero: int, total: int):
        slide = self._nueva_diapositiva(oscura=False)
        self._encabezado_contenido(slide, "Índice de la sesión", datos.get("title", ""), False)

        items = datos.get("items", [])[:6]
        col_w = (self.cw - 0.5) / 3
        row_h = 2.55
        for i, item in enumerate(items):
            col, fila = i % 3, i // 3
            x = self.t.margin_in + col * (col_w + 0.25)
            y = 2.0 + fila * (row_h + 0.25)
            self._rect(slide, x, y, col_w, row_h, self.t.off_light)
            self._texto(
                slide, x + 0.25, y + 0.2, 1.5, 0.5, item.get("numero", f"{i+1:02d}"),
                fuente=self.t.font_serif, tam=24, color=self.t.gold_deep, negrita=True,
            )
            self._texto(
                slide, x + 0.25, y + 0.85, col_w - 0.5, 0.4, item.get("titulo", ""),
                fuente=self.t.font_sans, tam=14, color=self.t.ink, negrita=True,
            )
            self._texto(
                slide, x + 0.25, y + 1.28, col_w - 0.5, 1.1, item.get("descripcion", ""),
                fuente=self.t.font_sans, tam=10.5, color=self.t.gray, interlineado=1.2,
            )
        self._pie_pagina(slide, numero, total, oscuro_bg=False)

    def _slide_bullets(self, datos: dict[str, Any], numero: int, total: int):
        oscuro = bool(datos.get("dark", False))
        slide = self._nueva_diapositiva(oscura=oscuro)
        self._encabezado_contenido(slide, datos.get("kicker", ""), datos.get("title", ""), oscuro)

        color_texto = self.t.white if oscuro else self.t.ink
        color_marca = self.t.gold

        y = 2.05
        for bullet in datos.get("bullets", []):
            self._circulo(slide, self.t.margin_in + 0.02, y + 0.1, 0.09, color_marca)
            self._texto(
                slide, self.t.margin_in + 0.3, y, self.cw - 0.3, 0.55, bullet,
                fuente=self.t.font_sans, tam=14, color=color_texto, interlineado=1.2,
                anchor=MSO_ANCHOR.TOP, # type: ignore
            )
            y += 0.62
        self._pie_pagina(slide, numero, total, oscuro)

    def _slide_table(self, datos: dict[str, Any], numero: int, total: int):
        oscuro = bool(datos.get("dark", False))
        slide = self._nueva_diapositiva(oscura=oscuro)
        self._encabezado_contenido(slide, datos.get("kicker", ""), datos.get("title", ""), oscuro)

        columnas = datos.get("columns", [])
        filas = datos.get("rows", [])
        if not columnas:
            self._pie_pagina(slide, numero, total, oscuro)
            return

        n_filas = len(filas) + 1
        n_cols = len(columnas)
        alto_fila = 0.5
        alto_total = min(alto_fila * n_filas, 4.6)

        tabla_shape = slide.shapes.add_table(
            n_filas, n_cols, Inches(self.t.margin_in), Inches(2.0), # type: ignore
            Inches(self.cw), Inches(alto_total), # type: ignore
        )
        tabla = tabla_shape.table

        for j, encabezado in enumerate(columnas):
            celda = tabla.cell(0, j)
            celda.text = str(encabezado)
            celda.fill.solid()
            celda.fill.fore_color.rgb = self.t.ink
            self._formatear_celda(celda, self.t.gold, self.t.font_sans, 12, negrita=True)

        for i, fila in enumerate(filas, start=1):
            for j in range(n_cols):
                valor = fila[j] if j < len(fila) else ""
                celda = tabla.cell(i, j)
                celda.text = str(valor)
                celda.fill.solid()
                celda.fill.fore_color.rgb = self.t.off_light if i % 2 == 0 else self.t.white
                self._formatear_celda(celda, self.t.ink, self.t.font_sans, 11)

        self._pie_pagina(slide, numero, total, oscuro)

    @staticmethod
    def _formatear_celda(celda, color: RGBColor, fuente: str, tam: float, negrita: bool = False):
        celda.margin_left = Pt(6) # type: ignore
        celda.margin_right = Pt(6) # type: ignore
        celda.margin_top = Pt(4) # type: ignore
        celda.margin_bottom = Pt(4) # type: ignore
        celda.vertical_anchor = MSO_ANCHOR.MIDDLE # type: ignore
        for p in celda.text_frame.paragraphs:
            p.alignment = PP_ALIGN.LEFT # type: ignore
            for run in p.runs:
                run.font.name = fuente
                run.font.size = Pt(tam) # type: ignore
                run.font.bold = negrita
                run.font.color.rgb = color

    def _slide_code(self, datos: dict[str, Any], numero: int, total: int):
        slide = self._nueva_diapositiva(oscura=datos.get("dark", True))
        self._encabezado_contenido(
            slide, datos.get("kicker", ""), datos.get("title", ""), datos.get("dark", True)
        )

        y0 = 1.95
        alto = 4.6
        self._rect(slide, self.t.margin_in, y0, self.cw, alto, RGBColor(0x0D, 0x0D, 0x0B)) # type: ignore

        # Puntos de "semáforo" estilo editor de código (rojo/ámbar/verde).
        for i, color in enumerate((self.t.red, self.t.amber, self.t.green)):
            self._circulo(slide, self.t.margin_in + 0.25 + i * 0.25, y0 + 0.2, 0.16, color)

        nombre_archivo = datos.get("filename", "codigo.py")
        self._texto(
            slide, self.t.margin_in + 1.1, y0 + 0.1, 6, 0.35, nombre_archivo,
            fuente=self.t.font_mono, tam=11, color=self.t.gray_light,
        )

        codigo = datos.get("code", "")
        caja = slide.shapes.add_textbox(
            Inches(self.t.margin_in + 0.3), Inches(y0 + 0.55), # type: ignore
            Inches(self.cw - 0.6), Inches(alto - 0.75), # type: ignore
        )
        tf = caja.text_frame
        tf.word_wrap = True
        for i, linea in enumerate(codigo.split("\n")):
            p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
            p.line_spacing = 1.1
            run = p.add_run()
            run.text = linea if linea.strip() else " "
            run.font.name = self.t.font_mono
            run.font.size = Pt(12) # type: ignore
            if linea.strip().startswith("#"):
                run.font.color.rgb = self.t.green
            elif '"' in linea or "'" in linea:
                run.font.color.rgb = RGBColor(0xE8, 0xC1, 0x70) # pyright: ignore[reportPossiblyUnboundVariable]
            else:
                run.font.color.rgb = RGBColor(0xE8, 0xE4, 0xDA) # type: ignore

        self._pie_pagina(slide, numero, total, True)

    def _slide_quote(self, datos: dict[str, Any], numero: int, total: int):
        oscuro = bool(datos.get("dark", True))
        slide = self._nueva_diapositiva(oscura=oscuro)
        self._circulo(slide, -2, 4.2, 6, self.t.gold, contorno=True)

        color_texto = self.t.white if oscuro else self.t.ink
        self._texto(
            slide, self.t.margin_in, 2.5, self.cw - 2.5, 2.2, datos.get("quote", ""),
            fuente=self.t.font_serif, tam=28, color=color_texto, negrita=True,
            cursiva=True, interlineado=1.2,
        )
        if datos.get("attribution"):
            self._texto(
                slide, self.t.margin_in, 4.9, self.cw - 2.5, 0.6, datos["attribution"],
                fuente=self.t.font_sans, tam=13, color=self.t.gold, interlineado=1.2,
            )
        self._pie_pagina(slide, numero, total, oscuro)

    def _slide_section(self, datos: dict[str, Any], numero: int, total: int):
        oscuro = bool(datos.get("dark", True))
        slide = self._nueva_diapositiva(oscura=oscuro)
        self._encabezado_contenido(slide, datos.get("kicker", ""), datos.get("title", ""), oscuro)
        self._pie_pagina(slide, numero, total, oscuro)

    def _slide_conclusion(self, datos: dict[str, Any], numero: int, total: int):
        slide = self._nueva_diapositiva(oscura=True)
        self._circulo(slide, self.t.slide_w_in - 3.5, 4.5, 5, self.t.gold, contorno=True)
        self._kicker(slide, "Cierre de la sesión", oscuro_bg=True)
        self._texto(
            slide, self.t.margin_in, 1.2, 8, 0.9, "Conclusión",
            fuente=self.t.font_serif, tam=36, color=self.t.white, negrita=True,
        )
        y = 2.3
        for punto in datos.get("points", []):
            self._circulo(slide, self.t.margin_in, y, 0.34, self.t.gold)
            self._texto(
                slide, self.t.margin_in + 0.55, y - 0.06, min(self.cw - 0.55, 10.0), 0.65,
                punto, fuente=self.t.font_sans, tam=13, color=self.t.white, interlineado=1.2,
            )
            y += 0.78
        self._pie_pagina(slide, numero, total, True)

    def _slide_references(self, datos: dict[str, Any], numero: int, total: int):
        slide = self._nueva_diapositiva(oscura=False)
        self._encabezado_contenido(slide, "Cierre", "Referencias y enlaces adicionales", False)

        y = 2.0
        for enlace in datos.get("links", []):
            self._circulo(slide, self.t.margin_in, y, 0.4, self.t.ink)
            self._texto(
                slide, self.t.margin_in + 0.6, y - 0.02, 8, 0.35, enlace.get("text", ""),
                fuente=self.t.font_sans, tam=13, color=self.t.ink, negrita=True,
            )
            self._texto(
                slide, self.t.margin_in + 0.6, y + 0.32, 9.5, 0.3, enlace.get("url", ""),
                fuente=self.t.font_sans, tam=10, color=self.t.gray_light,
            )
            y += 0.78
        self._pie_pagina(slide, numero, total, False)

    # -- orquestación ---------------------------------------------------------------

    _DESPACHADOR = {
        "title": "_slide_title",
        "agenda": "_slide_agenda",
        "bullets": "_slide_bullets",
        "table": "_slide_table",
        "code": "_slide_code",
        "quote": "_slide_quote",
        "section": "_slide_section",
        "conclusion": "_slide_conclusion",
        "references": "_slide_references",
    }

    def construir(self, guion: dict[str, Any]) -> None:
        diapositivas = guion.get("slides", [])
        total = len(diapositivas)
        if total == 0:
            raise ErrorGeneracionPresentacion(
                "El guion de diapositivas está vacío: no hay nada que generar."
            )

        for i, datos in enumerate(diapositivas, start=1):
            tipo = datos.get("type", "bullets")
            metodo_nombre = self._DESPACHADOR.get(tipo, "_slide_bullets")
            metodo = getattr(self, metodo_nombre)
            try:
                metodo(datos, i, total)
            except Exception as exc:
                raise ErrorGeneracionPresentacion(
                    f"Error al construir la diapositiva {i} (tipo '{tipo}'): {exc}"
                ) from exc
            self.logger.debug("Diapositiva %d/%d ('%s') generada.", i, total, tipo)

    def guardar(self, ruta_salida: str) -> str:
        ruta = Path(ruta_salida)
        try:
            ruta.parent.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise ErrorGeneracionPresentacion(
                f"No se pudo crear la carpeta de salida '{ruta.parent}'. "
                f"Detalle técnico: {exc}"
            ) from exc

        try:
            self.prs.save(str(ruta))
        except PermissionError as exc:
            raise ErrorGeneracionPresentacion(
                f"No se pudo guardar '{ruta}': permiso denegado. "
                "¿El archivo está abierto en PowerPoint? Ciérralo e inténtalo de nuevo."
            ) from exc
        except OSError as exc:
            raise ErrorGeneracionPresentacion(
                f"No se pudo guardar el archivo en '{ruta}'. Detalle técnico: {exc}"
            ) from exc

        return str(ruta.resolve())


# ============================================================================
# 10. ORQUESTACIÓN PRINCIPAL
# ============================================================================

def _obtener_planificador(
    config: dict[str, Any], logger: logging.Logger
) -> tuple[Any, str]:
    """Decide si se usa el planificador basado en Claude o el local,
    devolviendo también una descripción legible del modo elegido."""

    usar_api = config["anthropic"].get("use_api", False)
    clave_api = os.environ.get(ANTHROPIC_API_KEY_ENV_VAR, "").strip()

    if not usar_api:
        logger.info(
            "La opción 'anthropic.use_api' está desactivada en config.json: "
            "se usará el planificador local."
        )
        return PlanificadorLocal(logger), "local (sin API)"

    if anthropic is None:
        logger.warning(
            "La librería 'anthropic' no está instalada. Instálala con "
            "'pip install anthropic' para usar la API, o pon "
            "'anthropic.use_api' en 'false' en config.json. "
            "Se continuará en modo local."
        )
        return PlanificadorLocal(logger), "local (librería anthropic no instalada)"

    if not clave_api:
        logger.warning(
            "No se encontró la variable de entorno '%s'. Se continuará "
            "generando el guion de diapositivas de forma local, sin IA. "
            "Si quieres usar la API de Claude, define esa variable de entorno.",
            ANTHROPIC_API_KEY_ENV_VAR,
        )
        return PlanificadorLocal(logger), "local (sin clave de API)"

    return PlanificadorClaude(clave_api, config, logger), f"Claude ({config['anthropic']['model']})"


def generar_presentacion(
    ruta_docx: str = DOCX_INPUT_PATH,
    ruta_config: str = CONFIG_PATH,
) -> str:
    """Función de alto nivel que ejecuta todo el proceso de conversión y
    devuelve la ruta absoluta del .pptx generado. Lanza subclases de
    ErrorGeneracionPresentacion con mensajes claros en español ante
    cualquier fallo controlado."""

    # 1) Configuración -----------------------------------------------------
    gestor_config = GestorConfiguracion(ruta_config)
    config = gestor_config.cargar_y_validar()

    logger = configurar_logging(
        config["logging"]["level"], config["logging"].get("log_file"),
    )
    logger.info("=" * 70)
    logger.info("Iniciando generación de presentación a partir de: %s", ruta_docx)

    tema = TemaVisual.desde_config(config)

    # 2) Extracción del .docx ----------------------------------------------
    extractor = ExtractorDocx(ruta_docx, logger)
    bloques = extractor.extraer()
    titulo_doc = Path(ruta_docx).stem.replace("_", " ").title()

    # 3) Planificación del guion (Claude o local) ---------------------------
    planificador, modo = _obtener_planificador(config, logger)
    logger.info("Modo de planificación seleccionado: %s", modo)

    try:
        guion = planificador.planificar(bloques, titulo_doc)
    except ErrorApiAnthropic as exc:
        logger.warning(
            "Falló la planificación con la API de Anthropic (%s). "
            "Se usará el planificador local como respaldo.", exc,
        )
        guion = PlanificadorLocal(logger).planificar(bloques, titulo_doc)

    # 4) Construcción del .pptx ---------------------------------------------
    constructor = ConstructorPptx(tema, logger)
    constructor.construir(guion)

    nombre_salida = config["output"]["filename"]
    carpeta_salida = config["output"]["output_dir"]
    ruta_final = Path(carpeta_salida) / nombre_salida
    ruta_absoluta = constructor.guardar(str(ruta_final))

    logger.info("Presentación guardada correctamente en: %s", ruta_absoluta)
    return ruta_absoluta


# ============================================================================
# 11. PUNTO DE ENTRADA
# ============================================================================

def main() -> int:
    print("\n" + "=" * 70)
    print(" GENERADOR DE PRESENTACIONES .pptx A PARTIR DE .docx")
    print(" Estilo: Editorial Noir (negro / dorado)")
    print("=" * 70 + "\n")

    try:
        ruta_generada = generar_presentacion(DOCX_INPUT_PATH, CONFIG_PATH)
    except ErrorConfiguracion as exc:
        print(f"\n❌ ERROR DE CONFIGURACIÓN\n{exc}\n")
        return 1
    except ErrorDocumentoEntrada as exc:
        print(f"\n❌ ERROR CON EL DOCUMENTO DE ENTRADA\n{exc}\n")
        return 1
    except ErrorApiAnthropic as exc:
        print(f"\n❌ ERROR DE LA API DE ANTHROPIC\n{exc}\n")
        return 1
    except ErrorGeneracionPresentacion as exc:
        print(f"\n❌ ERROR AL GENERAR LA PRESENTACIÓN\n{exc}\n")
        return 1
    except Exception as exc:  # salvaguarda final: nunca mostrar un traceback crudo
        print(
            "\n❌ ERROR INESPERADO\n"
            f"Ocurrió un problema no previsto: {exc}\n"
            "Si el problema persiste, revisa el archivo de log para más detalles.\n"
        )
        logging.getLogger("generador_presentacion").exception("Error inesperado")
        return 1

    print("\n✅ ¡Presentación generada con éxito!")
    print(f"   Archivo: {ruta_generada}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
