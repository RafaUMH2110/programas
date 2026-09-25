#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
docx_guide_generator.py
========================

Turns a source file (a Jupyter/Colab notebook or a plain-text/Markdown design
brief) into a polished, beginner-friendly Word practice guide — using Claude
to analyze the source and write the content, and `python-docx` to render it
with a fixed, reusable visual design system (light color palette, Cambria /
Calibri typography, styled tables, callout boxes, a cover page, running
headers/footers, and an auto-updating table of contents).

--------------------------------------------------------------------------
HOW THIS PIPELINE WORKS (two clearly separated stages)
--------------------------------------------------------------------------
Claude's API returns *text*, never a .docx file directly. So this tool splits
the work into two stages with a clean boundary between them:

    1. CONTENT  (Claude)      Reads your source file and returns a strict
                               JSON description of the guide's content:
                               headings, paragraphs, bullet/numbered lists,
                               tables, callout boxes, and ready-to-paste
                               "prompt card" examples.

    2. RENDERING (this script) Walks that JSON, deterministically, and
                               builds the .docx with python-docx: every
                               color, font, table border and callout-box
                               style is defined once in `Palette` /
                               `GuideDocxWriter` below, so every guide you
                               generate looks consistent — the same way a
                               real design system would.

This separation matters: it means formatting NEVER depends on Claude "getting
the styling right" in free text — Claude only ever chooses *content*, and the
code guarantees the *appearance*. It also means this script cannot reproduce
hand-drawn diagrams (e.g. a custom pipeline illustration) — those were
bespoke artwork, not something a text model can emit. See `--images` below
for a way to slot pre-made diagrams back in.

--------------------------------------------------------------------------
INSTALLATION
--------------------------------------------------------------------------
Dependencies (also saved alongside this file as requirements.txt):

    anthropic>=0.40.0
    python-docx>=1.1.0
    python-dotenv>=1.0.0   # optional — see "Running from VS Code" below

Install with:

    pip install -r requirements.txt

--------------------------------------------------------------------------
USAGE
--------------------------------------------------------------------------
As a command-line tool:

    python docx_guide_generator.py path/to/notebook.ipynb
    python docx_guide_generator.py brief.md -o guide.docx --model claude-opus-4-5
    python docx_guide_generator.py brief.md --max-tokens 16000

As a library:

    from docx_guide_generator import (
        read_input_file, generate_guide_content, build_docx_from_content,
    )
    source_text = read_input_file(Path("notebook.ipynb"))
    content = generate_guide_content(client, model="claude-sonnet-4-5",
                                      max_tokens=8192, source_text=source_text)
    build_docx_from_content(content, Path("guide.docx"))

Your Anthropic API key is read from the ANTHROPIC_API_KEY environment
variable; if it isn't set, the script prompts for it interactively (input is
hidden, like a password) rather than ever hard-coding it in source control.

--------------------------------------------------------------------------
RUNNING FROM VS CODE
--------------------------------------------------------------------------
This file is written to work both ways VS Code can launch a script:

