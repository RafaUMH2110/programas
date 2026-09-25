# -*- coding: utf-8 -*-
"""
generate_presentation_vscode.py
================================

Versión pensada para ejecutarse cómodamente desde VS Code (botón
"Run Python File" o F5), sin necesidad de pasar argumentos por línea
de comandos. Toda la configuración se edita directamente en la sección
``CONFIGURACIÓN`` de este archivo.

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

En VS Code puedes definirla de forma persistente en un archivo ``.env``
en la raíz del proyecto (junto a este script):

    ANTHROPIC_API_KEY=sk-ant-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

y cargarla automáticamente instalando ``python-dotenv``
(``pip install python-dotenv``); este script la carga si está
disponible, y si no, simplemente asume que la variable ya está
definida en el entorno del sistema.

------------------------------------------------------------------
CÓMO EJECUTAR:

    1. Ajusta las rutas en la sección "CONFIGURACIÓN" más abajo.
    2. Pulsa F5 en VS Code (o el botón "Run Python File").
    3. Revisa la consola integrada para ver el progreso paso a paso.

------------------------------------------------------------------
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

# Intenta cargar variables desde un archivo .env si python-dotenv está
# instalado; si no lo está, simplemente se ignora (no es obligatorio).
try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

import os

from generate_pptx_common import (
    ConfiguracionLLM,
    configurar_logging,
    generar_presentacion_desde_docx,
)

# ===========================================================================
# CONFIGURACIÓN — EDITA ESTOS VALORES SEGÚN TU ENTORNO DE TRABAJO
# ===========================================================================

# Ruta al documento .docx de origen (la práctica de laboratorio, el temario, etc.)
RUTA_DOCX_ENTRADA = Path("/Users/rafa/Programas/tmp/prompts_engineering_moda_v2.docx")

# Ruta donde se guardará la presentación .pptx generada
RUTA_PPTX_SALIDA = Path("/Users/rafa/Programas/tmp/output/prompts_engineering_moda.pptx")

# Modelo de Claude (Anthropic) a utilizar. Modelos con ventana de
# contexto amplia (recomendado para documentos largos y presentaciones
# detalladas): "claude-sonnet-5" (equilibrio calidad/coste, por
# defecto), "claude-opus-4-8" (máxima calidad), "claude-haiku-4-5-20251001"
# (más rápido y económico).
MODELO_LLM = "claude-sonnet-5"

# Máximo de tokens de salida permitidos para la respuesta del modelo.
# Se recomienda un valor alto para presentaciones extensas (18-26 diapositivas).
MAX_TOKENS_SALIDA = 16000

# Temperatura: valores bajos (0.2-0.5) producen resultados más
# consistentes y predecibles, ideales para contenido académico.
TEMPERATURA_LLM = 0.4

# Si es True, además del .pptx se guarda el JSON intermedio devuelto
# por el modelo (útil para depurar o auditar el contenido generado).
GUARDAR_JSON_INTERMEDIO = True

# Nivel de detalle de los mensajes de consola: logging.DEBUG o logging.INFO
NIVEL_LOG = logging.INFO


# ===========================================================================
# PUNTO DE ENTRADA
# ===========================================================================

def main() -> int:
    """Ejecuta el proceso completo de generación de la presentación.

    Returns
    -------
    int
        Código de salida (0 = éxito, distinto de 0 = error), útil si en
        algún momento se decide invocar este script desde otro proceso.
    """
    configurar_logging(NIVEL_LOG)
    logger = logging.getLogger("grafcet_pptx")

    logger.info("=" * 70)
    logger.info("GENERADOR DE PRESENTACIONES — VERSIÓN VS CODE")
    logger.info("=" * 70)

    # Verificación temprana de la clave de API para dar un mensaje claro
    if not os.environ.get("ANTHROPIC_API_KEY"):
        logger.error(
            "No se ha encontrado la variable de entorno ANTHROPIC_API_KEY. "
            "Defínela en tu sistema o en un archivo .env antes de continuar."
        )
        return 1

    logger.info("Archivo de entrada (.docx): %s", RUTA_DOCX_ENTRADA.resolve())
    logger.info("Archivo de salida (.pptx):  %s", RUTA_PPTX_SALIDA.resolve())
    logger.info("Modelo LLM: %s | max_tokens=%d | temperatura=%.2f",
                MODELO_LLM, MAX_TOKENS_SALIDA, TEMPERATURA_LLM)

    config_llm = ConfiguracionLLM(
        modelo=MODELO_LLM,
        max_tokens=MAX_TOKENS_SALIDA,
        temperatura=TEMPERATURA_LLM,
    )

    try:
        ruta_final = generar_presentacion_desde_docx(
            ruta_docx=RUTA_DOCX_ENTRADA,
            ruta_pptx=RUTA_PPTX_SALIDA,
            config_llm=config_llm,
            guardar_json_intermedio=GUARDAR_JSON_INTERMEDIO,
        )
    except FileNotFoundError as error:
        logger.error("Archivo no encontrado: %s", error)
        return 1
    except RuntimeError as error:
        logger.error("Error durante la generación con el LLM: %s", error)
        return 1
    except Exception as error:  # noqa: BLE001 — se registra cualquier fallo inesperado
        logger.exception("Error inesperado durante la generación: %s", error)
        return 1

    logger.info("=" * 70)
    logger.info("¡Proceso completado con éxito!")
    logger.info("Presentación disponible en: %s", ruta_final.resolve())
    logger.info("=" * 70)
    return 0


if __name__ == "__main__":
    sys.exit(main())
