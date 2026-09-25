#!/usr/bin/env python3
"""
main.py
=======
Punto de entrada de línea de comandos del generador de ConSultar.

Uso típico desde una terminal (o desde VS Code con "Run Python File"):

    python main.py
    python main.py --config config.yaml
    python main.py --output ./dist
    python main.py --validate

Ejecutar sin argumentos genera la aplicación usando `config.yaml` y
escribe el resultado en el directorio indicado por
`aplicacion.directorio_salida` (por defecto, `output/`).
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

# Permite ejecutar "python main.py" desde cualquier directorio de trabajo,
# resolviendo el paquete `generator` de forma relativa a este archivo.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from generator.generator import ErrorDeGeneracion, generar_aplicacion  # noqa: E402

VERSION = "1.0.0"


def construir_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="main.py",
        description=(
            "Generador configurable de la aplicación web ConSultar. "
            "Lee un archivo de configuración (YAML o JSON) y produce un "
            "único archivo HTML autocontenido."
        ),
    )
    parser.add_argument(
        "--config", "-c",
        default="config.yaml",
        help="Ruta al archivo de configuración (YAML o JSON). Por defecto: config.yaml",
    )
    parser.add_argument(
        "--output", "-o",
        default=None,
        help="Directorio de salida. Sobrescribe 'aplicacion.directorio_salida' de la configuración.",
    )
    parser.add_argument(
        "--validate",
        action="store_true",
        help="Solo valida la configuración; no genera ningún archivo.",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Muestra información de depuración adicional.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {VERSION}")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = construir_parser()
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s: %(message)s",
    )

    try:
        ruta_salida = generar_aplicacion(
            ruta_config=Path(args.config),
            directorio_salida_override=Path(args.output) if args.output else None,
            solo_validar=args.validate,
        )
    except ErrorDeGeneracion as exc:
        logging.error(str(exc))
        return 1
    except KeyboardInterrupt:
        logging.warning("Interrumpido por el usuario.")
        return 130
    except Exception as exc:  # salvaguarda final: nunca mostrar una traza cruda al usuario
        logging.error("Error inesperado: %s", exc)
        return 1

    if ruta_salida is not None:
        print(f"\n✔ Aplicación generada en: {ruta_salida}")
    else:
        print("\n✔ La configuración es válida.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