1. Terminal, with arguments (recommended — full control):
   Open the Integrated Terminal (Ctrl+`) and run it like any CLI tool:

       python docx_guide_generator.py notebook.ipynb

2. The ▶ "Run Python File" button, or F5 (no arguments):
   VS Code runs `python docx_guide_generator.py` with no arguments in this
   mode, so the script falls back to asking for the input file path (and,
   as always, the API key and model) right there in the terminal panel.
   Just make sure the panel used is a real terminal and not the Debug
   Console — a `launch.json` with "console": "integratedTerminal" (see the
   .vscode/launch.json shipped alongside this script) takes care of that.

Two setup steps make repeated runs from VS Code smoother:

- Select the right interpreter: Ctrl+Shift+P -> "Python: Select Interpreter"
  -> the one where `pip install -r requirements.txt` was run.
- Optionally, create a `.env` file next to this script containing:

      ANTHROPIC_API_KEY=sk-ant-...

  If `python-dotenv` is installed, it's loaded automatically at startup, so
  you won't be prompted for the key each time. `.env` should never be
  committed to version control (add it to .gitignore).
"""

from __future__ import annotations

import argparse
import getpass
import json
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

# The anthropic and python-docx imports are wrapped so that a missing
# dependency produces one clear, actionable message instead of a raw
# traceback the first time someone runs this without `pip install -r
# requirements.txt`.
try:
    import anthropic
except ImportError:  # pragma: no cover - exercised only when the dep is missing
    sys.exit(
        "Missing dependency 'anthropic'. Install it with:\n"
        "    pip install -r requirements.txt"
    )

try:
    from docx import Document
    from docx.document import Document as DocumentObject
    from docx.enum.table import WD_TABLE_ALIGNMENT
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    from docx.shared import Cm, Pt, RGBColor
    from docx.table import _Cell
    from docx.text.paragraph import Paragraph
except ImportError:  # pragma: no cover - exercised only when the dep is missing
    sys.exit(
        "Missing dependency 'python-docx'. Install it with:\n"
        "    pip install -r requirements.txt"
    )

# python-dotenv is OPTIONAL: if it's installed and a `.env` file sits next to
# this script (or in the current working directory), ANTHROPIC_API_KEY can
# live there instead of being exported in the shell — the usual convenience
# for running a script from VS Code's Run button rather than a terminal.
# Nothing breaks if the package isn't installed or no .env file exists.
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


# ==========================================================================
# 1. CONFIGURATION: models, token limits, visual design system
# ==========================================================================

# A curated list offered in the interactive picker. Anthropic ships new
# models periodically, so the list also always offers a "type your own"
# escape hatch (see `select_model`) rather than ever blocking on a stale list.
AVAILABLE_MODELS: list[str] = [
    "claude-opus-4-5",
    "claude-sonnet-4-5",
    "claude-haiku-4-5-20251001",
    "claude-3-5-sonnet-20241022",
    "claude-3-opus-20240229",
    "claude-3-haiku-20240307",
]
DEFAULT_MODEL = "claude-sonnet-4-5"

# Why 8192 and not, say, 2048: the guide is returned as ONE JSON document
# containing every section, table and prompt example. Unlike prose, a
# truncated JSON response isn't just "cut short" — it's invalid JSON that
# fails to parse at all, so the whole run is lost rather than degraded.
# 8192 output tokens comfortably fits a full multi-section guide; raise it
# further (e.g. 16000) for very long source notebooks via --max-tokens.
DEFAULT_MAX_TOKENS = 8192


class Palette:
    """Hex colors shared by every visual element in the document.

    Centralizing them here is what makes the output look like a designed
    system rather than an assortment of ad hoc choices: change a value once
    and every table, callout and heading that uses it updates together.
    """

    ROSE = "C97B63"
    ROSE_DARK = "B05F49"
    ROSE_LIGHT = "F3E4DE"
    ROSE_LIGHTER = "FBF3EE"
    SAGE = "7C9473"
    SAGE_LIGHT = "E8EEE6"
    CHARCOAL = "4A4540"
    GRAY = "7A736C"
    GRAY_LIGHT = "F7F4F1"
    BORDER = "E3DAD2"
    WHITE = "FFFFFF"


FONT_HEADING = "Cambria"
FONT_BODY = "Calibri"
FONT_MONO = "Consolas"


# ==========================================================================
# 2. CONTENT SCHEMA: the JSON "contract" between Claude and the renderer
# ==========================================================================
#
# Claude never touches python-docx and never decides colors or fonts. It
# only ever produces data shaped like the dataclasses below. Keeping the
# schema narrow (a handful of block "types") is what makes the rendering
# step deterministic: every block type has exactly one visual treatment.

@dataclass
class Block:
    """One piece of content inside a section.

    Only the fields relevant to `type` are populated; the rest stay None.
    This is intentionally a single flat class (rather than a subclass per
    type) because the content arrives as loosely-typed JSON — validating
    and reporting a wrong/missing field is far simpler against one shape.
    """

    type: str  # one of: paragraph | subheading | bullet_list | numbered_list
    #             | callout | table | prompt_card
    text: Optional[str] = None
    title: Optional[str] = None
    style: Optional[str] = None  # callout accent: "rose" (default) or "sage"
    items: Optional[list[str]] = None
    headers: Optional[list[str]] = None
    rows: Optional[list[list[str]]] = None
    label: Optional[str] = None


@dataclass
class Section:
    heading: str  # e.g. "1. Introducción" — numbering is Claude's job,
    #                so it can match however many sections it decided to write.
    blocks: list[Block] = field(default_factory=list)


@dataclass
class CoverInfo:
    kicker: str  # small label above the title, e.g. "GUIÓN DE PRÁCTICA"
    title: str
    subtitle: str
    degree_line: str
    course_line: str
    university_line: str
    credit_line: str


@dataclass
class GuideContent:
    cover: CoverInfo
    sections: list[Section] = field(default_factory=list)


class ContentValidationError(ValueError):
    """Raised when Claude's JSON doesn't match the expected schema.

    Kept as its own exception type (rather than a bare ValueError) so
    callers can catch schema problems specifically and, e.g., decide to
    retry with a stricter reminder appended to the prompt.
    """


class GuideGenerationError(RuntimeError):
    """Raised for any Anthropic API-level failure (auth, rate limit,
    connection, truncated response).

    Library callers of `generate_guide_content` get a normal Python
    exception to catch — never a process-killing `sys.exit()` buried
    inside a function they called. Only `main()` (the CLI entry point)
    is allowed to turn errors into `sys.exit()` calls.
    """


_VALID_BLOCK_TYPES = {
    "paragraph", "subheading", "bullet_list", "numbered_list",
    "callout", "table", "prompt_card",
}


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ContentValidationError(message)


def content_from_json(data: dict[str, Any]) -> GuideContent:
    """Validate and convert raw JSON (as returned by Claude) into `GuideContent`.

    Deliberately strict: it's much easier to fix a clear "missing field X"
    error now than to debug a mysteriously blank paragraph in the final
    .docx later.
    """
    _require("cover" in data, "JSON is missing the top-level 'cover' object.")
    _require("sections" in data, "JSON is missing the top-level 'sections' list.")

    cover_raw = data["cover"]
    for key in ("kicker", "title", "subtitle", "degree_line", "course_line",
                "university_line", "credit_line"):
        _require(key in cover_raw, f"'cover' is missing required field '{key}'.")
    cover = CoverInfo(**{k: str(cover_raw[k]) for k in (
        "kicker", "title", "subtitle", "degree_line", "course_line",
        "university_line", "credit_line",
    )})

    sections: list[Section] = []
    for i, sec_raw in enumerate(data["sections"]):
        _require("heading" in sec_raw, f"sections[{i}] is missing 'heading'.")
        _require("blocks" in sec_raw, f"sections[{i}] is missing 'blocks'.")
        blocks: list[Block] = []
        for j, blk_raw in enumerate(sec_raw["blocks"]):
            where = f"sections[{i}].blocks[{j}]"
            _require("type" in blk_raw, f"{where} is missing 'type'.")
            btype = blk_raw["type"]
            _require(
                btype in _VALID_BLOCK_TYPES,
                f"{where} has unknown type '{btype}'. Expected one of: "
                f"{sorted(_VALID_BLOCK_TYPES)}.",
            )
            if btype in ("paragraph", "subheading", "prompt_card"):
                _require("text" in blk_raw, f"{where} (type={btype}) is missing 'text'.")
            if btype in ("bullet_list", "numbered_list"):
                _require("items" in blk_raw, f"{where} (type={btype}) is missing 'items'.")
            if btype == "callout":
                _require("title" in blk_raw and "text" in blk_raw,
                          f"{where} (type=callout) needs both 'title' and 'text'.")
            if btype == "table":
                _require("headers" in blk_raw and "rows" in blk_raw,
                          f"{where} (type=table) needs both 'headers' and 'rows'.")
            blocks.append(Block(
                type=btype,
                text=blk_raw.get("text"),
                title=blk_raw.get("title"),
                style=blk_raw.get("style"),
                items=blk_raw.get("items"),
                headers=blk_raw.get("headers"),
                rows=blk_raw.get("rows"),
                label=blk_raw.get("label"),
            ))
        sections.append(Section(heading=sec_raw["heading"], blocks=blocks))

    return GuideContent(cover=cover, sections=sections)


# ==========================================================================
# 3. INPUT HANDLING: reading the source file
# ==========================================================================

def _flatten_notebook(notebook_json: dict[str, Any]) -> str:
    """Render a .ipynb's cells as a plain-text transcript.

    Claude reads this the same way a person skimming the notebook would:
    markdown cells as prose, code cells clearly marked as code, in order.
    Cell outputs are intentionally skipped — they're execution artifacts,
    not part of the notebook's designed content.
    """
    lines: list[str] = []
    for idx, cell in enumerate(notebook_json.get("cells", [])):
        source = cell.get("source", "")
        text = "".join(source) if isinstance(source, list) else str(source)
        cell_type = cell.get("cell_type", "raw")
        lines.append(f"\n--- Cell {idx} [{cell_type}] ---\n{text}")
    return "".join(lines)


def read_input_file(path: Path) -> str:
    """Read a source file into plain text, with notebook-aware handling.

    Args:
        path: Path to a .ipynb notebook or any plain-text/Markdown file.

    Returns:
        The file's content as a single string, ready to hand to Claude.

    Raises:
        FileNotFoundError: if `path` doesn't exist.
        ValueError: if a .ipynb file isn't valid JSON.
    """
    if not path.exists():
        raise FileNotFoundError(f"Input file not found: {path}")

    raw = path.read_text(encoding="utf-8", errors="replace")

    if path.suffix.lower() == ".ipynb":
        try:
            notebook_json = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError(f"'{path}' has a .ipynb extension but isn't valid JSON: {exc}") from exc
        return _flatten_notebook(notebook_json)

    return raw


# ==========================================================================
# 4. CLAUDE INTEGRATION: source text -> structured guide content
# ==========================================================================

SYSTEM_PROMPT = """\
Eres un diseñador instruccional experto, especializado en crear guiones de \
práctica ("practice guides") en español de España para estudiantes de un \
grado universitario de Gestión, Tecnología y Moda, con conocimientos básicos \
de Python y Google Colab. No son estudiantes de informática: las \
instrucciones deben ser claras, no intimidantes y con foco en la aplicación \
práctica.

Vas a recibir el contenido de un cuaderno de Google Colab (o un documento \
similar). Tu tarea es analizarlo y devolver EXCLUSIVAMENTE un objeto JSON \
(sin bloques de código Markdown, sin texto antes o después) que describe el \
contenido completo de un guión de práctica sobre ese cuaderno, siguiendo \
exactamente el esquema indicado más abajo.

Estructura de contenido que debe seguir el guión (adapta los títulos \
exactos y el número de secciones a lo que tenga sentido para el cuaderno \
recibido, pero manteniendo este orden y espíritu):

1. Introducción — qué hace el cuaderno y cómo está organizado.
2. Objetivos de la práctica.
3. Requisitos previos (cuentas, claves de API, cómo guardarlas en Colab).
4. Visión general del cuaderno — un resumen sección por sección (usa \
   bloques "subheading" para cada sección del cuaderno).
5. Guía paso a paso para la primera ejecución (usa "numbered_list").
6. Modificar parámetros sencillos — una tabla con columnas Parámetro / \
   Dónde está / Qué controla / Efecto visible, seguida de experimentos \
   guiados con subheadings.
7. Experimentar con prompts o entradas propias — incluye una checklist \
   (bullet_list) de buenas prácticas y 3-5 ejemplos listos para copiar y \
   pegar, usando bloques "prompt_card".
8. Consejos para observar y comparar resultados.
9. (Si el cuaderno genera contenido sensible — imágenes de personas, datos \
   personales, etc. — incluye una sección de buen uso y consideraciones \
   éticas; si no aplica, omítela.)
10. Actividades de ampliación (opcional).
11. Glosario básico (tabla Término / Qué significa).
12. Solución de problemas comunes (usa subheadings + paragraph).
13. Checklist de entrega (bullet_list).

Extrae del propio cuaderno los datos reales para la portada (nombre de la \
asignatura, grado, universidad, autor, licencia) cuando estén presentes; si \
falta algún dato, usa un valor genérico razonable en vez de inventar datos \
falsos con apariencia de reales.

ESQUEMA JSON EXACTO A DEVOLVER:
{
  "cover": {
    "kicker": "GUIÓN DE PRÁCTICA",
    "title": "Título principal del guión",
    "subtitle": "Subtítulo breve en cursiva",
    "degree_line": "Grado en ...",
    "course_line": "Asignatura: ...",
    "university_line": "Universidad ...",
    "credit_line": "Material elaborado a partir de ... — Licencia ..."
  },
  "sections": [
    {
      "heading": "1. Introducción",
      "blocks": [
        {"type": "paragraph", "text": "Texto normal. Usa **negrita** para resaltar términos clave."},
        {"type": "subheading", "text": "Un subtítulo dentro de la sección"},
        {"type": "bullet_list", "items": ["Primer punto", "Segundo punto"]},
        {"type": "numbered_list", "items": ["Primer paso", "Segundo paso"]},
        {"type": "callout", "title": "Título del aviso", "text": "Texto del aviso.", "style": "sage"},
        {"type": "table", "headers": ["Col A", "Col B"], "rows": [["a1", "b1"], ["a2", "b2"]]},
        {"type": "prompt_card", "label": "idea_inicial =", "text": "Texto listo para copiar y pegar."}
      ]
    }
  ]
}

Reglas importantes:
- Devuelve SOLO el objeto JSON, empezando por "{" y terminando por "}". Sin \
  explicaciones, sin comentarios, sin bloques ```json.
- Usa "**texto**" dentro de cualquier "text" quieras que aparezca en negrita; \
  el renderizador lo interpretará automáticamente.
- El campo "style" de "callout" solo admite "rose" (aviso/consejo) o "sage" \
  (nota informativa/ética). Si lo omites, se usa "rose".
- Todas las tablas deben tener el mismo número de columnas en cada fila que \
  en "headers".
- Escribe todo el contenido en español de España, con tono cercano, \
  profesional y nunca intimidante.
"""


def _extract_json_object(raw_text: str) -> str:
    """Best-effort extraction of a JSON object from Claude's raw response.

    Claude is instructed to return bare JSON, but this defensively strips a
    ```json ... ``` fence if one slips in, so a minor formatting slip
    doesn't fail the whole run.
    """
    text = raw_text.strip()
    fence_match = re.match(r"^```(?:json)?\s*(.*)```\s*$", text, re.DOTALL)
    if fence_match:
        text = fence_match.group(1).strip()
    return text


def generate_guide_content(
    client: anthropic.Anthropic,
    model: str,
    max_tokens: int,
    source_text: str,
) -> GuideContent:
    """Ask Claude to analyze `source_text` and return structured guide content.

    Args:
        client: An initialized Anthropic client.
        model: Model ID to use (see AVAILABLE_MODELS).
        max_tokens: Output token ceiling — see DEFAULT_MAX_TOKENS for why
            this needs to be generous for a JSON-shaped response.
        source_text: The notebook/document content to analyze.

    Returns:
        A validated GuideContent object ready to render.

    Raises:
        GuideGenerationError: on any API-level failure (auth, rate limit,
            connection, or a response truncated by the max_tokens ceiling).
        ContentValidationError: if Claude's JSON doesn't match the schema.
        json.JSONDecodeError: if Claude's response isn't valid JSON at all.
    """
    user_message = (
        "Analiza el siguiente cuaderno/documento y genera el JSON del "
        "guión de práctica tal y como se describe en tus instrucciones.\n\n"
        "--- CONTENIDO DEL CUADERNO ---\n"
        f"{source_text}"
    )

    try:
        response = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_message}],
        )
    except anthropic.AuthenticationError as exc:
        raise GuideGenerationError(
            "Authentication failed: your Anthropic API key was rejected. "
            "Check ANTHROPIC_API_KEY (or the key you typed) and try again."
        ) from exc
    except anthropic.RateLimitError as exc:
        raise GuideGenerationError(
            "Rate limit reached on your Anthropic account. "
            "Wait a moment and retry, or check your plan's rate limits."
        ) from exc
    except anthropic.APIConnectionError as exc:
        raise GuideGenerationError(f"Could not reach the Anthropic API (network issue): {exc}") from exc
    except anthropic.APIStatusError as exc:
        raise GuideGenerationError(
            f"Anthropic API returned an error (status {exc.status_code}): {exc.message}"
        ) from exc
    except anthropic.AnthropicError as exc:  # catch-all for the SDK's own errors
        raise GuideGenerationError(f"Unexpected Anthropic SDK error: {exc}") from exc

    if response.stop_reason == "max_tokens":
        raise GuideGenerationError(
            "Claude's response was cut off because it hit the max_tokens "
            f"limit ({max_tokens}). Retry with a higher max_tokens value "
            "(e.g. double it) — a truncated JSON response cannot be parsed."
        )

    raw_text = response.content[0].text
    json_text = _extract_json_object(raw_text)

    try:
        data = json.loads(json_text)
    except json.JSONDecodeError as exc:
        preview = json_text[:500] + ("..." if len(json_text) > 500 else "")
        raise json.JSONDecodeError(
            f"Claude's response was not valid JSON ({exc.msg}). "
            f"First 500 characters of the response:\n{preview}",
            exc.doc, exc.pos,
        ) from exc

    return content_from_json(data)


