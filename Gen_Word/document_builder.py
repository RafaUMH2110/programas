"""
document_builder.py
================================================================================
El "motor de plantilla": convierte un diccionario de contenido (portada,
índice, secciones con bloques) en un documento Word con el diseño visual
exacto de la plantilla original — misma paleta de colores, misma
tipografía, misma portada con bloque de color, mismo índice manual, mismas
cajas de aviso, mismo encabezado/pie con número de página automático.

Este módulo NO sabe nada sobre de dónde viene el contenido (podría venir
de la API de Anthropic, de un archivo JSON escrito a mano, o de tests).
Tampoco sabe nada sobre cómo se obtienen las imágenes: espera que cada
bloque de tipo "figura" ya incluya una clave "image_path" apuntando a un
archivo existente en disco. Esta separación de responsabilidades es lo
que permite reutilizar el mismo motor para cualquier tema.

Notas de implementación
-------------------------
python-docx no expone una API de alto nivel para varias cosas que usa
esta plantilla (sombreado de celdas, bordes de párrafo, el campo de
número de página, el reinicio de numeración por sección). Esas
utilidades de bajo nivel manipulan directamente el XML interno (oxml) y
están todas agrupadas al principio del archivo, claramente separadas de
las funciones de "alto nivel" que se usan para maquetar contenido.
================================================================================
"""

from __future__ import annotations

import os
from typing import Any

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

import config

PALETA = config.PALETA
MAQUETACION = config.MAQUETACION
FONT_NAME = config.FONT_NAME
FONT_MONO = config.FONT_MONO


def rgb(hex_color: str) -> RGBColor:
    """Convierte un color hexadecimal ('RRGGBB') a un objeto RGBColor."""
    return RGBColor.from_string(hex_color)


# ==============================================================================
# UTILIDADES DE BAJO NIVEL (manipulación directa del XML / oxml)
# ==============================================================================

def _set_cell_background(cell: _Cell, hex_color: str) -> None:
    """Aplica un color de relleno sólido a una celda de tabla."""
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), hex_color)
    tc_pr.append(shd)


def _set_cell_margins(cell: _Cell, top: int = 100, bottom: int = 100,
                       left: int = 150, right: int = 150) -> None:
    """Define los márgenes internos (en twips) de una celda de tabla."""
    tc_pr = cell._tc.get_or_add_tcPr()
    mar = OxmlElement("w:tcMar")
    for lado, valor in (("top", top), ("bottom", bottom), ("start", left), ("end", right)):
        nodo = OxmlElement(f"w:{lado}")
        nodo.set(qn("w:w"), str(valor))
        nodo.set(qn("w:type"), "dxa")
        mar.append(nodo)
    tc_pr.append(mar)


def _set_table_borders(table: Table, **kwargs: tuple[int, str] | None) -> None:
    """Configura los bordes de una tabla. Cada lado se indica como
    ``kwargs['top'] = (tamaño_en_octavos_de_punto, 'RRGGBB')`` o ``None``
    para no dibujar ese lado. Lados admitidos: top, start, bottom, end,
    insideH, insideV."""
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
    """Añade una línea horizontal bajo un párrafo (se usa en los títulos H1
    a modo de filete de separación)."""
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
    """Inserta un campo de Word "complejo" (p. ej. PAGE) dentro de un
    párrafo, construido a mano con los tres bloques que exige OOXML:
    fldChar(begin) → instrText → fldChar(separate) → fldChar(end)."""
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
    """Reinicia la numeración de página (empezando en ``start``) a partir
    de la sección indicada."""
    sect_pr = section._sectPr
    pg_num_type = OxmlElement("w:pgNumType")
    pg_num_type.set(qn("w:start"), str(start))
    sect_pr.append(pg_num_type)


def _unlink_header_footer(section) -> None:
    """Desvincula encabezado y pie de una sección respecto a la anterior,
    para poder darle un contenido propio (la portada no lleva pie)."""
    section.header.is_linked_to_previous = False
    section.footer.is_linked_to_previous = False


