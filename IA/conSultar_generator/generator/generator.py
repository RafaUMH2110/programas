"""
generator.py
============
Orquesta el proceso completo de generación de la aplicación ConSultar:

    1. Cargar la configuración (config.cargar_configuracion).
    2. Validarla (validators.validar_configuracion).
    3. Renderizar las plantillas (templates.renderizar_aplicacion).
    4. Escribir el archivo HTML resultante en disco.

Este módulo es intencionadamente el único punto de la aplicación que
combina los tres anteriores: `config.py`, `validators.py` y `templates.py`
no se conocen entre sí, lo que facilita probarlos (y sustituirlos) por
separado — ver `tests/`.
"""
from __future__ import annotations

import logging
from pathlib import Path

from .config import ErrorDeConfiguracion, cargar_configuracion
from .templates import renderizar_aplicacion
from .validators import ErrorDeValidacion, validar_configuracion

logger = logging.getLogger("consultar_generator")


class ErrorDeGeneracion(Exception):
    """Error irrecuperable durante el proceso de generación; el mensaje ya
    está redactado en español y listo para mostrarse al usuario final tal
    cual, sin necesidad de traza técnica adicional."""


def generar_aplicacion(
    ruta_config: Path,
    directorio_salida_override: Path | None = None,
    solo_validar: bool = False,
) -> Path | None:
    """Ejecuta el proceso completo de generación.

    Parameters
    ----------
    ruta_config:
        Ruta al archivo de configuración (.yaml, .yml o .json).
    directorio_salida_override:
        Si se indica, sustituye a `aplicacion.directorio_salida` de la
        configuración (equivale a la opción --output de la línea de
        comandos).
    solo_validar:
        Si es True, se carga y valida la configuración pero NO se genera
        ningún archivo (equivale a la opción --validate).

    Returns
    -------
    La ruta del archivo HTML generado, o `None` si `solo_validar` es True.

    Raises
    ------
    ErrorDeGeneracion
        Si la configuración no se puede cargar o no es válida. Nunca se
        escribe un archivo de salida parcial o incompleto: la escritura en
        disco es la última operación de todo el proceso.
    """
    logger.info("Cargando configuración desde: %s", ruta_config)
    try:
        config = cargar_configuracion(ruta_config)
    except ErrorDeConfiguracion as exc:
        raise ErrorDeGeneracion(f"No se pudo cargar la configuración:\n{exc}") from exc

    logger.info("Validando configuración…")
    try:
        advertencias = validar_configuracion(config)
    except ErrorDeValidacion as exc:
        raise ErrorDeGeneracion(f"La configuración no es válida:\n{exc}") from exc

    for advertencia in advertencias:
        logger.warning("Aviso: %s", advertencia)

    logger.info(
        "Configuración válida: %d modelo(s) disponible(s), %d aviso(s).",
        len(config.modelos.disponibles),
        len(advertencias),
    )

    if solo_validar:
        logger.info("Modo --validate: no se generará ningún archivo.")
        return None

    logger.info("Renderizando la aplicación web «%s»…", config.aplicacion.nombre)
    try:
        html = renderizar_aplicacion(config)
    except Exception as exc:  # las plantillas pueden fallar por muchos motivos (Jinja2, etc.)
        raise ErrorDeGeneracion(f"No se pudo renderizar la plantilla de la aplicación:\n{exc}") from exc

    directorio_salida = directorio_salida_override or Path(config.aplicacion.directorio_salida)
    try:
        directorio_salida.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise ErrorDeGeneracion(f"No se pudo crear el directorio de salida '{directorio_salida}':\n{exc}") from exc

    ruta_salida = directorio_salida / config.aplicacion.archivo_salida
    try:
        ruta_salida.write_text(html, encoding="utf-8")
    except OSError as exc:
        raise ErrorDeGeneracion(f"No se pudo escribir el archivo de salida '{ruta_salida}':\n{exc}") from exc

    tamano_kb = ruta_salida.stat().st_size / 1024
    logger.info("Aplicación generada correctamente en: %s (%.1f KB)", ruta_salida, tamano_kb)
    return ruta_salida