# ==========================================================================
# 5. LOW-LEVEL DOCX HELPERS (python-docx doesn't expose these directly)
# ==========================================================================
#
# python-docx's high-level API doesn't cover cell shading, custom cell
# borders, page-number fields or a TOC field — all of these require
# reaching into the underlying OOXML. Each helper below does exactly one
# such thing, with the raw XML kept as close as possible to what Word
# itself writes, so the resulting .docx opens cleanly in Word, LibreOffice
# and Google Docs alike.

def set_run_font(run, name: str) -> None:
    """Set a run's font for every OOXML script slot (ascii/eastAsia/etc.).

    Setting only `run.font.name` leaves east-Asian and complex-script slots
    pointing at the theme default, which some renderers fall back to —
    setting all four slots is the standard fix.
    """
    run.font.name = name
    rpr = run._element.get_or_add_rPr()
    rFonts = rpr.find(qn("w:rFonts"))
    if rFonts is None:
        rFonts = OxmlElement("w:rFonts")
        rpr.append(rFonts)
    for attr in ("w:ascii", "w:hAnsi", "w:eastAsia", "w:cs"):
        rFonts.set(qn(attr), name)


def set_cell_background(cell: _Cell, hex_color: str) -> None:
    """Shade a table cell's background (python-docx has no shading API)."""
    tcPr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), hex_color)
    tcPr.append(shd)