def _clear_default_paragraph(container: Any) -> Paragraph:
    """Los encabezados/pies/celdas nuevos traen un párrafo vacío por
    defecto; se reutiliza como primer párrafo en vez de añadir uno extra."""
    if container.paragraphs:
        return container.paragraphs[0]
    return container.add_paragraph()


# ==============================================================================
# FUNCIONES DE ALTO NIVEL (un tipo de bloque de contenido → párrafos Word)
# ==============================================================================

def add_heading_1(doc: DocumentObject, texto: str) -> Paragraph:
    """Título de sección: grande, azul marino, con filete turquesa debajo."""
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(24)
    p.paragraph_format.space_after = Pt(12)
    run = p.add_run(texto)
    run.font.name, run.font.size, run.font.bold = FONT_NAME, Pt(16), True
    run.font.color.rgb = rgb(PALETA.navy)
    _set_paragraph_bottom_border(p, PALETA.teal, size=10)
    return p


def add_heading_2(doc: DocumentObject, texto: str) -> Paragraph:
    """Subtítulo: mediano, azul marino suave, sin filete."""
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(18)
    p.paragraph_format.space_after = Pt(8)
    run = p.add_run(texto)
    run.font.name, run.font.size, run.font.bold = FONT_NAME, Pt(13), True
    run.font.color.rgb = rgb(PALETA.navy_soft)
    return p


def add_body(doc: DocumentObject, texto: str) -> Paragraph:
    """Párrafo de texto normal, justificado, con interlineado cómodo."""
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    p.paragraph_format.space_after = Pt(9)
    p.paragraph_format.line_spacing = 1.2
    run = p.add_run(texto)
    run.font.name, run.font.size = FONT_NAME, Pt(11)
    run.font.color.rgb = rgb(PALETA.text)
    return p


def add_url_destacada(doc: DocumentObject, texto: str) -> Paragraph:
    """Línea de código/URL centrada y resaltada en fuente monoespaciada."""
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_after = Pt(8)
    run = p.add_run(texto)
    run.font.name, run.font.size, run.font.bold = FONT_MONO, Pt(13), True
    run.font.color.rgb = rgb(PALETA.teal)
    return p


def add_bullet(doc: DocumentObject, texto: str) -> Paragraph:
    """Viñeta con un guion largo en color turquesa como marcador."""
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


def add_figure(doc: DocumentObject, image_path: str, ancho_cm: float, pie_de_figura: str) -> None:
    """Inserta una imagen centrada seguida de su pie de figura en cursiva.

    Si ``image_path`` no existe en disco (por ejemplo, porque el servicio
    de imágenes falló de una forma no prevista), se omite la imagen
    mostrando únicamente el pie de figura, en vez de interrumpir la
    generación de todo el documento.
    """
    if image_path and os.path.exists(image_path):
        p_img = doc.add_paragraph()
        p_img.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p_img.paragraph_format.space_before = Pt(6)
        p_img.paragraph_format.space_after = Pt(4)
        run = p_img.add_run()
        run.add_picture(image_path, width=Cm(ancho_cm))

    p_pie = doc.add_paragraph()
    p_pie.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_pie.paragraph_format.space_after = Pt(18)
    run_pie = p_pie.add_run(pie_de_figura)
    run_pie.font.name, run_pie.font.size, run_pie.font.italic = FONT_NAME, Pt(10), True
    run_pie.font.color.rgb = rgb(PALETA.gray)


def add_note_box(doc: DocumentObject, titulo: str, texto: str, estilo: str = "teal") -> None:
    """Caja de aviso ('Nota', 'Importante', 'Consejo'): tabla de una celda
    con fondo suave y un borde grueso de color en el lado izquierdo."""
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
    """Línea del índice manual: número en turquesa, texto en azul marino."""
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(10)
    p.paragraph_format.tab_stops.add_tab_stop(Cm(1.2))
    r_num = p.add_run(f"{numero}\t")
    r_num.font.name, r_num.font.size, r_num.font.bold = FONT_NAME, Pt(12), True
    r_num.font.color.rgb = rgb(PALETA.teal)
    r_txt = p.add_run(texto)
    r_txt.font.name, r_txt.font.size = FONT_NAME, Pt(12)
    r_txt.font.color.rgb = rgb(PALETA.navy)


