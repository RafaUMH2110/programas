"""
validators.py
=============
Validación semántica de la configuración ya cargada (`ConfiguracionApp`).

`config.py` se encarga de que todas las claves existan (usando valores por
defecto cuando faltan); este módulo comprueba que los VALORES tengan
sentido: colores en formato hexadecimal válido, URLs bien formadas, modelos
con identificadores no vacíos, formatos de exportación coherentes entre sí,
etc.

Se distingue entre:

  * **Errores** (`ErrorDeValidacion`): impiden generar la aplicación, porque
    producirían un archivo roto o inseguro (por ejemplo, un color inválido
    rompería la hoja de estilos, o una librería necesaria deshabilitada
    dejaría la aplicación sin funcionar). Ante un error, el generador NO
    debe escribir ningún archivo de salida.
  * **Avisos** (devueltos como lista de cadenas): situaciones que no
    impiden generar la aplicación pero que conviene revisar (por ejemplo,
    un modelo con notas vacías, o un tiempo de espera de la API muy alto).
"""
from __future__ import annotations

import re

from .config import ConfiguracionApp

_RE_COLOR_HEX = re.compile(r"^#[0-9A-Fa-f]{6}$")
_RE_URL = re.compile(r"^https?://[^\s]+$")
_RE_NOMBRE_ARCHIVO = re.compile(r'^[^\\/:*?"<>|\r\n]+$')
_RE_ID_MODELO = re.compile(r"^[A-Za-z0-9_.\-]+$")
_RE_FAMILIA_TIPOGRAFICA = re.compile(r"^[A-Za-z0-9\s,'\-]+$")
_RE_MEDIDA_CSS = re.compile(r"^\d+(\.\d+)?(px|rem|em|%)$")
_RE_SOMBRA_CSS = re.compile(r"^[0-9A-Za-z\s,.()#%\-]+$")

FORMATOS_EXPORTACION_VALIDOS = ("markdown", "word", "pdf")
TAMANOS_PAGINA_PDF_VALIDOS = ("a4", "letter", "legal")


class ErrorDeValidacion(Exception):
    """Se lanza cuando la configuración contiene uno o más valores
    inválidos; el mensaje incluye la lista completa de problemas
    encontrados para que se puedan corregir todos de una vez."""


def validar_configuracion(config: ConfiguracionApp) -> list[str]:
    errores: list[str] = []
    advertencias: list[str] = []

    _validar_aplicacion(config, errores)
    ids_modelo = _validar_modelos(config, errores)
    _validar_api(config, errores, advertencias)
    _validar_prompts(config, ids_modelo, errores)
    _validar_tema(config, errores)
    _validar_exports(config, errores)
    _validar_librerias(config, errores, advertencias)

    if errores:
        detalle = "\n".join(f"  - {e}" for e in errores)
        raise ErrorDeValidacion(
            f"Se han encontrado {len(errores)} error(es) en la configuración:\n{detalle}"
        )

    return advertencias


# ---------------------------------------------------------------------------
# Validaciones por sección
# ---------------------------------------------------------------------------

def _validar_aplicacion(config: ConfiguracionApp, errores: list[str]) -> None:
    app = config.aplicacion
    if not app.nombre.strip():
        errores.append("aplicacion.nombre no puede estar vacío.")
    if not app.archivo_salida.strip():
        errores.append("aplicacion.archivo_salida no puede estar vacío.")
    elif not _RE_NOMBRE_ARCHIVO.match(app.archivo_salida):
        errores.append(f"aplicacion.archivo_salida contiene caracteres no válidos: '{app.archivo_salida}'.")
    elif not app.archivo_salida.lower().endswith(".html"):
        errores.append(f"aplicacion.archivo_salida debe terminar en '.html' (valor actual: '{app.archivo_salida}').")