def set_cell_borders(cell: _Cell, **sides: tuple[str, int, str]) -> None:
    """Set per-side borders on a table cell.

    Each keyword is one of top/bottom/left/right/insideH/insideV and maps
    to a (style, size_eighths_of_a_point, hex_color) tuple, e.g.:
        set_cell_borders(cell, left=("single", 28, Palette.ROSE))
    """
    tcPr = cell._tc.get_or_add_tcPr()
    borders = OxmlElement("w:tcBorders")
    for side, (style, size, color) in sides.items():
        edge = OxmlElement(f"w:{side}")
        edge.set(qn("w:val"), style)
        edge.set(qn("w:sz"), str(size))
        edge.set(qn("w:space"), "0")
        edge.set(qn("w:color"), color)
        borders.append(edge)
    tcPr.append(borders)


def add_page_number_field(paragraph: Paragraph) -> None:
    """Insert a live "current page number" field into a paragraph.

    This is the same three-part fldChar/instrText/fldChar structure Word
    itself writes for Insert > Page Number; python-docx has no shortcut
    for it.
    """
    run = paragraph.add_run()
    fld_begin = OxmlElement("w:fldChar")
    fld_begin.set(qn("w:fldCharType"), "begin")
    instr = OxmlElement("w:instrText")
    instr.set(qn("xml:space"), "preserve")
    instr.text = "PAGE"
    fld_end = OxmlElement("w:fldChar")
    fld_end.set(qn("w:fldCharType"), "end")
    run._r.append(fld_begin)
    run._r.append(instr)
    run._r.append(fld_end)


