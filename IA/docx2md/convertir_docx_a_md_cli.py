#!/usr/bin/env python3
"""
convertir_docx_a_md_cli.py
=================

VERSIÓN 2 — Interfaz de línea de comandos (CLI) para convertir un documento
Word (.docx) con imágenes incrustadas en un archivo Markdown (.md), con
detección automática de diagramas y su conversión a sintaxis Mermaid.

Uso básico:

    python convertir_docx_a_md_cli.py -i entrada.docx -o salida.md

Uso completo:

    python convertir_docx_a_md_cli.py \\
        --input entrada.docx \\
        --output salida/documento.md \\
        --images-dir salida/imagenes \\
        --mermaid-threshold 0.5 \\
        --no-ia \\
        --keep-temp \\
        --verbose

Requisitos externos (no instalables con pip):
    - Pandoc: https://pandoc.org/installing.html

Requisitos de Python: ver requirements.txt.

Códigos de salida:
    0  Éxito
    1  Archivo de entrada no encontrado
    2  Falta una dependencia externa (Pandoc)
    3  Error en la conversión con Pandoc
    5  Argumentos inválidos
    99 Error inesperado
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from docx_a_md_core import (  # noqa: E402
    ConversionPandocError,
    HerramientaNoEncontradaError,
    procesar_docx_a_markdown,
)

__version__ = "1.0.0"


def construir_parser() -> argparse.ArgumentParser:
    """Define y documenta todos los argumentos disponibles de la CLI."""
    parser = argparse.ArgumentParser(
        prog="convertir_docx_a_md_cli.py",
        description=(
            "Convierte un documento Word (.docx) con imágenes incrustadas en un archivo "
            "Markdown (.md), transformando los diagramas detectados en bloques Mermaid."
        ),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        epilog="Dependencia externa requerida: Pandoc (https://pandoc.org/installing.html).",
    )

    parser.add_argument("--input", "-i", required=True, type=Path, help="Ruta del documento Word (.docx) de entrada.")
    parser.add_argument("--output", "-o", required=True, type=Path, help="Ruta del archivo Markdown (.md) de salida.")
    parser.add_argument(
        "--images-dir",
        dest="images_dir",
        type=Path,
        default=None,
        help="Carpeta donde guardar las imágenes que NO se conviertan a Mermaid "
             "(por defecto, 'imagenes' junto al archivo .md de salida).",
    )
    parser.add_argument(
        "--mermaid-threshold",
        dest="umbral_mermaid",
        type=float,
        default=0.5,
        help="Sensibilidad (0.0-1.0) de la heurística de detección de diagramas. "
             "Valores más altos exigen que la imagen 'parezca' más claramente un diagrama.",
    )
    parser.add_argument(
        "--no-ia",
        dest="usar_ia",
        action="store_false",
        help="Desactiva el uso de IA con visión (Anthropic) para la conversión a Mermaid, "
             "usando siempre el esqueleto heurístico aproximado.",
    )
    parser.add_argument(
        "--keep-temp",
        dest="mantener_temporales",
        action="store_true",
        help="Conserva la carpeta de medios bruta extraída por Pandoc (no la borra al finalizar).",
    )
    parser.add_argument("--verbose", "-v", action="store_true", help="Muestra información detallada de cada paso.")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.set_defaults(usar_ia=True)
    return parser


def validar_argumentos(args: argparse.Namespace) -> None:
    """Validaciones adicionales que argparse no puede expresar de forma declarativa."""
    errores = []

    if args.input.suffix.lower() != ".docx":
        errores.append(f"El archivo de entrada debería tener extensión .docx (recibido: {args.input.suffix})")

    if args.output.suffix.lower() not in (".md", ".markdown"):
        errores.append(f"El archivo de salida debería tener extensión .md (recibido: {args.output.suffix})")

    if not (0.0 <= args.umbral_mermaid <= 1.0):
        errores.append("--mermaid-threshold debe estar entre 0.0 y 1.0")

    if errores:
        print("✗ Argumentos inválidos:", file=sys.stderr)
        for err in errores:
            print(f"  - {err}", file=sys.stderr)
        sys.exit(5)


def main() -> int:
    """Punto de entrada de la CLI."""
    parser = construir_parser()
    args = parser.parse_args()
    validar_argumentos(args)

    print("=" * 70)
    print(" CONVERSOR WORD (.docx) → MARKDOWN + MERMAID  —  Versión CLI")
    print("=" * 70 + "\n")

    ruta_docx = args.input.expanduser().resolve()
    ruta_md = args.output.expanduser().resolve()
    ruta_imagenes = (
        args.images_dir.expanduser().resolve()
        if args.images_dir is not None
        else ruta_md.parent / "imagenes"
    )

    if args.verbose:
        print("Parámetros:")
        print(f"  Entrada              : {ruta_docx}")
        print(f"  Salida (Markdown)    : {ruta_md}")
        print(f"  Carpeta de imágenes  : {ruta_imagenes}")
        print(f"  Umbral Mermaid       : {args.umbral_mermaid}")
        print(f"  Usar IA con visión   : {args.usar_ia}")
        print(f"  Conservar temporales : {args.mantener_temporales}")
        print()

    try:
        ruta_final = procesar_docx_a_markdown(
            ruta_docx=ruta_docx,
            ruta_md_salida=ruta_md,
            directorio_imagenes=ruta_imagenes,
            umbral_mermaid=args.umbral_mermaid,
            usar_ia=args.usar_ia,
            mantener_temporales=args.mantener_temporales,
            verbose=args.verbose,
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
    except Exception as exc:  # noqa: BLE001 — red de seguridad ante fallos no previstos
        print(f"\n✗ ERROR inesperado: {exc}", file=sys.stderr)
        return 99

    print("=" * 70)
    print(f" ✓ ¡Listo! Documento Markdown generado en: {ruta_final}")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    sys.exit(main())