def _validar_modelos(config: ConfiguracionApp, errores: list[str]) -> set[str]:
    modelos = config.modelos
    if not modelos.disponibles:
        errores.append("modelos.disponibles no puede estar vacío: define al menos un modelo.")
        return set()

    ids_vistos: set[str] = set()
    for modelo in modelos.disponibles:
        if not modelo.id.strip():
            errores.append("Hay un modelo sin 'id'.")
            continue
        if not _RE_ID_MODELO.match(modelo.id):
            errores.append(f"El id de modelo '{modelo.id}' contiene caracteres no permitidos.")
        if modelo.id in ids_vistos:
            errores.append(f"El id de modelo '{modelo.id}' está repetido.")
        ids_vistos.add(modelo.id)
        if not modelo.nombre.strip():
            errores.append(f"El modelo '{modelo.id}' no tiene 'nombre'.")
        if modelo.max_output_tokens <= 0:
            errores.append(f"El modelo '{modelo.id}' debe tener max_output_tokens > 0.")

    if modelos.modelo_por_defecto not in ids_vistos:
        errores.append(
            f"modelos.modelo_por_defecto ('{modelos.modelo_por_defecto}') "
            f"no coincide con ningún id de modelos.disponibles."
        )

    return ids_vistos


def _validar_api(config: ConfiguracionApp, errores: list[str], advertencias: list[str]) -> None:
    api = config.api
    if not _RE_URL.match(api.endpoint):
        errores.append(f"api.endpoint no es una URL http(s) válida: '{api.endpoint}'.")
    if api.timeout_segundos <= 0:
        errores.append("api.timeout_segundos debe ser mayor que 0.")
    elif api.timeout_segundos > 300:
        advertencias.append("api.timeout_segundos es muy alto (> 300 s); considera reducirlo.")
    if api.reintentos < 0:
        errores.append("api.reintentos no puede ser negativo.")
    elif api.reintentos > 5:
        advertencias.append("api.reintentos es muy alto (> 5); las peticiones fallidas tardarán mucho en agotarse.")
    if not api.api_key_env.strip():
        advertencias.append("api.api_key_env está vacío; se usará únicamente el campo de clave del navegador.")


def _validar_prompts(config: ConfiguracionApp, ids_modelo: set[str], errores: list[str]) -> None:
    for etiqueta, prompt in (("prompts.mejora", config.prompts.mejora), ("prompts.final", config.prompts.final)):
        if not prompt.system.strip():
            errores.append(f"{etiqueta}.system no puede estar vacío.")
        if not prompt.user.strip():
            errores.append(f"{etiqueta}.user no puede estar vacío.")
        if prompt.max_tokens <= 0:
            errores.append(f"{etiqueta}.max_tokens debe ser mayor que 0.")
        if prompt.temperature is not None and not (0.0 <= prompt.temperature <= 1.0):
            errores.append(f"{etiqueta}.temperature debe estar entre 0.0 y 1.0.")
        if prompt.modelo and ids_modelo and prompt.modelo not in ids_modelo:
            errores.append(f"{etiqueta}.modelo ('{prompt.modelo}') no coincide con ningún id de modelos.disponibles.")


def _validar_tema(config: ConfiguracionApp, errores: list[str]) -> None:
    tema = config.tema
    colores = {
        "tema.color_primario": tema.color_primario,
        "tema.color_primario_hover": tema.color_primario_hover,
        "tema.color_secundario": tema.color_secundario,
        "tema.color_fondo": tema.color_fondo,
        "tema.color_texto": tema.color_texto,
        "tema.color_texto_tenue": tema.color_texto_tenue,
        "tema.color_borde": tema.color_borde,
        "tema.color_acento": tema.color_acento,
    }
    for nombre_campo, valor in colores.items():
        if not _RE_COLOR_HEX.match(valor):
            errores.append(f"{nombre_campo} debe ser un color hexadecimal de 6 dígitos, p. ej. '#2E6DA4' (valor actual: '{valor}').")

    for nombre_campo, valor in (
        ("tema.familia_tipografica", tema.familia_tipografica),
        ("tema.familia_monoespaciada", tema.familia_monoespaciada),
    ):
        if not valor.strip():
            errores.append(f"{nombre_campo} no puede estar vacío.")
        elif not _RE_FAMILIA_TIPOGRAFICA.match(valor):
            errores.append(
                f"{nombre_campo} contiene caracteres no permitidos: '{valor}' "
                f"(solo se permiten letras, números, espacios, comas, apóstrofos y guiones)."
            )

    if not _RE_MEDIDA_CSS.match(tema.ancho_maximo):
        errores.append(f"tema.ancho_maximo debe ser una medida CSS simple, p. ej. '980px' (valor actual: '{tema.ancho_maximo}').")
    if not _RE_MEDIDA_CSS.match(tema.radio_borde):
        errores.append(f"tema.radio_borde debe ser una medida CSS simple, p. ej. '14px' (valor actual: '{tema.radio_borde}').")
    if not _RE_SOMBRA_CSS.match(tema.sombra):
        errores.append("tema.sombra contiene caracteres no permitidos para una declaración 'box-shadow'.")