def add_toc_field(document: DocumentObject) -> None:
    """Insert a Word "Table of Contents" field (heading levels 1-3).

    Word populates this the first time the document is opened and the
    field is updated (F9), exactly like a TOC inserted by hand via
    References > Table of Contents. Until then, Word shows a placeholder —
    which is why we also print a short instruction paragraph above it.
    """
    paragraph = document.add_paragraph()
    run = paragraph.add_run()

    fld_begin = OxmlElement("w:fldChar")
    fld_begin.set(qn("w:fldCharType"), "begin")

    instr = OxmlElement("w:instrText")
    instr.set(qn("xml:space"), "preserve")
    instr.text = 'TOC \\o "1-3" \\h \\z \\u'

    fld_separate = OxmlElement("w:fldChar")
    fld_separate.set(qn("w:fldCharType"), "separate")

    placeholder = OxmlElement("w:t")
    placeholder.text = "Actualiza este campo (clic derecho → Actualizar campo) para ver el índice."

    fld_end = OxmlElement("w:fldChar")
    fld_end.set(qn("w:fldCharType"), "end")

    run._r.append(fld_begin)
    run._r.append(instr)
    run._r.append(fld_separate)
    run._r.append(placeholder)
    run._r.append(fld_end)


def add_page_break(document: DocumentObject) -> None:
    document.add_page_break()


# ==========================================================================
# 6. THE DOCX WRITER: renders GuideContent into a styled .docx
# ==========================================================================

_BOLD_PATTERN = re.compile(r"\*\*(.+?)\*\*")


