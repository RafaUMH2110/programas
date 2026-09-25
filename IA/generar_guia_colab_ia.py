"""
================================================================================
 GENERADOR DE LA GUÍA "ACCESO A GOOGLE COLAB" (contenido generado vía API)
 Asignatura: Tecnología en Moda — Universidad Miguel Hernández de Elche (UMH)
================================================================================

Diferencia respecto a la versión anterior
------------------------------------------
En la versión anterior, todos los textos del documento estaban escritos a
mano dentro del propio script (funciones `construir_seccion_1`, `_2`, etc.).

En ESTA versión, el texto de la guía (portada, índice y las 7 secciones) se
solicita a un modelo de Anthropic a través de la API oficial, usando tu
propia API key. El modelo devuelve el contenido en un formato JSON muy
concreto (un "esquema" de bloques: párrafo, viñetas, nota, figura…) y el
programa recorre ese JSON para maquetar el documento Word exactamente con
el mismo diseño que la versión anterior (misma paleta de colores, mismas
4 ilustraciones, misma portada, mismo encabezado/pie con número de página).

Es decir: lo único que cambia es "quién escribe el texto" (antes estaba
fijo en el código, ahora lo genera Claude a través de la API); el motor
que maqueta el .docx es el mismo.

Cómo obtener y configurar tu API key
--------------------------------------
1. Crea una API key en la consola de Anthropic: https://console.anthropic.com
2. NUNCA escribas la key directamente en el código. Configúrala como
   variable de entorno:

   · En Windows (PowerShell):
         setx ANTHROPIC_API_KEY "tu-api-key-aqui"
         (cierra y vuelve a abrir la terminal/VSCode para que surta efecto)

   · En macOS / Linux (bash/zsh), añade a tu ~/.bashrc o ~/.zshrc:
         export ANTHROPIC_API_KEY="tu-api-key-aqui"

   · Alternativa cómoda en VSCode: crea un archivo ".env" (mismo directorio
     que este script) con la línea:
         ANTHROPIC_API_KEY=tu-api-key-aqui
     Este script lo carga automáticamente si tienes instalado python-dotenv.

Cómo ejecutarlo en VSCode
--------------------------
1. Instala las dependencias (una sola vez):
       pip install python-docx pillow anthropic python-dotenv
2. Comprueba que la variable ANTHROPIC_API_KEY está disponible (ver arriba).
3. Ejecuta este archivo con el botón "Run" de VSCode, o desde la terminal:
       python generar_guia_colab_ia.py
4. El documento final aparecerá en:
       ./salida/Guia_acceso_Google_Colab.docx

Estructura del código
----------------------
  PARTE 1 · Configuración general (rutas, paleta de colores, tipografía)
  PARTE 2 · Generación de las ilustraciones (Pillow) — SIN CAMBIOS
  PARTE 3 · Utilidades de bajo nivel para python-docx — SIN CAMBIOS
  PARTE 4 · Obtención del CONTENIDO a través de la API de Anthropic
            (definición del esquema JSON, prompt, llamada, validación)
  PARTE 5 · Renderizador genérico: recorre el JSON y construye el .docx
            reutilizando las funciones de maquetación (título, párrafo,
            viñeta, nota, figura…)
  PARTE 6 · Montaje del documento y punto de entrada (main)
================================================================================
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass

from PIL import Image, ImageDraw, ImageFont

from docx import Document
from docx.document import Document as DocumentObject
from docx.enum.section import WD_SECTION
from docx.enum.table import WD_ALIGN_VERTICAL
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor
from docx.table import Table, _Cell
from docx.text.paragraph import Paragraph

# El SDK de Anthropic y python-dotenv son opcionales de cara a poder LEER
# este archivo sin tenerlos instalados, pero son obligatorios para poder
# EJECUTARLO (se comprueba y se avisa con un mensaje claro si faltan).
try:
    from anthropic import Anthropic
except ImportError:  # pragma: no cover
    Anthropic = None

try:
    from dotenv import load_dotenv
    load_dotenv()  # carga variables definidas en un archivo .env, si existe
except ImportError:  # pragma: no cover
    pass


# ==============================================================================
# PARTE 1 · CONFIGURACIÓN GENERAL
# ==============================================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(BASE_DIR, "salida")
IMG_DIR = os.path.join(OUTPUT_DIR, "img")
DOCX_PATH = os.path.join(OUTPUT_DIR, "Guia_acceso_Google_Colab.docx")

# Modelo de Anthropic usado para generar el contenido del documento.
MODELO_ANTHROPIC = "claude-sonnet-5"

FONT_NAME = "Calibri"
FONT_MONO = "Consolas"


@dataclass(frozen=True)
class Paleta:
    navy: str = "1A2A44"
    navy_soft: str = "34496C"
    teal: str = "279594"
    teal_light: str = "D6F0EF"
    orange: str = "E9892F"
    orange_light: str = "FBEEDF"
    gray: str = "6B7480"
    gray_light: str = "E1E5E9"
    text: str = "212936"
    note_bg: str = "F2F8F7"


PALETA = Paleta()


def rgb(hex_color: str) -> RGBColor:
    """Convierte un color hexadecimal ('RRGGBB') a un objeto RGBColor."""
    return RGBColor.from_string(hex_color)


# ==============================================================================
# PARTE 2 · GENERACIÓN DE LAS ILUSTRACIONES (Pillow) — sin cambios respecto
# a la versión anterior: son mockups genéricos dibujados por código, no
# capturas reales de la interfaz de terceros.
# ==============================================================================

SS = 2
W, H = 1600, 1000


def _font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    nombre = "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"
    ruta = f"/usr/share/fonts/truetype/dejavu/{nombre}"
    try:
        return ImageFont.truetype(ruta, size)
    except OSError:
        return ImageFont.load_default()


def _lienzo() -> tuple[Image.Image, ImageDraw.ImageDraw]:
    img = Image.new("RGB", (W * SS, H * SS), (247, 249, 250))
    return img, ImageDraw.Draw(img)


def _guardar(img: Image.Image, nombre: str) -> None:
    img = img.resize((img.width // SS, img.height // SS), Image.LANCZOS)
    os.makedirs(IMG_DIR, exist_ok=True)
    img.save(os.path.join(IMG_DIR, f"{nombre}.png"))


def _color(hex_color: str) -> tuple[int, int, int]:
    return tuple(int(hex_color[i:i + 2], 16) for i in (0, 2, 4))


def _ventana_navegador(draw, x, y, w, h, url_texto: str) -> int:
    radio = 22 * SS
    draw.rounded_rectangle([x, y, x + w, y + h], radius=radio,
                            fill=(255, 255, 255), outline=_color(PALETA.gray_light),
                            width=2 * SS)
    barra_h = 84 * SS
    draw.rounded_rectangle([x, y, x + w, y + barra_h], radius=radio, fill=(238, 240, 243))
    draw.rectangle([x, y + barra_h - radio, x + w, y + barra_h], fill=(238, 240, 243))
    for i, c in enumerate([(233, 137, 47), (240, 200, 90), (120, 190, 150)]):
        cx = x + (40 + i * 34) * SS
        cy = y + barra_h // 2
        r = 10 * SS
        draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=c)
    bx0, bx1 = x + 170 * SS, x + w - 40 * SS
    by0, by1 = y + 20 * SS, y + barra_h - 20 * SS
    draw.rounded_rectangle([bx0, by0, bx1, by1], radius=18 * SS, fill=(255, 255, 255),
                            outline=_color(PALETA.gray_light), width=2 * SS)
    draw.text((bx0 + 24 * SS, (by0 + by1) // 2), url_texto, font=_font(24 * SS),
               fill=_color(PALETA.navy_soft), anchor="lm")
    return barra_h


def _boton_redondeado(draw, x, y, w, h, texto, relleno, color_texto=(255, 255, 255), fuente=None):
    draw.rounded_rectangle([x, y, x + w, y + h], radius=h // 2, fill=relleno)
    fuente = fuente or _font(26 * SS, bold=True)
    draw.text((x + w / 2, y + h / 2), texto, font=fuente, fill=color_texto, anchor="mm")


def _insignia_paso(draw, cx, cy, r, numero):
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=_color(PALETA.navy))
    draw.text((cx, cy), str(numero), font=_font(int(r * 1.1), bold=True),
               fill=(255, 255, 255), anchor="mm")


def _imagen_1_abrir_navegador() -> None:
    img, d = _lienzo()
    margen = 90 * SS
    bx, by = margen, margen + 40 * SS
    bw, bh = W * SS - 2 * margen, H * SS - 2 * margen - 60 * SS
    barra_h = _ventana_navegador(d, bx, by, bw, bh, "colab.research.google.com")
    cuerpo_y = by + barra_h
    cx = bx + bw // 2
    r_icono = 110 * SS
    d.rounded_rectangle(
        [cx - r_icono, cuerpo_y + 90 * SS, cx + r_icono, cuerpo_y + 90 * SS + r_icono * 2],
        radius=28 * SS, fill=_color(PALETA.teal_light), outline=_color(PALETA.teal), width=4 * SS,
    )
    nx0, ny0 = cx - 55 * SS, cuerpo_y + 90 * SS + 55 * SS
    nx1, ny1 = cx + 55 * SS, cuerpo_y + 90 * SS + 165 * SS
    d.rounded_rectangle([nx0, ny0, nx1, ny1], radius=10 * SS, fill=(255, 255, 255),
                         outline=_color(PALETA.navy), width=4 * SS)
    for i in range(3):
        yy = ny0 + 26 * SS + i * 26 * SS
        d.line([nx0 + 16 * SS, yy, nx1 - 16 * SS, yy], fill=_color(PALETA.gray), width=4 * SS)
    d.text((cx, cuerpo_y + 90 * SS + r_icono * 2 + 60 * SS), "Google Colaboratory",
            font=_font(46 * SS, bold=True), fill=_color(PALETA.text), anchor="mm")
    d.text((cx, cuerpo_y + 90 * SS + r_icono * 2 + 120 * SS), "Cuadernos de código en la nube",
            font=_font(28 * SS), fill=_color(PALETA.gray), anchor="mm")
    _insignia_paso(d, bx - 10 * SS, by - 10 * SS, 46 * SS, 1)
    _guardar(img, "01_abrir_navegador")


def _imagen_2_inicio_sesion() -> None:
    img, d = _lienzo()
    margen = 90 * SS
    bx, by = margen, margen + 40 * SS
    bw, bh = W * SS - 2 * margen, H * SS - 2 * margen - 60 * SS
    barra_h = _ventana_navegador(d, bx, by, bw, bh, "accounts.google.com")
    card_w, card_h = 760 * SS, 620 * SS
    card_x = bx + (bw - card_w) // 2
    card_y = by + barra_h + 60 * SS
    d.rounded_rectangle([card_x, card_y, card_x + card_w, card_y + card_h], radius=24 * SS,
                         fill=(255, 255, 255), outline=_color(PALETA.gray_light), width=2 * SS)
    r = 46 * SS
    acx, acy = card_x + card_w // 2, card_y + 90 * SS
    d.ellipse([acx - r, acy - r, acx + r, acy + r], fill=_color(PALETA.navy))
    d.ellipse([acx - 20 * SS, acy - 26 * SS, acx + 20 * SS, acy + 14 * SS], fill=(255, 255, 255))
    d.pieslice([acx - 34 * SS, acy + 6 * SS, acx + 34 * SS, acy + 60 * SS], 180, 360,
               fill=(255, 255, 255))
    d.text((acx, card_y + 160 * SS), "Iniciar sesión", font=_font(32 * SS, bold=True),
            fill=_color(PALETA.text), anchor="mm")
    d.text((acx, card_y + 200 * SS), "Utiliza tu cuenta de la UMH", font=_font(24 * SS),
            fill=_color(PALETA.gray), anchor="mm")
    fx0, fx1 = card_x + 70 * SS, card_x + card_w - 70 * SS
    fy0, fy1 = card_y + 260 * SS, card_y + 260 * SS + 76 * SS
    d.rounded_rectangle([fx0, fy0, fx1, fy1], radius=12 * SS, fill=(255, 255, 255),
                         outline=_color(PALETA.teal), width=3 * SS)
    d.text((fx0 + 22 * SS, (fy0 + fy1) // 2), "nombre.apellido@umh.es",
            font=_font(26 * SS), fill=_color(PALETA.navy_soft), anchor="lm")
    fy2_0, fy2_1 = fy1 + 30 * SS, fy1 + 30 * SS + 76 * SS
    d.rounded_rectangle([fx0, fy2_0, fx1, fy2_1], radius=12 * SS, fill=(255, 255, 255),
                         outline=_color(PALETA.gray_light), width=3 * SS)
    d.text((fx0 + 22 * SS, (fy2_0 + fy2_1) // 2), "••••••••••••", font=_font(26 * SS),
            fill=_color(PALETA.gray), anchor="lm")
    _boton_redondeado(d, fx1 - 220 * SS, fy2_1 + 40 * SS, 220 * SS, 70 * SS, "Siguiente",
                       relleno=_color(PALETA.teal))
    _insignia_paso(d, bx - 10 * SS, by - 10 * SS, 46 * SS, 2)
    _guardar(img, "02_inicio_sesion")


def _imagen_3_nuevo_notebook() -> None:
    img, d = _lienzo()
    margen = 90 * SS
    bx, by = margen, margen + 40 * SS
    bw, bh = W * SS - 2 * margen, H * SS - 2 * margen - 60 * SS
    barra_h = _ventana_navegador(d, bx, by, bw, bh, "colab.research.google.com")
    menu_y0 = by + barra_h
    menu_h = 90 * SS
    d.rectangle([bx, menu_y0, bx + bw, menu_y0 + menu_h], fill=(255, 255, 255))
    d.line([bx, menu_y0 + menu_h, bx + bw, menu_y0 + menu_h],
           fill=_color(PALETA.gray_light), width=2 * SS)
    for i, etiqueta in enumerate(["Archivo", "Editar", "Ver", "Insertar", "Entorno de ejecución"]):
        d.text((bx + 40 * SS + i * 240 * SS, menu_y0 + menu_h // 2), etiqueta,
                font=_font(26 * SS), fill=_color(PALETA.navy_soft), anchor="lm")
    panel_y = menu_y0 + menu_h + 70 * SS
    cx = bx + bw // 2
    d.text((cx, panel_y), "Bienvenido a Colab", font=_font(40 * SS, bold=True),
            fill=_color(PALETA.text), anchor="mm")
    btn_w, btn_h = 420 * SS, 96 * SS
    _boton_redondeado(d, cx - btn_w // 2, panel_y + 90 * SS, btn_w, btn_h,
                       "+  Nuevo notebook", relleno=_color(PALETA.orange),
                       fuente=_font(30 * SS, bold=True))
    _insignia_paso(d, bx - 10 * SS, by - 10 * SS, 46 * SS, 3)
    _guardar(img, "03_nuevo_notebook")


def _imagen_4_interfaz() -> None:
    img, d = _lienzo()
    margen = 90 * SS
    bx, by = margen, margen + 40 * SS
    bw, bh = W * SS - 2 * margen, H * SS - 2 * margen - 60 * SS
    barra_h = _ventana_navegador(d, bx, by, bw, bh, "colab.research.google.com/notebook")
    top = by + barra_h
    menu_h = 80 * SS
    d.rectangle([bx, top, bx + bw, top + menu_h], fill=(255, 255, 255))
    d.line([bx, top + menu_h, bx + bw, top + menu_h], fill=_color(PALETA.gray_light), width=2 * SS)
    d.text((bx + 40 * SS, top + menu_h // 2), "Practica_01.ipynb",
            font=_font(26 * SS, bold=True), fill=_color(PALETA.text), anchor="lm")
    cx0, cx1 = bx + 60 * SS, bx + bw - 60 * SS
    cy0, cy1 = top + menu_h + 60 * SS, top + menu_h + 60 * SS + 200 * SS
    d.rounded_rectangle([cx0, cy0, cx1, cy1], radius=14 * SS, fill=(40, 44, 52),
                         outline=_color(PALETA.gray_light), width=2 * SS)
    r_play = 26 * SS
    play_cx, play_cy = cx0 + 40 * SS, cy0 + 40 * SS
    d.ellipse([play_cx - r_play, play_cy - r_play, play_cx + r_play, play_cy + r_play],
              fill=_color(PALETA.teal))
    d.polygon([(play_cx - 9 * SS, play_cy - 14 * SS), (play_cx - 9 * SS, play_cy + 14 * SS),
               (play_cx + 15 * SS, play_cy)], fill=(255, 255, 255))
    for i, linea in enumerate(["import pandas as pd", "print('Hola, Tecnología en Moda')"]):
        d.text((cx0 + 90 * SS, cy0 + 34 * SS + i * 44 * SS), linea, font=_font(24 * SS),
                fill=_color(PALETA.teal_light))
    my0, my1 = cy1 + 40 * SS, cy1 + 40 * SS + 120 * SS
    d.rounded_rectangle([cx0, my0, cx1, my1], radius=14 * SS, fill=(255, 255, 255),
                         outline=_color(PALETA.gray_light), width=2 * SS)
    d.text((cx0 + 30 * SS, my0 + 30 * SS), "## Anotaciones", font=_font(28 * SS, bold=True),
            fill=_color(PALETA.text))
    d.text((cx0 + 30 * SS, my0 + 74 * SS), "Texto explicativo del ejercicio…",
            font=_font(24 * SS), fill=_color(PALETA.gray))
    r_lbl = 28 * SS
    l1_cx, l1_cy = play_cx + 30 * SS, cy0 - 60 * SS
    d.line([play_cx, cy0 - 6 * SS, l1_cx, l1_cy + r_lbl], fill=_color(PALETA.navy_soft), width=3 * SS)
    _insignia_paso(d, l1_cx, l1_cy, r_lbl, 1)
    d.text((l1_cx + r_lbl + 16 * SS, l1_cy), "Botón para ejecutar la celda",
            font=_font(26 * SS), fill=_color(PALETA.navy_soft), anchor="lm")
    l2_cx, l2_cy = cx0 + 260 * SS, my0 - 55 * SS
    d.line([cx0 + 220 * SS, my0 - 4 * SS, l2_cx, l2_cy + r_lbl], fill=_color(PALETA.navy_soft), width=3 * SS)
    _insignia_paso(d, l2_cx, l2_cy, r_lbl, 2)
    d.text((l2_cx + r_lbl + 16 * SS, l2_cy), "Celda de texto (anotaciones)",
            font=_font(26 * SS), fill=_color(PALETA.navy_soft), anchor="lm")
    _guardar(img, "04_interfaz")


def generar_ilustraciones() -> None:
    """Genera (o regenera) las 4 ilustraciones usadas en el documento."""
    _imagen_1_abrir_navegador()
    _imagen_2_inicio_sesion()
    _imagen_3_nuevo_notebook()
    _imagen_4_interfaz()


# ==============================================================================
# PARTE 3 · UTILIDADES DE BAJO NIVEL PARA PYTHON-DOCX — sin cambios
# ==============================================================================

def _set_cell_background(cell: _Cell, hex_color: str) -> None:
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), hex_color)
    tc_pr.append(shd)


def _set_cell_margins(cell: _Cell, top=100, bottom=100, left=150, right=150) -> None:
    tc_pr = cell._tc.get_or_add_tcPr()
    mar = OxmlElement("w:tcMar")
    for lado, valor in (("top", top), ("bottom", bottom), ("start", left), ("end", right)):
        nodo = OxmlElement(f"w:{lado}")
        nodo.set(qn("w:w"), str(valor))
        nodo.set(qn("w:type"), "dxa")
        mar.append(nodo)
    tc_pr.append(mar)


def _set_table_borders(table: Table, **kwargs) -> None:
    tbl_pr = table._tbl.tblPr
    borders = OxmlElement("w:tblBorders")
    for lado in ("top", "start", "bottom", "end", "insideH", "insideV"):
        nodo = OxmlElement(f"w:{lado}")
        valor = kwargs.get(lado)
        if valor is None:
            nodo.set(qn("w:val"), "none")
            nodo.set(qn("w:sz"), "0")
            nodo.set(qn("w:color"), "FFFFFF")
        else:
            tam, color = valor
            nodo.set(qn("w:val"), "single")
            nodo.set(qn("w:sz"), str(tam))
            nodo.set(qn("w:color"), color)
        borders.append(nodo)
    tbl_pr.append(borders)


def _set_paragraph_bottom_border(paragraph: Paragraph, color: str, size: int = 10) -> None:
    p_pr = paragraph._p.get_or_add_pPr()
    p_bdr = OxmlElement("w:pBdr")
    bottom = OxmlElement("w:bottom")
    bottom.set(qn("w:val"), "single")
    bottom.set(qn("w:sz"), str(size))
    bottom.set(qn("w:space"), "6")
    bottom.set(qn("w:color"), color)
    p_bdr.append(bottom)
    p_pr.append(p_bdr)


def _add_field(paragraph: Paragraph, field_code: str) -> None:
    run = paragraph.add_run()
    fld_begin = OxmlElement("w:fldChar")
    fld_begin.set(qn("w:fldCharType"), "begin")
    instr = OxmlElement("w:instrText")
    instr.set(qn("xml:space"), "preserve")
    instr.text = field_code
    fld_sep = OxmlElement("w:fldChar")
    fld_sep.set(qn("w:fldCharType"), "separate")
    fld_end = OxmlElement("w:fldChar")
    fld_end.set(qn("w:fldCharType"), "end")
    run._r.append(fld_begin)
    run._r.append(instr)
    run._r.append(fld_sep)
    run._r.append(fld_end)


def _restart_page_numbering(section, start: int = 1) -> None:
    sect_pr = section._sectPr
    pg_num_type = OxmlElement("w:pgNumType")
    pg_num_type.set(qn("w:start"), str(start))
    sect_pr.append(pg_num_type)


def _unlink_header_footer(section) -> None:
    section.header.is_linked_to_previous = False
    section.footer.is_linked_to_previous = False


def _clear_default_paragraph(container):
    if container.paragraphs:
        return container.paragraphs[0]
    return container.add_paragraph()


# ==============================================================================
# PARTE 4 · OBTENCIÓN DEL CONTENIDO A TRAVÉS DE LA API DE ANTHROPIC
# ==============================================================================
#
# En vez de tener el texto "hardcodeado", se lo pedimos al modelo en forma
# de JSON estructurado en "bloques". Cada bloque indica su tipo (párrafo,
# viñetas, nota, figura, subtítulo…) y el propio motor de maquetación
# (PARTE 5) sabe cómo convertir cada tipo de bloque en párrafos de Word.

# Nombres de las 4 imágenes disponibles, para que el modelo sepa qué
# identificadores puede usar en los bloques de tipo "figura".
IMAGENES_DISPONIBLES = [
    "01_abrir_navegador",
    "02_inicio_sesion",
    "03_nuevo_notebook",
    "04_interfaz",
]

# Esquema JSON que debe devolver el modelo. Se incluye tal cual dentro del
# prompt para que la respuesta sea siempre analizable por el programa.
ESQUEMA_JSON = """
{
  "portada": {
    "kicker": "string (línea corta en mayúsculas, p. ej. el nombre de la asignatura)",
    "titulo_linea_1": "string (p. ej. 'Guía de acceso a')",
    "titulo_linea_2": "string (p. ej. 'Google Colab')",
    "subtitulo": "string",
    "universidad": "string",
    "grado": "string",
    "departamento": "string"
  },
  "indice": [
    {"numero": "1.", "texto": "Introducción"}
  ],
  "secciones": [
    {
      "titulo": "1. Introducción",
      "bloques": [
        {"tipo": "parrafo", "texto": "..."},
        {"tipo": "subtitulo", "texto": "..."},
        {"tipo": "url_destacada", "texto": "colab.research.google.com"},
        {"tipo": "vinetas", "items": ["...", "..."]},
        {"tipo": "nota", "titulo": "...", "texto": "...", "estilo": "teal|orange"},
        {"tipo": "figura", "imagen": "01_abrir_navegador", "ancho_cm": 12, "pie": "Figura 1. ..."}
      ]
    }
  ]
}
""".strip()


def _construir_prompt() -> tuple[str, str]:
    """Construye el prompt (system + user) que se enviará a la API.

    Se le pide EXPLÍCITAMENTE al modelo el mismo contenido pedagógico ya
    validado para esta guía (mismas 7 secciones, mismo tono cercano y en
    español de España), de modo que el documento resultante sea el mismo
    que el generado en la versión anterior del script. Si en el futuro se
    quiere un contenido distinto, basta con reescribir este prompt.
    """
    system = (
        "Eres un redactor técnico-docente experto en materiales didácticos "
        "universitarios en español de España. Debes devolver ÚNICAMENTE un "
        "JSON válido (sin texto adicional, sin bloques ```), que siga "
        "exactamente el esquema indicado por el usuario. No inventes tipos "
        "de bloque distintos a los permitidos: parrafo, subtitulo, "
        "url_destacada, vinetas, nota, figura."
    )

    user = f"""
