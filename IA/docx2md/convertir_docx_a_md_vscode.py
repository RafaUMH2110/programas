"""
convertir_docx_a_md_vscode.py
====================

VERSIÓN 1 — Pensada para ejecutarse y depurarse directamente desde VS Code
(por ejemplo, pulsando F5 o "Run Python File").

Convierte un documento Word (.docx) con imágenes incrustadas en un archivo
Markdown (.md), transformando los diagramas detectados en bloques de código
Mermaid y organizando el resto de imágenes en una carpeta de salida.

Cómo configurar la ejecución (en este orden de prioridad):

    1. Variables de entorno (útil para "launch.json" de VS Code):
         DOCX_MD_INPUT        -> ruta del .docx de entrada
         DOCX_MD_OUTPUT       -> ruta del .md de salida
         DOCX_MD_IMAGES_DIR   -> carpeta para las imágenes conservadas

    2. Archivo "config_docx_a_md.json" en la misma carpeta que este script (ver
       "config_docx_a_md.ejemplo.json" incluido). Si no existe, se usan valores por
       defecto pensados para pruebas rápidas.

    3. Argumentos de línea de comandos (máxima prioridad), útiles si se
       ejecuta desde la terminal integrada de VS Code.

Ejemplo de "config_docx_a_md.json":
{
    "input": "documentos/manual.docx",
    "output": "salida/manual.md",
    "images_dir": "salida/imagenes",
    "umbral_mermaid": 0.5,
    "usar_ia": true,
    "mantener_temporales": false,
    "verbose": true
}

Requisitos externos (no instalables con pip):
    - Pandoc: https://pandoc.org/installing.html

Requisitos de Python: ver requirements.txt.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from docx_a_md_core import (  # noqa: E402
    ConversionPandocError,
    HerramientaNoEncontradaError,
    procesar_docx_a_markdown,
)


# ---------------------------------------------------------------------------
# Configuración por defecto
# ---------------------------------------------------------------------------

CONFIGURACION_POR_DEFECTO = {
    "input": "/Users/rafa/Programas/tmp/salida/documento_final1.docx",
    "output": "/Users/rafa/Programas/tmp/salida/documento_final1.md",
    "images_dir": "/Users/rafa/Programas/tmp/salida/imagenes",
    "umbral_mermaid": 0.5,
    "usar_ia": True,
    "mantener_temporales": False,
    "verbose": True,
}

RUTA_CONFIG_JSON = Path(__file__).resolve().parent / "config_docx_a_md.json"


def cargar_configuracion() -> dict:
    """
    Construye la configuración final combinando, de menor a mayor prioridad:
        1. Valores por defecto embebidos en este script.
        2. Archivo config_docx_a_md.json (si existe junto a este script).
        3. Variables de entorno DOCX_MD_*.

    Returns:
        Diccionario de configuración ya resuelto.
    """
    config = dict(CONFIGURACION_POR_DEFECTO)

    if RUTA_CONFIG_JSON.exists():
        try:
            with open(RUTA_CONFIG_JSON, "r", encoding="utf-8") as f:
                config.update(json.load(f))
            print(f"ℹ Configuración cargada desde: {RUTA_CONFIG_JSON}")
        except json.JSONDecodeError as exc:
            print(f"⚠ No se pudo leer '{RUTA_CONFIG_JSON}' (JSON inválido): {exc}. Se usan valores por defecto.",
                  file=sys.stderr)
    else:
        print("ℹ No se encontró config_docx_a_md.json; se usan valores por defecto/entorno.")

    if os.environ.get("DOCX_MD_INPUT"):
        config["input"] = os.environ["DOCX_MD_INPUT"]
    if os.environ.get("DOCX_MD_OUTPUT"):
        config["output"] = os.environ["DOCX_MD_OUTPUT"]
    if os.environ.get("DOCX_MD_IMAGES_DIR"):
        config["images_dir"] = os.environ["DOCX_MD_IMAGES_DIR"]

    return config


def parsear_argumentos_opcionales() -> argparse.Namespace:
    """Argumentos opcionales; si se pasan, tienen prioridad máxima sobre config_docx_a_md.json/entorno."""
    parser = argparse.ArgumentParser(
        description="Convierte un .docx con imágenes a Markdown + Mermaid. Uso pensado para VS Code.",
    )
    parser.add_argument("--input", "-i", dest="input", default=None, help="Ruta del .docx de entrada")
    parser.add_argument("--output", "-o", dest="output", default=None, help="Ruta del .md de salida")
    parser.add_argument("--images-dir", dest="images_dir", default=None, help="Carpeta para las imágenes conservadas")
    parser.add_argument("--no-ia", dest="usar_ia", action="store_false", default=None,
                         help="Desactiva el uso de IA con visión, aunque esté disponible")
    parser.add_argument("--verbose", "-v", action="store_true", default=None, help="Salida detallada")
    parser.add_argument("--keep-temp", dest="mantener_temporales", action="store_true", default=None,
                         help="Conserva la carpeta de medios bruta extraída por Pandoc")
    args, _desconocidos = parser.parse_known_args()
    return args


def main() -> int:
    """Punto de entrada principal, pensado para ejecutarse tal cual desde VS Code."""
    print("=" * 70)
    print(" CONVERSOR WORD (.docx) → MARKDOWN + MERMAID  —  Versión VS Code")
    print("=" * 70 + "\n")

    config = cargar_configuracion()
    args = parsear_argumentos_opcionales()

    if args.input is not None:
        config["input"] = args.input
    if args.output is not None:
        config["output"] = args.output
    if args.images_dir is not None:
        config["images_dir"] = args.images_dir
    if args.usar_ia is not None:
        config["usar_ia"] = args.usar_ia
    if args.verbose is not None:
        config["verbose"] = args.verbose
    if args.mantener_temporales is not None:
        config["mantener_temporales"] = args.mantener_temporales

    ruta_docx = Path(config["input"]).expanduser().resolve()
    ruta_md = Path(config["output"]).expanduser().resolve()
    ruta_imagenes = Path(config["images_dir"]).expanduser().resolve()

    print("Configuración efectiva:")
    print(f"  Entrada              : {ruta_docx}")
    print(f"  Salida (Markdown)    : {ruta_md}")
    print(f"  Carpeta de imágenes  : {ruta_imagenes}")
    print(f"  Umbral Mermaid       : {config['umbral_mermaid']}")
    print(f"  Usar IA con visión   : {config['usar_ia']}")
    print(f"  Conservar temporales : {config['mantener_temporales']}")
    print()

    try:
        ruta_final = procesar_docx_a_markdown(
            ruta_docx=ruta_docx,
            ruta_md_salida=ruta_md,
            directorio_imagenes=ruta_imagenes,
            umbral_mermaid=config["umbral_mermaid"],
            usar_ia=config["usar_ia"],
            mantener_temporales=config["mantener_temporales"],
            verbose=config["verbose"],
        )
    except FileNotFoundError as exc:
        print(f"\n✗ ERROR — Archivo no encontrado: {exc}", file=sys.stderr)
        return 1
    except HerramientaNoEncontradaError as exc:
        print(f"\n✗ ERROR — Falta una dependencia externa:\n{exc}", file=sys.stderr)
        return 2
    except ConversionPandocError as exc:
        print(f"\n✗ ERROR — Fallo en la conversión con Pandoc:\n{exc}", file=sys.stderr)
        return 3
    except Exception as exc:  # noqa: BLE001 — feedback amigable ante cualquier fallo inesperado
        print(f"\n✗ ERROR inesperado: {exc}", file=sys.stderr)
        return 99

    print("=" * 70)
    print(f" ✓ ¡Listo! Documento Markdown generado en: {ruta_final}")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    sys.exit(main())