class GuideDocxWriter:
    """Builds one .docx document from a `GuideContent` object.

    All formatting decisions (colors, fonts, spacing, border weights) live
    in this class's methods, in one place, so the whole document stays
    visually consistent by construction rather than by convention.
    """

    def __init__(self) -> None:
        self.document: DocumentObject = Document()
        self._setup_page_and_styles()

    # -- setup -------------------------------------------------------

    def _setup_page_and_styles(self) -> None:
        section = self.document.sections[0]
        section.page_width = Cm(21.0)   # A4
        section.page_height = Cm(29.7)
        section.top_margin = Cm(1.9)
        section.bottom_margin = Cm(1.9)
        section.left_margin = Cm(2.1)
        section.right_margin = Cm(2.1)
        # A blank first-page header/footer keeps the cover page clean while
        # the running header/footer still applies from page 2 onward.
        section.different_first_page_header_footer = True

        normal = self.document.styles["Normal"]
        normal.font.name = FONT_BODY
        normal.font.size = Pt(11)
        normal.font.color.rgb = RGBColor.from_string(Palette.CHARCOAL)

    def add_running_header_and_footer(self, running_title: str) -> None:
        """Set the header/footer used from page 2 onward (cover stays blank)."""
        section = self.document.sections[0]

        header_para = section.header.paragraphs[0]
        header_para.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        run = header_para.add_run(running_title)
        set_run_font(run, FONT_BODY)
        run.font.size = Pt(8)
        run.font.italic = True
        run.font.color.rgb = RGBColor.from_string(Palette.GRAY)

        footer_para = section.footer.paragraphs[0]
        footer_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = footer_para.add_run("Página ")
        set_run_font(run, FONT_BODY)
        run.font.size = Pt(8)
        run.font.color.rgb = RGBColor.from_string(Palette.GRAY)
        add_page_number_field(footer_para)

        # Leave the first-page header/footer empty (cover page).
        _ = section.first_page_header.paragraphs[0]
        _ = section.first_page_footer.paragraphs[0]

    # -- inline formatting --------------------------------------------

    def _add_runs_with_bold(
        self, paragraph: Paragraph, text: str, *,
        size: int = 11, color: str = Palette.CHARCOAL, font: str = FONT_BODY,
    ) -> None:
        """Add `text` to `paragraph`, turning **bold** markers into bold runs."""
        pos = 0
        for match in _BOLD_PATTERN.finditer(text):
            if match.start() > pos:
                run = paragraph.add_run(text[pos:match.start()])
                set_run_font(run, font)
                run.font.size = Pt(size)
                run.font.color.rgb = RGBColor.from_string(color)
            run = paragraph.add_run(match.group(1))
            set_run_font(run, font)
            run.font.size = Pt(size)
            run.font.bold = True
            run.font.color.rgb = RGBColor.from_string(color)
            pos = match.end()
        if pos < len(text):
            run = paragraph.add_run(text[pos:])
            set_run_font(run, font)
            run.font.size = Pt(size)
            run.font.color.rgb = RGBColor.from_string(color)

    # -- cover page ----------------------------------------------------

    def add_cover(self, cover: CoverInfo) -> None:
        d = self.document

        def centered(text: str, *, size: int, color: str, bold: bool = False,
                     italic: bool = False, font: str = FONT_BODY,
                     space_before: int = 0, space_after: int = 6) -> None:
            p = d.add_paragraph()
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            p.paragraph_format.space_before = Pt(space_before)
            p.paragraph_format.space_after = Pt(space_after)
            run = p.add_run(text)
            set_run_font(run, font)
            run.font.size = Pt(size)
            run.font.bold = bold
            run.font.italic = italic
            run.font.color.rgb = RGBColor.from_string(color)

        # Vertical breathing room before the title block.
        for _ in range(4):
            d.add_paragraph()

        centered(cover.kicker, size=12, color=Palette.SAGE, bold=True, space_after=8)
        centered(cover.title, size=28, color=Palette.ROSE, bold=True,
                 font=FONT_HEADING, space_after=10)
        centered(cover.subtitle, size=14, color=Palette.CHARCOAL, italic=True,
                 font=FONT_HEADING, space_after=30)
        centered(cover.degree_line, size=12, color=Palette.CHARCOAL, bold=True, space_after=3)
        centered(cover.course_line, size=11, color=Palette.GRAY, space_after=3)
        centered(cover.university_line, size=11, color=Palette.GRAY, space_after=30)
        centered(cover.credit_line, size=9, color=Palette.GRAY)

        add_page_break(d)

    # -- table of contents ----------------------------------------------

    def add_table_of_contents(self) -> None:
        d = self.document
        self._add_heading(1, "Índice")
        note = d.add_paragraph()
        run = note.add_run(
            "Este índice se actualiza automáticamente en Word: haz clic "
            "derecho sobre él y elige “Actualizar campo” si aparece vacío."
        )
        set_run_font(run, FONT_BODY)
        run.font.size = Pt(9)
        run.font.italic = True
        run.font.color.rgb = RGBColor.from_string(Palette.GRAY)
        add_toc_field(d)
        add_page_break(d)

    # -- headings --------------------------------------------------------

    def _add_heading(self, level: int, text: str) -> None:
        """Add a heading that is BOTH visually styled AND a real Word
        heading style (Heading 1/2/3), which is what lets `add_toc_field`
        above pick it up automatically.
        """
        d = self.document
        style_name = {1: "Heading 1", 2: "Heading 2", 3: "Heading 3"}[level]
        paragraph = d.add_paragraph(style=style_name)
        paragraph.paragraph_format.space_before = Pt({1: 18, 2: 14, 3: 10}[level])
        paragraph.paragraph_format.space_after = Pt({1: 8, 2: 6, 3: 4}[level])
        run = paragraph.add_run(text)
        size = {1: 17, 2: 13, 3: 11}[level]
        color = {1: Palette.ROSE, 2: Palette.CHARCOAL, 3: Palette.ROSE_DARK}[level]
        set_run_font(run, FONT_HEADING)
        run.font.size = Pt(size)
        run.font.bold = True
        run.font.italic = (level == 3)
        run.font.color.rgb = RGBColor.from_string(color)
        if level == 1:
            self._add_bottom_border(paragraph, Palette.ROSE)

    @staticmethod
    def _add_bottom_border(paragraph: Paragraph, color: str) -> None:
        pPr = paragraph._p.get_or_add_pPr()
        pBdr = OxmlElement("w:pBdr")
        bottom = OxmlElement("w:bottom")
        bottom.set(qn("w:val"), "single")
        bottom.set(qn("w:sz"), "8")
        bottom.set(qn("w:space"), "4")
        bottom.set(qn("w:color"), color)
        pBdr.append(bottom)
        pPr.append(pBdr)

    # -- section dispatch --------------------------------------------------

    def add_section(self, section: Section) -> None:
        self._add_heading(1, section.heading)
        for block in section.blocks:
            self._add_block(block)
        add_page_break(self.document)

    def _add_block(self, block: Block) -> None:
        dispatch = {
            "paragraph": self._add_paragraph_block,
            "subheading": self._add_subheading_block,
            "bullet_list": self._add_bullet_list_block,
            "numbered_list": self._add_numbered_list_block,
            "callout": self._add_callout_block,
            "table": self._add_table_block,
            "prompt_card": self._add_prompt_card_block,
        }
        dispatch[block.type](block)

    # -- individual block renderers -----------------------------------

    def _add_paragraph_block(self, block: Block) -> None:
        p = self.document.add_paragraph()
        p.paragraph_format.space_after = Pt(8)
        p.paragraph_format.line_spacing = 1.15
        self._add_runs_with_bold(p, block.text or "")

    def _add_subheading_block(self, block: Block) -> None:
        self._add_heading(3, block.text or "")

    def _add_bullet_list_block(self, block: Block) -> None:
        for item in block.items or []:
            p = self.document.add_paragraph()
            p.paragraph_format.left_indent = Cm(0.6)
            p.paragraph_format.first_line_indent = Cm(-0.3)
            p.paragraph_format.space_after = Pt(4)
            bullet_run = p.add_run("•  ")
            set_run_font(bullet_run, FONT_BODY)
            bullet_run.font.color.rgb = RGBColor.from_string(Palette.ROSE)
            bullet_run.font.bold = True
            self._add_runs_with_bold(p, item)

    def _add_numbered_list_block(self, block: Block) -> None:
        # Numbers are written as literal text (rather than Word's built-in
        # numbering) so a document with several numbered lists never risks
        # one list silently continuing another's count.
        for i, item in enumerate(block.items or [], start=1):
            p = self.document.add_paragraph()
            p.paragraph_format.left_indent = Cm(0.7)
            p.paragraph_format.first_line_indent = Cm(-0.7)
            p.paragraph_format.space_after = Pt(6)
            number_run = p.add_run(f"{i}.  ")
            set_run_font(number_run, FONT_BODY)
            number_run.font.bold = True
            number_run.font.color.rgb = RGBColor.from_string(Palette.ROSE_DARK)
            self._add_runs_with_bold(p, item)

    def _add_callout_block(self, block: Block) -> None:
        accent = Palette.SAGE if block.style == "sage" else Palette.ROSE
        fill = Palette.SAGE_LIGHT if block.style == "sage" else Palette.ROSE_LIGHTER
        title_color = "5C7554" if block.style == "sage" else Palette.ROSE_DARK

        table = self.document.add_table(rows=1, cols=1)
        table.autofit = True
        cell = table.rows[0].cells[0]
        set_cell_background(cell, fill)
        set_cell_borders(
            cell,
            top=("single", 2, fill), bottom=("single", 2, fill), right=("single", 2, fill),
            left=("single", 28, accent),
        )
        cell.margin_top = Cm(0.2)
        cell.margin_bottom = Cm(0.2)
        cell.margin_left = Cm(0.3)
        cell.margin_right = Cm(0.3)

        title_p = cell.paragraphs[0]
        title_p.paragraph_format.space_after = Pt(4)
        run = title_p.add_run(block.title or "")
        set_run_font(run, FONT_HEADING)
        run.font.bold = True
        run.font.size = Pt(11)
        run.font.color.rgb = RGBColor.from_string(title_color)

        body_p = cell.add_paragraph()
        body_p.paragraph_format.line_spacing = 1.15
        self._add_runs_with_bold(body_p, block.text or "")

        # A blank spacer paragraph after the table keeps the next block
        # from crowding the callout's bottom edge.
        self.document.add_paragraph()

    def _add_table_block(self, block: Block) -> None:
        headers = block.headers or []
        rows = block.rows or []
        n_cols = len(headers)

        table = self.document.add_table(rows=1, cols=n_cols)
        table.alignment = WD_TABLE_ALIGNMENT.CENTER

        header_cells = table.rows[0].cells
        for cell, text in zip(header_cells, headers):
            set_cell_background(cell, Palette.ROSE)
            set_cell_borders(
                cell,
                top=("single", 4, Palette.BORDER), bottom=("single", 4, Palette.BORDER),
                left=("single", 4, Palette.BORDER), right=("single", 4, Palette.BORDER),
            )
            p = cell.paragraphs[0]
            run = p.add_run(text)
            set_run_font(run, FONT_BODY)
            run.font.bold = True
            run.font.size = Pt(10)
            run.font.color.rgb = RGBColor.from_string(Palette.WHITE)

        for row_index, row_values in enumerate(rows):
            row_cells = table.add_row().cells
            fill = Palette.WHITE if row_index % 2 == 0 else Palette.GRAY_LIGHT
            for cell, text in zip(row_cells, row_values):
                set_cell_background(cell, fill)
                set_cell_borders(
                    cell,
                    top=("single", 4, Palette.BORDER), bottom=("single", 4, Palette.BORDER),
                    left=("single", 4, Palette.BORDER), right=("single", 4, Palette.BORDER),
                )
                p = cell.paragraphs[0]
                run = p.add_run(text)
                set_run_font(run, FONT_BODY)
                run.font.size = Pt(10)
                run.font.color.rgb = RGBColor.from_string(Palette.CHARCOAL)

        self.document.add_paragraph()  # breathing room after the table

    def _add_prompt_card_block(self, block: Block) -> None:
        table = self.document.add_table(rows=1, cols=1)
        cell = table.rows[0].cells[0]
        set_cell_background(cell, Palette.GRAY_LIGHT)
        set_cell_borders(
            cell,
            top=("single", 2, Palette.GRAY_LIGHT), bottom=("single", 2, Palette.GRAY_LIGHT),
            right=("single", 2, Palette.GRAY_LIGHT), left=("single", 28, Palette.ROSE),
        )
        cell.margin_top = Cm(0.2)
        cell.margin_bottom = Cm(0.2)
        cell.margin_left = Cm(0.3)
        cell.margin_right = Cm(0.3)

        label_p = cell.paragraphs[0]
        label_p.paragraph_format.space_after = Pt(4)
        run = label_p.add_run(block.label or "")
        set_run_font(run, FONT_BODY)
        run.font.bold = True
        run.font.size = Pt(9)
        run.font.color.rgb = RGBColor.from_string(Palette.ROSE_DARK)

        body_p = cell.add_paragraph()
        body_p.paragraph_format.line_spacing = 1.1
        run = body_p.add_run(block.text or "")
        set_run_font(run, FONT_MONO)
        run.font.size = Pt(9)
        run.font.color.rgb = RGBColor.from_string(Palette.CHARCOAL)

        self.document.add_paragraph()

    # -- output ------------------------------------------------------------

    def save(self, path: Path) -> None:
        self.document.save(str(path))