# -- Despachador de bloques ----------------------------------------------------
# Cada entrada de "bloques" en el contenido tiene un campo "tipo"; esta
# función asocia cada tipo con la rutina que sabe dibujarlo. Añadir un
# nuevo tipo de bloque en el futuro solo requiere una función `add_*` y
# una nueva rama aquí.

def _renderizar_bloque(doc: DocumentObject, bloque: dict[str, Any]) -> None:
    tipo = bloque.get("tipo")
    if tipo == "parrafo":
        add_body(doc, bloque["texto"])
    elif tipo == "subtitulo":
        add_heading_2(doc, bloque["texto"])
    elif tipo == "url_destacada":
        add_url_destacada(doc, bloque["texto"])
    elif tipo == "vinetas":
        for item in bloque.get("items", []):
            add_bullet(doc, item)
    elif tipo == "nota":
        add_note_box(doc, bloque.get("titulo", "Nota"), bloque.get("texto", ""), bloque.get("estilo", "teal"))
    elif tipo == "figura":
        add_figure(
            doc,
            bloque.get("image_path", ""),
            bloque.get("ancho_cm") or MAQUETACION.ancho_figura_cm_defecto,
            bloque.get("pie", ""),
        )
    else:
        raise ValueError(f"Tipo de bloque no reconocido: {tipo!r}")


# ==============================================================================
# PORTADA, ÍNDICE Y ENCABEZADO/PIE
# ==============================================================================

def construir_portada(doc: DocumentObject, portada: dict[str, Any]) -> None:
    """Bloque de color con el título del documento, seguido de hasta tres
    líneas de contexto (organización, autoría, fecha…)."""
    doc.add_paragraph().paragraph_format.space_before = Pt(90)

    tabla = doc.add_table(rows=1, cols=1)
    celda = tabla.rows[0].cells[0]
    _set_cell_background(celda, PALETA.navy)
    _set_cell_margins(celda, top=700, bottom=700, left=700, right=700)
    _set_table_borders(tabla, top=None, bottom=None, start=None, end=None, insideH=None, insideV=None)

    def _linea(texto: str, size: int, color: str, bold: bool = False,
               italic: bool = False, space_after: int = 6, primera: bool = False) -> None:
        p = _clear_default_paragraph(celda) if primera else celda.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.space_after = Pt(space_after)
        r = p.add_run(texto)
        r.font.name, r.font.size, r.font.bold, r.font.italic = FONT_NAME, Pt(size), bold, italic
        r.font.color.rgb = rgb(color)

    _linea(portada["kicker"], 11, "BFD7EC", bold=True, space_after=14, primera=True)
    _linea(portada["titulo_linea_1"], 20, "FFFFFF", space_after=4)
    _linea(portada["titulo_linea_2"], 30, "FFFFFF", bold=True, space_after=18)
    _linea(portada["subtitulo"], 12, PALETA.teal_light, italic=True, space_after=0)

    doc.add_paragraph().paragraph_format.space_before = Pt(28)

    lineas_pie = [
        (portada.get("linea_1"), 12, PALETA.navy, True),
        (portada.get("linea_2"), 11, PALETA.navy_soft, False),
        (portada.get("linea_3"), 10, PALETA.gray, False),
    ]
    for texto, size, color, bold in lineas_pie:
        if not texto:
            continue
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.space_after = Pt(2)
        r = p.add_run(texto)
        r.font.name, r.font.size, r.font.bold = FONT_NAME, Pt(size), bold
        r.font.color.rgb = rgb(color)


def construir_indice(doc: DocumentObject, indice: list[dict[str, str]]) -> None:
    """Índice manual (sin campos TOC): siempre se ve correcto, incluso si
    el lector nunca actualiza los campos del documento."""
    add_heading_1(doc, "Índice")
    doc.add_paragraph().paragraph_format.space_after = Pt(4)
    for entrada in indice:
        add_toc_entry(doc, entrada["numero"], entrada["texto"])


