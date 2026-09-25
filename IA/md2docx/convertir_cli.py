#!/usr/bin/env python3
"""
convertir_cli.py
=================

VERSIÓN 2 — Interfaz de línea de comandos (CLI) para convertir un Markdown
con diagramas Mermaid en un documento Word (.docx) en español (es-ES).

Uso básico:

    python convertir_cli.py -i entrada.md -o salida.docx

Uso completo:

    python convertir_cli.py \\
        --input entrada.md \\
        --output salida.docx \\
        --theme neutral \\
        --width 1400 --height 900 --scale 2.5 \\
        --background white \\
        --lang es-ES \\
        --reference-doc plantilla_corporativa.docx \\
        --keep-temp \\
        --verbose

Requisitos externos (no instalables con pip):
    - Pandoc      : https://pandoc.org/installing.html
    - Mermaid CLI : npm install -g @mermaid-js/mermaid-cli

Requisitos de Python: ver requirements.txt (python-docx).

Códigos de salida:
    0  Éxito
    1  Archivo de entrada no encontrado
    2  Falta una dependencia externa (Pandoc/mmdc)
    3  Error al renderizar un diagrama Mermaid
    4  Error en la conversión con Pandoc
    5  Argumentos inválidos
    99 Error inesperado
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from mermaid_docx_core import (  # noqa: E402
    TAMANOS_PAGINA_CM,
    TEMAS_VALIDOS,
    ConversionPandocError,
    HerramientaNoEncontradaError,
    RenderizadoMermaidError,
    procesar_markdown_a_docx,
)

__version__ = "1.0.0"


def construir_parser() -> argparse.ArgumentParser:
    """Define y documenta todos los argumentos disponibles de la CLI."""
    parser = argparse.ArgumentParser(
        prog="convertir_cli.py",
        description=(
            "Convierte un archivo Markdown con diagramas Mermaid en un "
            "documento Word (.docx) en español (es-ES), renderizando cada "
            "diagrama como imagen PNG de alta calidad."
        ),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        epilog=(
            "Dependencias externas requeridas: Pandoc y Mermaid CLI (mmdc).\n"
            "Instala Mermaid CLI con: npm install -g @mermaid-js/mermaid-cli"
        ),
    )

    parser.add_argument(
        "--input", "-i",
        required=True,
        type=Path,
        help="Ruta del archivo Markdown (.md) de entrada.",
    )
    parser.add_argument(
        "--output", "-o",
        required=True,
        type=Path,
        help="Ruta del archivo Word (.docx) de salida.",
    )
    parser.add_argument(
        "--theme",
        dest="tema",
        default="default",
        choices=sorted(TEMAS_VALIDOS),
        help="Tema visual de los diagramas Mermaid.",
    )
    parser.add_argument(
        "--width",
        dest="ancho",
        type=int,
        default=1200,
        help="Ancho en píxeles del lienzo de renderizado de cada diagrama.",
    )
    parser.add_argument(
        "--height",
        dest="alto",
        type=int,
        default=800,
        help="Alto en píxeles del lienzo de renderizado de cada diagrama.",
    )
    parser.add_argument(
        "--scale",
        dest="escala",
        type=float,
        default=2.0,
        help="Factor de escala para aumentar la resolución final (nitidez de imagen).",
    )
    parser.add_argument(
        "--background",
        dest="fondo",
        default="white",
        help='Color de fondo de los diagramas ("white", "transparent", "#RRGGBB"...).',
    )
    parser.add_argument(
        "--lang",
        dest="idioma",
        default="es-ES",
        help="Código de idioma BCP-47 aplicado al documento Word final.",
    )
    parser.add_argument(
        "--page-size",
        dest="tamano_pagina",
        default="A4",
        choices=sorted(TAMANOS_PAGINA_CM),
        help="Tamaño de página usado como límite máximo para las imágenes insertadas.",
    )
    parser.add_argument(
        "--margin",
        dest="margen_cm",
        type=float,
        default=2.5,
        help="Margen de página en centímetros, usado para calcular el área útil disponible para las imágenes.",
    )
    parser.add_argument(
        "--reference-doc",
        dest="plantilla_referencia",
        type=Path,
        default=None,
        help="Plantilla .docx opcional (--reference-doc de Pandoc) para aplicar estilos corporativos.",
    )
    parser.add_argument(
        "--keep-temp",
        dest="mantener_temporales",
        action="store_true",
        help="Conserva los PNG renderizados y el Markdown intermedio (no los borra al finalizar).",
    )
    parser.add_argument(
        "--no-sandbox",
        dest="sin_sandbox",
        action="store_true",
        help="Desactiva el sandbox de Chromium/Puppeteer (necesario en muchos entornos Docker/CI Linux).",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Muestra información detallada de cada paso (comandos ejecutados, avisos, etc.).",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    return parser


def validar_argumentos(args: argparse.Namespace) -> None:
    """
    Realiza validaciones adicionales que argparse no puede expresar de forma
    declarativa (por ejemplo, extensión de archivo o valores numéricos > 0).

    Lanza:
        SystemExit(5) si algún argumento no es válido.
    """
    errores = []

    if args.input.suffix.lower() not in (".md", ".markdown"):
        errores.append(f"El archivo de entrada debería tener extensión .md (recibido: {args.input.suffix})")

    if args.output.suffix.lower() != ".docx":
        errores.append(f"El archivo de salida debe tener extensión .docx (recibido: {args.output.suffix})")

    if args.ancho <= 0 or args.alto <= 0:
        errores.append("El ancho y el alto deben ser valores positivos.")

    if args.escala <= 0:
        errores.append("La escala debe ser un valor positivo.")

    if args.margen_cm < 0:
        errores.append("El margen de página (--margin) no puede ser negativo.")

    if args.plantilla_referencia is not None and not args.plantilla_referencia.exists():
        errores.append(f"La plantilla de referencia indicada no existe: {args.plantilla_referencia}")

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
    print(" CONVERSOR MARKDOWN + MERMAID → WORD (es-ES)  —  Versión CLI")
    print("=" * 70 + "\n")

    ruta_md = args.input.expanduser().resolve()
    ruta_docx = args.output.expanduser().resolve()
    ruta_plantilla = args.plantilla_referencia.expanduser().resolve() if args.plantilla_referencia else None

    if args.verbose:
        print("Parámetros:")
        print(f"  Entrada              : {ruta_md}")
        print(f"  Salida               : {ruta_docx}")
        print(f"  Tema Mermaid         : {args.tema}")
        print(f"  Resolución           : {args.ancho}x{args.alto} (escala {args.escala})")
        print(f"  Fondo                : {args.fondo}")
        print(f"  Idioma del documento : {args.idioma}")
        print(f"  Tamaño de página     : {args.tamano_pagina} (margen {args.margen_cm} cm)")
        print(f"  Plantilla referencia : {ruta_plantilla or '(ninguna)'}")
        print(f"  Conservar temporales : {args.mantener_temporales}")
        print(f"  Sin sandbox          : {args.sin_sandbox}")
        print()

    try:
        ruta_final = procesar_markdown_a_docx(
            ruta_md=ruta_md,
            ruta_docx=ruta_docx,
            tema=args.tema,
            ancho=args.ancho,
            alto=args.alto,
            escala=args.escala,
            fondo=args.fondo,
            idioma=args.idioma,
            tamano_pagina=args.tamano_pagina,
            margen_cm=args.margen_cm,
            referencia_docx=ruta_plantilla,
            mantener_temporales=args.mantener_temporales,
            sin_sandbox=args.sin_sandbox,
            verbose=args.verbose,
        )
    except FileNotFoundError as exc:
        print(f"\n✗ ERROR — Archivo no encontrado: {exc}", file=sys.stderr)
        return 1
    except HerramientaNoEncontradaError as exc:
        print(f"\n✗ ERROR — Falta una dependencia externa:\n{exc}", file=sys.stderr)
        return 2
    except RenderizadoMermaidError as exc:
        print(f"\n✗ ERROR — Fallo al renderizar un diagrama Mermaid:\n{exc}", file=sys.stderr)
        return 3
    except ConversionPandocError as exc:
        print(f"\n✗ ERROR — Fallo en la conversión con Pandoc:\n{exc}", file=sys.stderr)
        return 4
    except ValueError as exc:
        print(f"\n✗ ERROR — Parámetro inválido: {exc}", file=sys.stderr)
        return 5
    except Exception as exc:  # noqa: BLE001 — red de seguridad ante fallos no previstos
        print(f"\n✗ ERROR inesperado: {exc}", file=sys.stderr)
        return 99

    print("=" * 70)
    print(f" ✓ ¡Listo! Documento Word generado en: {ruta_final}")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    sys.exit(main())