def build_docx_from_content(content: GuideContent, output_path: Path) -> None:
    """Render a validated `GuideContent` into a .docx file at `output_path`.

    This is the single deterministic step of the pipeline: given the same
    `content`, it always produces the same document, byte-for-byte
    formatting choices included.
    """
    writer = GuideDocxWriter()
    writer.add_cover(content.cover)
    writer.add_running_header_and_footer(content.cover.title)
    writer.add_table_of_contents()
    for section in content.sections:
        writer.add_section(section)
    writer.save(output_path)


# ==========================================================================
# 7. CLI / API-KEY / MODEL SELECTION
# ==========================================================================

def get_api_key(cli_key: Optional[str]) -> str:
    """Resolve the Anthropic API key from (in order): --api-key, the
    ANTHROPIC_API_KEY environment variable, or an interactive hidden prompt.
    """
    if cli_key:
        return cli_key
    env_key = os.environ.get("ANTHROPIC_API_KEY")
    if env_key:
        return env_key
    print("ANTHROPIC_API_KEY is not set.")
    try:
        key = getpass.getpass("Enter your Anthropic API key (input hidden): ").strip()
    except EOFError:
        sys.exit(
            "No se pudo leer la API key de forma interactiva.\n"
            "Define la variable de entorno ANTHROPIC_API_KEY, crea un "
            "archivo .env (ver .env.example), o pásala con --api-key."
        )
    if not key:
        sys.exit("No API key provided. Aborting.")
    return key