def construir_encabezado_pie(section, titulo_documento: str, kicker: str) -> None:
    """Encabezado (kicker + título del documento) y pie de página (número
    de página automático) de una sección de contenido."""
    header_p = _clear_default_paragraph(section.header)
    header_p.paragraph_format.tab_stops.add_tab_stop(Cm(16.5))
    _set_paragraph_bottom_border(header_p, PALETA.gray_light, size=4)
    r1 = header_p.add_run(kicker)
    r1.font.name, r1.font.size = FONT_NAME, Pt(9)
    r1.font.color.rgb = rgb(PALETA.gray)
    r2 = header_p.add_run(f"\t{titulo_documento}")
    r2.font.name, r2.font.size = FONT_NAME, Pt(9)
    r2.font.color.rgb = rgb(PALETA.gray)

    footer_p = _clear_default_paragraph(section.footer)
    footer_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r_pref = footer_p.add_run("Página ")
    r_pref.font.name, r_pref.font.size = FONT_NAME, Pt(9)
    r_pref.font.color.rgb = rgb(PALETA.gray)
    _add_field(footer_p, "PAGE")


# ==============================================================================
# MONTAJE COMPLETO DEL DOCUMENTO
# ==============================================================================

def construir_documento(contenido: dict[str, Any]) -> DocumentObject:
    """Construye el objeto ``Document`` completo a partir del diccionario
    de contenido (portada, índice, secciones con bloques ya resueltos —
    es decir, con ``image_path`` ya asignado en cada bloque de tipo
    "figura").

    Args:
        contenido: Diccionario con las claves ``portada``, ``indice`` y
            ``secciones``, tal como lo produce
            ``content_generator.ContentGenerator.generate`` (tras pasar
            por ``main.resolver_imagenes``).

    Returns:
        Un objeto ``docx.document.Document`` listo para guardarse con
        ``.save(ruta)``.
    """
    doc = Document()

    # --- Sección 1: portada (sin encabezado ni pie) ---------------------------
    seccion_portada = doc.sections[0]
    seccion_portada.page_width = Cm(MAQUETACION.ancho_pagina_cm)
    seccion_portada.page_height = Cm(MAQUETACION.alto_pagina_cm)
    for margen in ("top_margin", "bottom_margin", "left_margin", "right_margin"):
        setattr(seccion_portada, margen, Cm(MAQUETACION.margen_portada_cm))

    estilo_normal = doc.styles["Normal"]
    estilo_normal.font.name = FONT_NAME
    estilo_normal.font.size = Pt(11)

    construir_portada(doc, contenido["portada"])

    # --- Sección 2: contenido (con encabezado, pie y nº de página) -----------
    seccion_contenido = doc.add_section(WD_SECTION.NEW_PAGE)
    seccion_contenido.page_width = Cm(MAQUETACION.ancho_pagina_cm)
    seccion_contenido.page_height = Cm(MAQUETACION.alto_pagina_cm)
    seccion_contenido.top_margin = Cm(MAQUETACION.margen_superior_cm)
    seccion_contenido.bottom_margin = Cm(MAQUETACION.margen_inferior_cm)
    seccion_contenido.left_margin = Cm(MAQUETACION.margen_lateral_cm)
    seccion_contenido.right_margin = Cm(MAQUETACION.margen_lateral_cm)

    _unlink_header_footer(seccion_contenido)
    _restart_page_numbering(seccion_contenido, start=1)

    titulo_documento = " ".join(
        filter(None, [contenido["portada"].get("titulo_linea_1"), contenido["portada"].get("titulo_linea_2")])
    )
    construir_encabezado_pie(seccion_contenido, titulo_documento, contenido["portada"].get("kicker", ""))

    # --- Índice y secciones ----------------------------------------------------
    construir_indice(doc, contenido["indice"])
    doc.add_page_break()

    for seccion in contenido["secciones"]:
        if not isinstance(seccion, dict) or "titulo" not in seccion:
            raise ValueError(
                f"Cada sección debe ser un objeto con 'titulo' y 'bloques'; "
                f"se recibió: {seccion!r}"
            )
        add_heading_1(doc, seccion["titulo"])
        for bloque in seccion.get("bloques", []):
            if not isinstance(bloque, dict) or "tipo" not in bloque:
                raise ValueError(f"Bloque de contenido inválido: {bloque!r}")
            _renderizar_bloque(doc, bloque)

    return doc