Redacta el contenido de una guía en Word, dirigida a alumnado de la
asignatura "Tecnología en Moda" (Grado en Gestión, Tecnología y Moda,
Universidad Miguel Hernández de Elche) que NO tiene experiencia previa con
Google Colab. Todos los alumnos disponen de cuenta institucional de la UMH.

El documento debe tener exactamente estas 7 secciones, en este orden:
  1. Introducción (qué es Google Colab y por qué se usa en la asignatura).
  2. Requisitos previos (cuenta institucional UMH, navegador, conexión a
     internet; incluye una nota de tipo "orange" recordando usar la cuenta
     institucional y no una personal).
  3. Acceso paso a paso, con 4 subapartados que usan, en este orden, las
     imágenes "01_abrir_navegador", "02_inicio_sesion", "03_nuevo_notebook"
     y "04_interfaz" (cada una en un bloque de tipo "figura", con su pie de
     figura numerado "Figura 1.", "Figura 2.", etc.). El primer subapartado
     debe incluir un bloque "url_destacada" con el texto
     "colab.research.google.com". El último subapartado debe terminar con
     una lista de viñetas explicando los elementos de la interfaz (botón de
     ejecutar, celdas de texto, nombre del archivo, menú superior).
  4. Primeros pasos dentro del notebook (renombrar el archivo, ejecutar una
     celda, añadir una celda de texto, guardar en Drive), como viñetas.
  5. Consejos y buenas prácticas, como viñetas.
  6. Solución de problemas frecuentes, con 4 subtítulos (uno por problema
     típico: no reconoce la cuenta institucional, la página no responde,
     el notebook aparece en inglés, no encuentra el notebook guardado) y un
     párrafo de solución debajo de cada uno.
  7. Recursos adicionales, como viñetas, terminando con una nota invitando a
     consultar al profesorado.