def select_model(cli_model: Optional[str]) -> str:
    """Resolve the model to use, prompting interactively if not given on the CLI.

    If stdin isn't interactive (EOF right away), this falls back to
    DEFAULT_MODEL instead of crashing — picking a model is a convenience
    prompt, not something that should block a run the way a missing file
    or API key does.
    """
    if cli_model:
        return cli_model

    print("\nAvailable Claude models:")
    for i, name in enumerate(AVAILABLE_MODELS, start=1):
        print(f"  {i}. {name}")
    print(f"  {len(AVAILABLE_MODELS) + 1}. Enter a different model ID")

    try:
        choice = input(f"Choose a model [default: {DEFAULT_MODEL}]: ").strip()
    except EOFError:
        print(f"(sin entrada interactiva; usando el modelo por defecto: {DEFAULT_MODEL})")
        return DEFAULT_MODEL
    if not choice:
        return DEFAULT_MODEL
    if choice.isdigit():
        index = int(choice)
        if 1 <= index <= len(AVAILABLE_MODELS):
            return AVAILABLE_MODELS[index - 1]
        if index == len(AVAILABLE_MODELS) + 1:
            try:
                custom = input("Enter the model ID: ").strip()
            except EOFError:
                print(f"(sin entrada interactiva; usando el modelo por defecto: {DEFAULT_MODEL})")
                return DEFAULT_MODEL
            if custom:
                return custom
    # Anything else typed directly is treated as a literal model ID —
    # this is the escape hatch for models newer than AVAILABLE_MODELS.
    return choice


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="docx_guide_generator.py",
        description=(
            "Generate a styled Word practice guide from a notebook or "
            "text file, using Claude to analyze the content."
        ),
    )
    parser.add_argument(
        "input_file", type=Path, nargs="?", default=None,
        help=(
            "Path to the source file (.ipynb notebook, .md, or .txt). "
            "If omitted, you'll be prompted for it interactively — this is "
            "what happens automatically when you run this file from VS "
            "Code's ▶ Run button, which passes no arguments."
        ),
    )
    parser.add_argument(
        "-o", "--output", type=Path, default=None,
        help="Output .docx path. Defaults to <input_file stem>_guia.docx.",
    )
    parser.add_argument(
        "--model", default=None,
        help=f"Claude model ID to use. If omitted, prompts interactively. "
             f"Default when pressing Enter: {DEFAULT_MODEL}.",
    )
    parser.add_argument(
        "--max-tokens", type=int, default=DEFAULT_MAX_TOKENS,
        help=f"Max output tokens for Claude's response (default: {DEFAULT_MAX_TOKENS}). "
             "Raise this for very long source notebooks.",
    )
    parser.add_argument(
        "--api-key", default=None,
        help="Anthropic API key. If omitted, uses ANTHROPIC_API_KEY or prompts interactively.",
    )
    return parser


def resolve_input_path(cli_path: Optional[Path]) -> Path:
    """Resolve the input file path, prompting interactively if it wasn't
    given on the command line.

    This is what makes the script "just work" when launched from VS Code's
    ▶ Run button (or F5), which runs `python docx_guide_generator.py` with
    no arguments at all — without this fallback, argparse would reject a
    missing positional argument before the user ever sees a prompt.
    """
    if cli_path is not None:
        return cli_path.expanduser()

    print("No se indicó un archivo de entrada como argumento.")
    try:
        typed = input(
            "Ruta del archivo de entrada (cuaderno .ipynb, .md o .txt): "
        ).strip()
    except EOFError:
        # Happens if stdin isn't interactive at all (e.g. piped input with
        # nothing left to read) — fail with guidance instead of a traceback.
        sys.exit(
            "No se pudo leer una ruta de archivo de forma interactiva.\n"
            "Ejecuta el script pasando la ruta directamente, por ejemplo:\n"
            "    python docx_guide_generator.py ruta/al/archivo.ipynb"
        )
    if not typed:
        sys.exit("No se indicó ninguna ruta de archivo. Abortando.")
    # Strip optional quotes: VS Code / Explorer "Copy Path" sometimes
    # includes them when the path is pasted into a terminal prompt.
    typed = typed.strip('"').strip("'")
    return Path(typed).expanduser()


def main(argv: Optional[list[str]] = None) -> None:
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    input_path = resolve_input_path(args.input_file)
    if not input_path.exists():
        sys.exit(f"Input file not found: {input_path}")

    output_path = args.output or input_path.with_name(
        input_path.stem + "_guia.docx"
    )

    print(f"Reading '{input_path}'...")
    try:
        source_text = read_input_file(input_path)
    except (FileNotFoundError, ValueError) as exc:
        sys.exit(str(exc))

    api_key = get_api_key(args.api_key)
    model = select_model(args.model)
    client = anthropic.Anthropic(api_key=api_key)

    print(f"Sending content to Claude ({model})... this may take a moment.")
    try:
        content = generate_guide_content(
            client=client, model=model, max_tokens=args.max_tokens,
            source_text=source_text,
        )
    except (ContentValidationError, json.JSONDecodeError, GuideGenerationError) as exc:
        sys.exit(f"Claude's response could not be used: {exc}")

    print(f"Building '{output_path}'...")
    build_docx_from_content(content, output_path)
    print(f"Done. Guide saved to: {output_path}")


if __name__ == "__main__":
    main()
