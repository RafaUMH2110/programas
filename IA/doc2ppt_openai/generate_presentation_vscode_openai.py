# -*- coding: utf-8 -*-
"""
generate_presentation_vscode_openai.py
========================================

Versión pensada para ejecutarse cómodamente desde VS Code (botón
"Run Python File" o F5), sin necesidad de pasar argumentos por línea
de comandos. Toda la configuración se edita directamente en la sección
``CONFIGURACIÓN`` de este archivo.

------------------------------------------------------------------
REQUISITOS (contenido sugerido de requirements.txt):

    python-pptx>=0.6.23
    python-docx>=1.1.0
    openai>=1.30.0

Instalación:
    pip install -r requirements.txt

------------------------------------------------------------------
VARIABLES DE ENTORNO NECESARIAS:

    OPENAI_API_KEY   Clave de la API de OpenAI (obligatoria).
                      Se obtiene en https://platform.openai.com/api-keys

En VS Code puedes definirla de forma persistente en un archivo ``.env``
en la raíz del proyecto (junto a este script):

    OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

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

from generate_pptx_common_openai import (
    ConfiguracionLLM,
    configurar_logging,
    generar_presentacion_desde_docx,
)

# ===========================================================================
# CONFIGURACIÓN — EDITA ESTOS VALORES SEGÚN TU ENTORNO DE TRABAJO
# ===========================================================================

# Ruta al documento .docx de origen (la práctica de laboratorio, el temario, etc.)
RUTA_DOCX_ENTRADA = Path("/Users/rafa/Programas/tmp/resultado_opus45.docx")

# Ruta donde se guardará la presentación .pptx generada
RUTA_PPTX_SALIDA = Path("/Users/rafa/Programas/tmp/output/resultado_opus45_openai.pptx")

# Modelo de OpenAI a utilizar. Modelos con ventana de contexto amplia
# (recomendado para documentos largos y presentaciones detalladas):
# "gpt-4o" (equilibrio calidad/coste, por defecto), "gpt-4.1" (contexto
# muy amplio), "gpt-4o-mini" (más rápido y económico). Los modelos de
# razonamiento ("o3", "o4-mini") también son compatibles: el código
# detecta y se adapta automáticamente a sus particularidades (no
# admiten "temperature" y usan "max_completion_tokens").
MODELO_LLM = "gpt-4o"

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
    if not os.environ.get("OPENAI_API_KEY"):
        logger.error(
            "No se ha encontrado la variable de entorno OPENAI_API_KEY. "
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
        resultado = generar_presentacion_desde_docx(
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
    logger.info("Presentación disponible en: %s", resultado.ruta_pptx.resolve())
    logger.info("Consumo de tokens de la consulta: %s", resultado.uso_tokens.resumen())
    logger.info("=" * 70)
    return 0


if __name__ == "__main__":
    sys.exit(main())