def _validar_exports(config: ConfiguracionApp, errores: list[str]) -> None:
    exports = config.exports
    activos = {
        "markdown": exports.markdown.activo,
        "word": exports.word.activo,
        "pdf": exports.pdf.activo,
    }

    if exports.formato_por_defecto not in FORMATOS_EXPORTACION_VALIDOS:
        errores.append(
            f"exports.formato_por_defecto debe ser uno de {FORMATOS_EXPORTACION_VALIDOS} "
            f"(valor actual: '{exports.formato_por_defecto}')."
        )
    elif not activos[exports.formato_por_defecto]:
        errores.append(
            f"exports.formato_por_defecto ('{exports.formato_por_defecto}') "
            f"no puede ser un formato que esté desactivado (exports.{exports.formato_por_defecto}.activo: false)."
        )

    if config.visibilidad.mostrar_exportacion and not any(activos.values()):
        errores.append(
            "visibilidad.mostrar_exportacion es 'true' pero no hay ningún formato de "
            "exportación activo (exports.markdown/word/pdf.activo son todos 'false')."
        )

    if not _RE_NOMBRE_ARCHIVO.match(exports.nombre_archivo_por_defecto):
        errores.append(f"exports.nombre_archivo_por_defecto contiene caracteres no válidos: '{exports.nombre_archivo_por_defecto}'.")

    if exports.pdf_tamano_pagina not in TAMANOS_PAGINA_PDF_VALIDOS:
        errores.append(f"exports.pdf_tamano_pagina debe ser uno de {TAMANOS_PAGINA_PDF_VALIDOS}.")
    if exports.pdf_margen_pt <= 0:
        errores.append("exports.pdf_margen_pt debe ser mayor que 0.")
    if exports.word_tamano_fuente_pt <= 0:
        errores.append("exports.word_tamano_fuente_pt debe ser mayor que 0.")
    if not exports.word_fuente.strip() or not _RE_FAMILIA_TIPOGRAFICA.match(exports.word_fuente):
        errores.append(f"exports.word_fuente no es un nombre de fuente válido: '{exports.word_fuente}'.")


def _validar_librerias(config: ConfiguracionApp, errores: list[str], advertencias: list[str]) -> None:
    librerias = config.librerias

    # marked y DOMPurify son imprescindibles: sin la primera no se puede
    # mostrar el resultado como Markdown; sin la segunda, el HTML generado
    # a partir de la respuesta de la IA no estaría saneado (riesgo de XSS).
    if not librerias.markdown.activa:
        errores.append("librerias.markdown.activa no puede ser 'false': es imprescindible para mostrar el resultado.")
    if not librerias.sanitizador.activa:
        errores.append(
            "librerias.sanitizador.activa no puede ser 'false': sin ella, el HTML generado "
            "a partir de la respuesta de la IA no se sanearía antes de mostrarse (riesgo de XSS)."
        )

    if config.exports.word.activo and not librerias.docx.activa:
        errores.append("exports.word.activo es 'true' pero librerias.docx.activa es 'false'.")
    if config.exports.pdf.activo and not librerias.jspdf.activa:
        errores.append("exports.pdf.activo es 'true' pero librerias.jspdf.activa es 'false'.")

    for nombre, libreria in (
        ("librerias.markdown", librerias.markdown),
        ("librerias.sanitizador", librerias.sanitizador),
        ("librerias.docx", librerias.docx),
        ("librerias.jspdf", librerias.jspdf),
    ):
        if libreria.activa and not _RE_URL.match(libreria.url):
            errores.append(f"{nombre}.url no es una URL http(s) válida: '{libreria.url}'.")
        if libreria.activa and "cdn" not in libreria.url and "jsdelivr" not in libreria.url and "cloudflare" not in libreria.url:
            advertencias.append(f"{nombre}.url no apunta a un CDN habitual; comprueba que el enlace es correcto y estable.")
