"""
convertir_vscode.py
====================

VERSIÓN 1 — Pensada para ejecutarse y depurarse directamente desde VS Code
(por ejemplo, pulsando F5 o "Run Python File").

Convierte un Markdown con diagramas Mermaid en un documento Word (.docx)
en español (es-ES), renderizando cada diagrama como imagen PNG de alta
calidad e insertándola en la posición exacta donde estaba el bloque de
código original.

Cómo configurar la ejecución (dos formas, en este orden de prioridad):

    1. Variables de entorno (útil para "launch.json" de VS Code):
         MERMAID_DOCX_INPUT   -> ruta del Markdown de entrada
         MERMAID_DOCX_OUTPUT  -> ruta del .docx de salida
         MERMAID_DOCX_THEME   -> tema Mermaid (default/dark/neutral/forest/base)

    2. Archivo "config.json" en la misma carpeta que este script (ver
       "config.ejemplo.json" incluido). Si no existe, se usan valores
       por defecto pensados para pruebas rápidas.

    3. También puedes pasar argumentos por línea de comandos si prefieres
       ejecutarlo desde la terminal integrada de VS Code; estos argumentos
       tienen la prioridad más alta de todas.

Ejemplo de "config.json":
{
    "input": "documentos/manual.md",
    "output": "salida/manual.docx",
    "tema": "neutral",
    "ancho": 1400,
    "alto": 900,
    "escala": 2.0,
    "fondo": "white",
    "idioma": "es-ES",
    "plantilla_referencia": null,
    "mantener_temporales": false,
    "verbose": true
}

Requisitos externos (no instalables con pip):
    - Pandoc      : https://pandoc.org/installing.html
    - Mermaid CLI : npm install -g @mermaid-js/mermaid-cli

Requisitos de Python: ver requirements.txt (python-docx).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

# Permite ejecutar este script tanto si está en la misma carpeta que
# mermaid_docx_core.py como si VS Code lo lanza desde otro directorio de trabajo.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from mermaid_docx_core import (  # noqa: E402
    ConversionPandocError,
    HerramientaNoEncontradaError,
    RenderizadoMermaidError,
    procesar_markdown_a_docx,
)


# ---------------------------------------------------------------------------
# Configuración por defecto (usada si no hay config.json ni variables de entorno)
# ---------------------------------------------------------------------------

CONFIGURACION_POR_DEFECTO = {
    "input": "/Users/rafa/Programas/tmp/guia_github_claude.md",
    "output": "/Users/rafa/Programas/tmp/salida/guia_github_claude.docx",
    "tema": "default",
    "ancho": 1200,
    "alto": 800,
    "escala": 2.0,
    "fondo": "white",
    "idioma": "es-ES",
    "tamano_pagina": "A4",
    "margen_cm": 2.5,
    "plantilla_referencia": None,
    "mantener_temporales": False,
    "sin_sandbox": False,
    "verbose": False,
}

RUTA_CONFIG_JSON = Path(__file__).resolve().parent / "config.json"


def cargar_configuracion() -> dict:
    """
    Construye la configuración final combinando, de menor a mayor prioridad:
        1. Valores por defecto embebidos en este script.
        2. Archivo config.json (si existe junto a este script).
        3. Variables de entorno MERMAID_DOCX_*.

    Returns:
        Diccionario de configuración ya resuelto.
    """
    config = dict(CONFIGURACION_POR_DEFECTO)

    if RUTA_CONFIG_JSON.exists():
        try:
            with open(RUTA_CONFIG_JSON, "r", encoding="utf-8") as f:
                config_archivo = json.load(f)
            config.update(config_archivo)
            print(f"ℹ Configuración cargada desde: {RUTA_CONFIG_JSON}")
        except json.JSONDecodeError as exc:
            print(
                f"⚠ No se pudo leer '{RUTA_CONFIG_JSON}' (JSON inválido): {exc}. "
                "Se usarán los valores por defecto.",
                file=sys.stderr,
            )
    else:
        print("ℹ No se encontró config.json; se usan valores por defecto/entorno.")

    # Las variables de entorno tienen la máxima prioridad para facilitar
    # su uso desde un launch.json de VS Code.
    if os.environ.get("MERMAID_DOCX_INPUT"):
        config["input"] = os.environ["MERMAID_DOCX_INPUT"]
    if os.environ.get("MERMAID_DOCX_OUTPUT"):
        config["output"] = os.environ["MERMAID_DOCX_OUTPUT"]
    if os.environ.get("MERMAID_DOCX_THEME"):
        config["tema"] = os.environ["MERMAID_DOCX_THEME"]

    return config


def parsear_argumentos_opcionales() -> argparse.Namespace:
    """
    Argumentos de línea de comandos opcionales; si se proporcionan,
    sobrescriben tanto config.json como las variables de entorno.
    Todos son opcionales para no romper el flujo "pulsar F5" de VS Code.
    """
    parser = argparse.ArgumentParser(
        description="Convierte Markdown con Mermaid a Word (es-ES). Uso pensado para VS Code.",
        add_help=True,
    )
    parser.add_argument("--input", "-i", dest="input", default=None, help="Ruta del Markdown de entrada")
    parser.add_argument("--output", "-o", dest="output", default=None, help="Ruta del .docx de salida")
    parser.add_argument("--theme", dest="tema", default=None, help="Tema Mermaid (default/dark/neutral/forest/base)")
    parser.add_argument("--page-size", dest="tamano_pagina", default=None, help="Tamaño de página límite para las imágenes (A4/Carta)")
    parser.add_argument("--margin", dest="margen_cm", type=float, default=None, help="Margen de página en cm para calcular el área útil")
    parser.add_argument("--verbose", "-v", action="store_true", default=None, help="Salida detallada")
    parser.add_argument("--keep-temp", dest="mantener_temporales", action="store_true", default=None,
                         help="Conserva los archivos temporales (PNG y .md intermedio)")
    # parse_known_args evita errores si VS Code inyecta argumentos propios de depuración.
    args, _desconocidos = parser.parse_known_args()
    return args


def main() -> int:
    """
    Punto de entrada principal. Pensado para ejecutarse tal cual desde VS Code.

    Returns:
        Código de salida (0 = éxito, distinto de 0 = error), útil también
        si se ejecuta desde una tarea de VS Code (tasks.json).
    """
    print("=" * 70)
    print(" CONVERSOR MARKDOWN + MERMAID → WORD (es-ES)  —  Versión VS Code")
    print("=" * 70 + "\n")

    config = cargar_configuracion()
    args = parsear_argumentos_opcionales()

    # Los argumentos de línea de comandos (si se pasaron) tienen prioridad máxima.
    if args.input is not None:
        config["input"] = args.input
    if args.output is not None:
        config["output"] = args.output
    if args.tema is not None:
        config["tema"] = args.tema
    if args.tamano_pagina is not None:
        config["tamano_pagina"] = args.tamano_pagina
    if args.margen_cm is not None:
        config["margen_cm"] = args.margen_cm
    if args.verbose is not None:
        config["verbose"] = args.verbose
    if args.mantener_temporales is not None:
        config["mantener_temporales"] = args.mantener_temporales

    ruta_md = Path(config["input"]).expanduser().resolve()
    ruta_docx = Path(config["output"]).expanduser().resolve()
    plantilla = config.get("plantilla_referencia")
    ruta_plantilla = Path(plantilla).expanduser().resolve() if plantilla else None

    print("Configuración efectiva:")
    print(f"  Entrada             : {ruta_md}")
    print(f"  Salida               : {ruta_docx}")
    print(f"  Tema Mermaid         : {config['tema']}")
    print(f"  Resolución           : {config['ancho']}x{config['alto']} (escala {config['escala']})")
    print(f"  Idioma del documento : {config['idioma']}")
    print(f"  Tamaño de página     : {config['tamano_pagina']} (margen {config['margen_cm']} cm)")
    print(f"  Plantilla de referencia: {ruta_plantilla or '(ninguna, estilo por defecto de Pandoc)'}")
    print(f"  Conservar temporales : {config['mantener_temporales']}")
    print()

    try:
        ruta_final = procesar_markdown_a_docx(
            ruta_md=ruta_md,
            ruta_docx=ruta_docx,
            tema=config["tema"],
            ancho=config["ancho"],
            alto=config["alto"],
            escala=config["escala"],
            fondo=config["fondo"],
            idioma=config["idioma"],
            tamano_pagina=config["tamano_pagina"],
            margen_cm=config["margen_cm"],
            referencia_docx=ruta_plantilla,
            mantener_temporales=config["mantener_temporales"],
            sin_sandbox=config.get("sin_sandbox", False),
            verbose=config["verbose"],
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
    except Exception as exc:  # noqa: BLE001 — feedback amigable ante cualquier fallo inesperado
        print(f"\n✗ ERROR inesperado: {exc}", file=sys.stderr)
        return 99

    print("=" * 70)
    print(f" ✓ ¡Listo! Documento Word generado en: {ruta_final}")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    sys.exit(main())
