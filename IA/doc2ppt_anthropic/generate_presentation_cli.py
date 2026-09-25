#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
generate_presentation_cli.py
=============================

Herramienta de línea de comandos para generar, a partir de un documento
.docx, una presentación .pptx con el mismo estilo visual "Editorial
Noir / Automatización Industrial" (fondo oscuro en portada/cierre,
fondo claro en el contenido, acentos en ámbar y turquesa, iconos en
círculo, diagramas de proceso y diagramas GRAFCET), utilizando un LLM
(API de Anthropic — Claude) para estructurar el contenido.

------------------------------------------------------------------
REQUISITOS (contenido sugerido de requirements.txt):

    python-pptx>=0.6.23
    python-docx>=1.1.0
    anthropic>=0.34.0

Instalación:
    pip install -r requirements.txt

------------------------------------------------------------------
VARIABLES DE ENTORNO NECESARIAS:

    ANTHROPIC_API_KEY   Clave de la API de Anthropic (obligatoria).
                         Se obtiene en https://console.anthropic.com

------------------------------------------------------------------
EJEMPLOS DE USO:

    # Uso básico
    python generate_presentation_cli.py --input practica.docx --output presentacion.pptx

    # Especificando modelo, tokens y temperatura
    python generate_presentation_cli.py \\
        --input practica.docx \\
        --output presentacion.pptx \\
        --model claude-sonnet-5 \\
        --max-tokens 16000 \\
        --temperature 0.4

    # Guardando también el JSON intermedio generado por el LLM
    python generate_presentation_cli.py -i practica.docx -o salida.pptx --save-json

    # Modo detallado (debug)
    python generate_presentation_cli.py -i practica.docx -o salida.pptx --verbose

------------------------------------------------------------------
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

from generate_pptx_common import (
    ConfiguracionLLM,
    configurar_logging,
    generar_presentacion_desde_docx,
)

logger = logging.getLogger("grafcet_pptx")


def construir_parser() -> argparse.ArgumentParser:
    """Construye y devuelve el parser de argumentos de la herramienta CLI."""
    parser = argparse.ArgumentParser(
        prog="generate_presentation_cli.py",
        description=(
            "Genera una presentación .pptx con estilo académico profesional "
            "a partir de un documento .docx, utilizando un modelo de "
            "lenguaje (API de Anthropic — Claude) para estructurar el contenido."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Ejemplo:\n"
            "  python generate_presentation_cli.py -i practica.docx "
            "-o presentacion.pptx --model claude-sonnet-5 --max-tokens 16000\n"
        ),
    )

    parser.add_argument(
        "-i", "--input",
        dest="ruta_entrada",
        type=Path,
        required=True,
        help="Ruta al archivo .docx de origen (obligatorio).",
    )
    parser.add_argument(
        "-o", "--output",
        dest="ruta_salida",
        type=Path,
        required=True,
        help="Ruta del archivo .pptx que se generará (obligatorio).",
    )
    parser.add_argument(
        "--model",
        dest="modelo",
        type=str,
        default="claude-sonnet-5",
        help=(
            "Modelo de Claude (Anthropic) a utilizar (por defecto: "
            "'claude-sonnet-5'). Otras opciones habituales: "
            "'claude-opus-4-8' (máxima calidad) o "
            "'claude-haiku-4-5-20251001' (más rápido y económico)."
        ),
    )
    parser.add_argument(
        "--max-tokens",
        dest="max_tokens",
        type=int,
        default=16000,
        help="Máximo de tokens de salida para la respuesta del LLM (por defecto: 16000).",
    )
    parser.add_argument(
        "--temperature",
        dest="temperatura",
        type=float,
        default=0.4,
        help="Temperatura de generación del LLM, entre 0.0 y 1.0 (por defecto: 0.4).",
    )
    parser.add_argument(
        "--retries",
        dest="intentos_maximos",
        type=int,
        default=3,
        help="Número máximo de reintentos ante fallos del LLM (por defecto: 3).",
    )
    parser.add_argument(
        "--save-json",
        dest="guardar_json",
        action="store_true",
        help="Guarda también el JSON intermedio generado por el LLM junto al .pptx.",
    )
    parser.add_argument(
        "-v", "--verbose",
        dest="verbose",
        action="store_true",
        help="Activa mensajes de depuración detallados (nivel DEBUG).",
    )

    return parser


