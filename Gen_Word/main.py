#!/usr/bin/env python3
"""
main.py
================================================================================
Punto de entrada del generador de documentos Word de propósito general.

Uso típico desde VSCode / terminal:

    python main.py --tema "La fotosíntesis"
    python main.py --tema "Guía de onboarding" --secciones 5 --idioma "inglés"
    python main.py            # modo interactivo: pregunta el tema por consola

Este archivo solo ORQUESTA tres pasos, cada uno delegado en su propio
módulo (separación de responsabilidades):

    1. content_generator.ContentGenerator.generate(tema)
           → dict con portada, índice y secciones (bloques con
             "image_query" en vez de imágenes reales).

    2. resolver_imagenes(contenido, image_service)
           → recorre los bloques de tipo "figura" y sustituye cada
             "image_query" por un "image_path" real (descargado o
             generado localmente por ImageService).

    3. document_builder.construir_documento(contenido)
           → objeto Document listo para guardar en disco.

No contiene lógica de negocio propia más allá de esa orquestación y del
manejo de errores de cara al usuario final.
================================================================================
"""

from __future__ import annotations

import argparse
import logging
import os
import re
import sys
from typing import Any

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

import config
import document_builder
from content_generator import ContentGenerationError, ContentGenerator
from image_service import ImageService, ImageServiceConfig

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("main")


# ==============================================================================
# RESOLUCIÓN DE IMÁGENES
# ==============================================================================

def resolver_imagenes(contenido: dict[str, Any], image_service: ImageService) -> None:
    """Sustituye, en cada bloque de tipo "figura", la clave ``image_query``
    (una descripción textual, generada por la IA) por ``image_path`` (una
    ruta de archivo real en disco).

    Modifica ``contenido`` in-place. Cualquier fallo al resolver una imagen
    concreta se registra como aviso y esa figura simplemente se queda sin
    imagen (ver ``document_builder.add_figure``, que en ese caso solo
    muestra el pie de figura) — un problema con una imagen no debe tirar
    abajo la generación de todo el documento.
    """
    indice_figura = 0
    for seccion in contenido.get("secciones", []):
        if not isinstance(seccion, dict):
            logger.warning(
                "Se esperaba un objeto de sección con 'bloques' y se encontró "
                "%s; se omite (%r).", type(seccion).__name__, seccion,
            )
            continue
        for bloque in seccion.get("bloques", []):
            if not isinstance(bloque, dict):
                logger.warning(
                    "Se esperaba un objeto de bloque y se encontró %s; se omite (%r).",
                    type(bloque).__name__, bloque,
                )
                continue
            if bloque.get("tipo") != "figura":
                continue
            consulta = bloque.get("image_query", "").strip()
            if not consulta:
                logger.warning("Bloque de figura sin 'image_query'; se omite la imagen.")
                bloque["image_path"] = ""
                continue
            try:
                bloque["image_path"] = image_service.obtener_imagen(consulta, indice_figura=indice_figura)
            except Exception as exc:  # noqa: BLE001
                logger.warning("No se pudo resolver la imagen para %r: %s", consulta, exc)
                bloque["image_path"] = ""
            indice_figura += 1


# ==============================================================================
# UTILIDADES DE CLI
# ==============================================================================

def _slug(texto: str) -> str:
    """Convierte un tema en un nombre de archivo seguro (sin espacios ni
    caracteres especiales), p. ej. 'La fotosíntesis' → 'la-fotosintesis'."""
    texto = texto.strip().lower()
    texto = re.sub(r"[^\w\s-]", "", texto, flags=re.UNICODE)
    texto = re.sub(r"[\s_]+", "-", texto)
    return texto.strip("-") or "documento"


def _parsear_argumentos() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Genera un documento Word (.docx) profesional sobre cualquier tema."
    )
    parser.add_argument("--tema", type=str, default=None, help="Tema del documento.")
    parser.add_argument("--idioma", type=str, default=None, help="Idioma de redacción (por defecto, español de España).")
    parser.add_argument("--tono", type=str, default=None, help="Tono/registro del texto.")
    parser.add_argument("--audiencia", type=str, default=None, help="Público al que va dirigido el documento.")
    parser.add_argument("--secciones", type=int, default=None, help="Número de secciones a generar (por defecto, 6).")
    parser.add_argument(
        "--instrucciones", type=str, default=None,
        help="Instrucciones adicionales en texto libre (p. ej. 'incluye un apartado de bibliografía').",
    )
    parser.add_argument(
        "--salida", type=str, default=None,
        help="Ruta del archivo .docx de salida (por defecto, ./salida/<tema>.docx).",
    )
    return parser.parse_args()


# ==============================================================================
# PUNTO DE ENTRADA
# ==============================================================================

def main() -> int:
    args = _parsear_argumentos()

    tema = args.tema or input("¿Sobre qué tema quieres generar el documento?\n> ").strip()
    if not tema:
        logger.error("No se ha indicado ningún tema. Abortando.")
        return 1

    # --- Comprobación temprana de la API key ---------------------------------
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        logger.error(
            "Falta la variable de entorno ANTHROPIC_API_KEY. Consulta el "
            "README.md para saber cómo configurarla."
        )
        return 1

    os.makedirs(config.OUTPUT_DIR, exist_ok=True)

    # --- Paso 1: generar el contenido con la IA ------------------------------
    try:
        logger.info("Generando el contenido del documento sobre %r…", tema)
        generador = ContentGenerator(api_key=api_key)
        contenido = generador.generate(
            tema,
            idioma=args.idioma,
            tono=args.tono,
            audiencia=args.audiencia,
            num_secciones=args.secciones,
            instrucciones_adicionales=args.instrucciones,
        )
    except ContentGenerationError as exc:
        logger.error("No se pudo generar el contenido: %s", exc)
        return 1

    # --- Paso 2: resolver las imágenes ----------------------------------------
    logger.info("Buscando y descargando imágenes…")
    servicio_imagenes = ImageService(
        ImageServiceConfig(
            unsplash_access_key=os.environ.get("UNSPLASH_ACCESS_KEY"),
            pexels_api_key=os.environ.get("PEXELS_API_KEY"),
        )
    )
    resolver_imagenes(contenido, servicio_imagenes)

    # --- Paso 3: maquetar el documento Word -----------------------------------
    logger.info("Maquetando el documento Word…")
    try:
        documento = document_builder.construir_documento(contenido)
    except (KeyError, ValueError) as exc:
        logger.error(
            "El contenido generado no tiene el formato esperado (%s). "
            "Puede deberse a una respuesta inusual del modelo; prueba a "
            "ejecutar de nuevo.", exc,
        )
        return 1

    ruta_salida = args.salida or os.path.join(config.OUTPUT_DIR, f"{_slug(tema)}.docx")
    os.makedirs(os.path.dirname(os.path.abspath(ruta_salida)), exist_ok=True)
    documento.save(ruta_salida)

    logger.info("✅ Documento generado correctamente en: %s", ruta_salida)
    return 0


if __name__ == "__main__":
    sys.exit(main())