Devuelve el resultado como un único JSON que siga EXACTAMENTE este esquema
(los comentarios entre paréntesis son solo orientativos, no los incluyas
en la respuesta):

{ESQUEMA_JSON}

Requisitos de estilo: español de España, tono cercano y claro, sin
tecnicismos innecesarios, párrafos breves (máximo 4-5 líneas). El campo
"indice" debe tener una entrada por cada una de las 7 secciones, con el
mismo texto que el título de cada sección (sin el número).
""".strip()

    return system, user


def _extraer_json(texto_respuesta: str) -> dict:
    """Limpia la respuesta del modelo (por si acaso viene envuelta en
    bloques de código ```json ... ```) y la convierte en un diccionario."""
    texto = texto_respuesta.strip()
    if texto.startswith("```"):
        texto = texto.strip("`")
        # Quita un posible prefijo de idioma, p. ej. "json\n{...}"
        if texto.lstrip().startswith("json"):
            texto = texto.lstrip()[4:]
    return json.loads(texto)


def obtener_contenido_desde_api() -> dict:
    """Llama a la API de Anthropic para generar el contenido del documento
    y lo devuelve ya convertido en un diccionario Python (según el esquema
    definido en ESQUEMA_JSON)."""
    if Anthropic is None:
        raise RuntimeError(
            "No se encuentra instalado el paquete 'anthropic'. Instálalo con:\n"
            "    pip install anthropic"
        )

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError(
            "No se ha encontrado la variable de entorno ANTHROPIC_API_KEY.\n"
            "Configúrala con tu API key de https://console.anthropic.com "
            "antes de ejecutar este script (ver instrucciones al principio "
            "del archivo)."
        )

    cliente = Anthropic(api_key=api_key)
    system, user = _construir_prompt()

    respuesta = cliente.messages.create(
        model=MODELO_ANTHROPIC,
        max_tokens=4000,
        system=system,
        messages=[{"role": "user", "content": user}],
    )

    # La respuesta puede venir dividida en varios bloques de texto;
    # los unimos antes de analizarla como JSON.
    texto_completo = "".join(
        bloque.text for bloque in respuesta.content if bloque.type == "text"
    )
    return _extraer_json(texto_completo)


# ==============================================================================
# PARTE 5 · RENDERIZADOR GENÉRICO: JSON → DOCUMENTO WORD
# ==============================================================================

def add_heading_1(doc: DocumentObject, texto: str) -> Paragraph:
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(24)
    p.paragraph_format.space_after = Pt(12)
    run = p.add_run(texto)
    run.font.name, run.font.size, run.font.bold = FONT_NAME, Pt(16), True
    run.font.color.rgb = rgb(PALETA.navy)
    _set_paragraph_bottom_border(p, PALETA.teal, size=10)
    return p


def add_heading_2(doc: DocumentObject, texto: str) -> Paragraph:
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(18)
    p.paragraph_format.space_after = Pt(8)
    run = p.add_run(texto)
    run.font.name, run.font.size, run.font.bold = FONT_NAME, Pt(13), True
    run.font.color.rgb = rgb(PALETA.navy_soft)
    return p


def add_body(doc: DocumentObject, texto: str) -> Paragraph:
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    p.paragraph_format.space_after = Pt(9)
    p.paragraph_format.line_spacing = 1.2
    run = p.add_run(texto)
    run.font.name, run.font.size = FONT_NAME, Pt(11)
    run.font.color.rgb = rgb(PALETA.text)
    return p


def add_url_destacada(doc: DocumentObject, texto: str) -> Paragraph:
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_after = Pt(8)
    run = p.add_run(texto)
    run.font.name, run.font.size, run.font.bold = FONT_MONO, Pt(13), True
    run.font.color.rgb = rgb(PALETA.teal)
    return p


def add_bullet(doc: DocumentObject, texto: str) -> Paragraph:
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(5)
    p.paragraph_format.line_spacing = 1.15
    p.paragraph_format.left_indent = Cm(0.9)
    p.paragraph_format.first_line_indent = Cm(-0.5)
    marcador = p.add_run("—  ")
    marcador.font.name, marcador.font.size, marcador.font.bold = FONT_NAME, Pt(11), True
    marcador.font.color.rgb = rgb(PALETA.teal)
    texto_run = p.add_run(texto)
    texto_run.font.name, texto_run.font.size = FONT_NAME, Pt(11)
    texto_run.font.color.rgb = rgb(PALETA.text)
    return p


def add_figure(doc: DocumentObject, nombre_archivo: str, ancho_cm: float, pie_de_figura: str) -> None:
    ruta = os.path.join(IMG_DIR, f"{nombre_archivo}.png")
    p_img = doc.add_paragraph()
    p_img.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_img.paragraph_format.space_before = Pt(6)
    p_img.paragraph_format.space_after = Pt(4)
    run = p_img.add_run()
    run.add_picture(ruta, width=Cm(ancho_cm))

    p_pie = doc.add_paragraph()
    p_pie.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_pie.paragraph_format.space_after = Pt(18)
    run_pie = p_pie.add_run(pie_de_figura)
    run_pie.font.name, run_pie.font.size, run_pie.font.italic = FONT_NAME, Pt(10), True
    run_pie.font.color.rgb = rgb(PALETA.gray)


def add_note_box(doc: DocumentObject, titulo: str, texto: str, estilo: str = "teal") -> None:
    color_borde = PALETA.orange if estilo == "orange" else PALETA.teal
    color_fondo = PALETA.orange_light if estilo == "orange" else PALETA.note_bg

    tabla = doc.add_table(rows=1, cols=1)
    tabla.autofit = True
    celda = tabla.rows[0].cells[0]
    _set_cell_background(celda, color_fondo)
    _set_cell_margins(celda, top=150, bottom=150, left=250, right=200)
    celda.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
    _set_table_borders(
        tabla,
        top=(4, PALETA.gray_light), bottom=(4, PALETA.gray_light),
        end=(4, PALETA.gray_light), start=(28, color_borde),
        insideH=None, insideV=None,
    )

    p_titulo = _clear_default_paragraph(celda)
    p_titulo.paragraph_format.space_after = Pt(3)
    r_titulo = p_titulo.add_run(titulo)
    r_titulo.font.name, r_titulo.font.size, r_titulo.font.bold = FONT_NAME, Pt(10.5), True
    r_titulo.font.color.rgb = rgb(PALETA.navy)

    p_texto = celda.add_paragraph()
    p_texto.paragraph_format.line_spacing = 1.15
    r_texto = p_texto.add_run(texto)
    r_texto.font.name, r_texto.font.size = FONT_NAME, Pt(10.5)
    r_texto.font.color.rgb = rgb(PALETA.text)

    doc.add_paragraph().paragraph_format.space_after = Pt(6)


def add_toc_entry(doc: DocumentObject, numero: str, texto: str) -> None:
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(10)
    p.paragraph_format.tab_stops.add_tab_stop(Cm(1.2))
    r_num = p.add_run(f"{numero}\t")
    r_num.font.name, r_num.font.size, r_num.font.bold = FONT_NAME, Pt(12), True
    r_num.font.color.rgb = rgb(PALETA.teal)
    r_txt = p.add_run(texto)
    r_txt.font.name, r_txt.font.size = FONT_NAME, Pt(12)
    r_txt.font.color.rgb = rgb(PALETA.navy)


# --- Despachador de bloques ---------------------------------------------------
# Cada entrada del JSON "bloques" tiene un campo "tipo"; este diccionario
# asocia cada tipo con la función que sabe dibujarlo en el documento.

def _renderizar_bloque(doc: DocumentObject, bloque: dict) -> None:
    tipo = bloque.get("tipo")
    if tipo == "parrafo":
        add_body(doc, bloque["texto"])
    elif tipo == "subtitulo":
        add_heading_2(doc, bloque["texto"])
    elif tipo == "url_destacada":
        add_url_destacada(doc, bloque["texto"])
    elif tipo == "vinetas":
        for item in bloque["items"]:
            add_bullet(doc, item)
    elif tipo == "nota":
        add_note_box(doc, bloque["titulo"], bloque["texto"], bloque.get("estilo", "teal"))
    elif tipo == "figura":
        add_figure(doc, bloque["imagen"], bloque.get("ancho_cm", 12), bloque["pie"])
    else:
        raise ValueError(f"Tipo de bloque no reconocido en la respuesta de la API: {tipo!r}")


def construir_portada(doc: DocumentObject, portada: dict) -> None:
    doc.add_paragraph().paragraph_format.space_before = Pt(90)

    tabla = doc.add_table(rows=1, cols=1)
    celda = tabla.rows[0].cells[0]
    _set_cell_background(celda, PALETA.navy)
    _set_cell_margins(celda, top=700, bottom=700, left=700, right=700)
    _set_table_borders(tabla, top=None, bottom=None, start=None, end=None, insideH=None, insideV=None)

    def _linea(contenedor, texto, size, color, bold=False, italic=False, space_after=6, primera=False):
        p = _clear_default_paragraph(contenedor) if primera else contenedor.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.space_after = Pt(space_after)
        r = p.add_run(texto)
        r.font.name, r.font.size, r.font.bold, r.font.italic = FONT_NAME, Pt(size), bold, italic
        r.font.color.rgb = rgb(color)

    _linea(celda, portada["kicker"], 11, "BFD7EC", bold=True, space_after=14, primera=True)
    _linea(celda, portada["titulo_linea_1"], 20, "FFFFFF", space_after=4)
    _linea(celda, portada["titulo_linea_2"], 30, "FFFFFF", bold=True, space_after=18)
    _linea(celda, portada["subtitulo"], 12, PALETA.teal_light, italic=True, space_after=0)

    doc.add_paragraph().paragraph_format.space_before = Pt(28)
    for texto, size, color, bold in [
        (portada["universidad"], 12, PALETA.navy, True),
        (portada["grado"], 11, PALETA.navy_soft, False),
        (portada["departamento"], 10, PALETA.gray, False),
    ]:
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.space_after = Pt(2)
        r = p.add_run(texto)
        r.font.name, r.font.size, r.font.bold = FONT_NAME, Pt(size), bold
        r.font.color.rgb = rgb(color)


def construir_indice(doc: DocumentObject, indice: list[dict]) -> None:
    add_heading_1(doc, "Índice")
    doc.add_paragraph().paragraph_format.space_after = Pt(4)
    for entrada in indice:
        add_toc_entry(doc, entrada["numero"], entrada["texto"])


def construir_encabezado_pie(section) -> None:
    header_p = _clear_default_paragraph(section.header)
    header_p.paragraph_format.tab_stops.add_tab_stop(Cm(16.5))
    _set_paragraph_bottom_border(header_p, PALETA.gray_light, size=4)
    r1 = header_p.add_run("Tecnología en Moda")
    r1.font.name, r1.font.size = FONT_NAME, Pt(9)
    r1.font.color.rgb = rgb(PALETA.gray)
    r2 = header_p.add_run("\tGuía de acceso a Google Colab")
    r2.font.name, r2.font.size = FONT_NAME, Pt(9)
    r2.font.color.rgb = rgb(PALETA.gray)

    footer_p = _clear_default_paragraph(section.footer)
    footer_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r_pref = footer_p.add_run("Página ")
    r_pref.font.name, r_pref.font.size = FONT_NAME, Pt(9)
    r_pref.font.color.rgb = rgb(PALETA.gray)
    _add_field(footer_p, "PAGE")


# ==============================================================================
# PARTE 6 · MONTAJE DEL DOCUMENTO Y PUNTO DE ENTRADA
# ==============================================================================

def construir_documento(contenido: dict) -> DocumentObject:
    """Recibe el diccionario de contenido (procedente de la API) y
    construye el objeto Document completo con el mismo diseño que la
    versión anterior del script."""
    doc = Document()

    seccion_portada = doc.sections[0]
    seccion_portada.page_width = Cm(21.0)
    seccion_portada.page_height = Cm(29.7)
    for margen in ("top_margin", "bottom_margin", "left_margin", "right_margin"):
        setattr(seccion_portada, margen, Cm(2.0))

    estilo_normal = doc.styles["Normal"]
    estilo_normal.font.name = FONT_NAME
    estilo_normal.font.size = Pt(11)

    construir_portada(doc, contenido["portada"])

    seccion_contenido = doc.add_section(WD_SECTION.NEW_PAGE)
    seccion_contenido.page_width = Cm(21.0)
    seccion_contenido.page_height = Cm(29.7)
    seccion_contenido.top_margin = Cm(2.3)
    seccion_contenido.bottom_margin = Cm(2.1)
    seccion_contenido.left_margin = Cm(2.3)
    seccion_contenido.right_margin = Cm(2.3)
    _unlink_header_footer(seccion_contenido)
    _restart_page_numbering(seccion_contenido, start=1)
    construir_encabezado_pie(seccion_contenido)

    construir_indice(doc, contenido["indice"])
    doc.add_page_break()

    for seccion in contenido["secciones"]:
        add_heading_1(doc, seccion["titulo"])
        for bloque in seccion["bloques"]:
            _renderizar_bloque(doc, bloque)

    return doc


def main() -> None:
    print("1/3 · Generando ilustraciones…")
    generar_ilustraciones()

    print("2/3 · Solicitando el contenido a la API de Anthropic…")
    contenido = obtener_contenido_desde_api()

    print("3/3 · Construyendo el documento Word…")
    documento = construir_documento(contenido)

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    documento.save(DOCX_PATH)

    print(f"\n✅ Documento generado correctamente en:\n   {DOCX_PATH}")


if __name__ == "__main__":
    main()