def validar_argumentos(args: argparse.Namespace) -> None:
    """Valida los argumentos recibidos y lanza ``SystemExit`` con un
    mensaje claro en caso de error.
    """
    if not args.ruta_entrada.exists():
        logger.error("El archivo de entrada no existe: %s", args.ruta_entrada)
        raise SystemExit(2)

    if args.ruta_entrada.suffix.lower() != ".docx":
        logger.error("El archivo de entrada debe tener extensión .docx: %s", args.ruta_entrada)
        raise SystemExit(2)

    if args.ruta_salida.suffix.lower() != ".pptx":
        logger.error("El archivo de salida debe tener extensión .pptx: %s", args.ruta_salida)
        raise SystemExit(2)

    if not 0.0 <= args.temperatura <= 1.0:
        logger.error("La temperatura debe estar entre 0.0 y 1.0 (valor recibido: %s).", args.temperatura)
        raise SystemExit(2)

    if args.max_tokens <= 0:
        logger.error("El número máximo de tokens debe ser positivo (valor recibido: %s).", args.max_tokens)
        raise SystemExit(2)


def main(argv: list[str] | None = None) -> int:
    """Punto de entrada principal de la herramienta CLI.

    Parameters
    ----------
    argv:
        Lista de argumentos (útil para pruebas). Si es ``None``, se
        toman de ``sys.argv``.

    Returns
    -------
    int
        Código de salida del proceso (0 = éxito).
    """
    parser = construir_parser()
    args = parser.parse_args(argv)

    configurar_logging(logging.DEBUG if args.verbose else logging.INFO)

    logger.info("=" * 70)
    logger.info("GENERADOR DE PRESENTACIONES — HERRAMIENTA CLI")
    logger.info("=" * 70)

    validar_argumentos(args)

    if not os.environ.get("ANTHROPIC_API_KEY"):
        logger.error(
            "No se ha encontrado la variable de entorno ANTHROPIC_API_KEY. "
            "Expórtala antes de ejecutar este script, por ejemplo:\n"
            "  export ANTHROPIC_API_KEY='sk-ant-...'   (Linux/macOS)\n"
            "  setx ANTHROPIC_API_KEY \"sk-ant-...\"     (Windows)"
        )
        return 1

    logger.info("Archivo de entrada (.docx): %s", args.ruta_entrada.resolve())
    logger.info("Archivo de salida (.pptx):  %s", args.ruta_salida.resolve())
    logger.info(
        "Modelo LLM: %s | max_tokens=%d | temperatura=%.2f | reintentos=%d",
        args.modelo, args.max_tokens, args.temperatura, args.intentos_maximos,
    )

    config_llm = ConfiguracionLLM(
        modelo=args.modelo,
        max_tokens=args.max_tokens,
        temperatura=args.temperatura,
        intentos_maximos=args.intentos_maximos,
    )

    try:
        ruta_final = generar_presentacion_desde_docx(
            ruta_docx=args.ruta_entrada,
            ruta_pptx=args.ruta_salida,
            config_llm=config_llm,
            guardar_json_intermedio=args.guardar_json,
        )
    except FileNotFoundError as error:
        logger.error("Archivo no encontrado: %s", error)
        return 1
    except RuntimeError as error:
        logger.error("Error durante la generación con el LLM: %s", error)
        return 1
    except Exception as error:  # noqa: BLE001 — cualquier fallo inesperado queda registrado
        logger.exception("Error inesperado durante la generación: %s", error)
        return 1

    logger.info("=" * 70)
    logger.info("¡Proceso completado con éxito!")
    logger.info("Presentación disponible en: %s", ruta_final.resolve())
    logger.info("=" * 70)
    return 0


if __name__ == "__main__":
    sys.exit(main())
