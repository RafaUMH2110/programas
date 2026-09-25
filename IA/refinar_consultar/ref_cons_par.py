#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
refinar_y_consultar.py
=======================

Script de ejemplo que utiliza el SDK oficial de Anthropic (`anthropic`) para
realizar un flujo de trabajo en DOS pasos:

    1. REFINADO DEL PROMPT
       Se envía el prompt original del usuario a Claude junto con un
       "system prompt" específico para esta tarea, cuyo único objetivo es
       reescribir/mejorar ese prompt y traducirlo al inglés. El resultado
       de esta llamada es el "prompt mejorado".

    2. CONSULTA PRINCIPAL
       El prompt mejorado (en inglés) obtenido en el paso 1 se envía a
       Claude en una segunda llamada, esta vez con el "system prompt"
       principal que el usuario quiera usar para obtener la respuesta
       definitiva.

    3. GUARDADO EN MARKDOWN
       La respuesta final del paso 2 se guarda en un archivo .md cuya ruta
       es configurable.

Requisitos
----------
    pip install anthropic python-dotenv

Configuración de la clave de API
---------------------------------
Se recomienda NO escribir la clave directamente en el código. Este script
la busca, en este orden:

    1. Variable de entorno ANTHROPIC_API_KEY ya definida en el sistema.
    2. Un archivo ``.env`` en el mismo directorio que este script, con una
       línea como:

           ANTHROPIC_API_KEY=sk-ant-xxxxxxxxxxxxxxxxxxxxxxxx

Uso
---
Este script está pensado para ejecutarse SIEMPRE desde VS Code (botón
"Run Python File" o F5), no desde la línea de comandos.

Todos los valores de configuración —prompts, modelo, parámetros de
generación y ruta de salida— se definen más abajo, en la sección
"CONFIGURACIÓN" (clase `ConfiguracionGeneral`). Para cambiar cualquier
valor, edita directamente esos campos en el código y vuelve a ejecutar
el script.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field, replace
from datetime import datetime
from pathlib import Path
from typing import List, Optional

# ---------------------------------------------------------------------------
# Dependencias externas
# ---------------------------------------------------------------------------
# `python-dotenv` permite cargar variables de entorno desde un archivo .env.
# Es una dependencia opcional: si no está instalada, el script sigue
# funcionando siempre que la variable de entorno ya esté definida en el
# sistema operativo.
try:
    from dotenv import load_dotenv  # type: ignore
    _DOTENV_DISPONIBLE = True
except ImportError:
    _DOTENV_DISPONIBLE = False

# El SDK oficial de Anthropic. Es una dependencia obligatoria para este
# script.
try:
    import anthropic
except ImportError as exc:  # pragma: no cover - mensaje de ayuda al usuario
    sys.stderr.write(
        "\n[ERROR] No se ha encontrado el paquete 'anthropic'.\n"
        "Instálalo con:\n\n    pip install anthropic\n\n"
    )
    raise SystemExit(1) from exc


# ===========================================================================
# CATÁLOGO DE MODELOS
# ===========================================================================
# Lista de todos los modelos de Claude disponibles a través de la API de
# Anthropic. Cada modelo se selecciona por su ÍNDICE dentro de esta lista
# (ver `indice_modelo` en `ConfiguracionModelo`, más abajo), en lugar de
# escribir el identificador de la API a mano, para reducir errores.
#
# IMPORTANTE: Anthropic publica nuevos modelos y retira los antiguos con
# cierta frecuencia. Antes de un uso serio/en producción, conviene
# comprobar la lista y los límites vigentes en la documentación oficial:
# https://docs.claude.com/en/docs/about-claude/models/overview
#
# `max_output_tokens` es el límite MÁXIMO que la API acepta para
# `max_tokens` en ese modelo (una petición con un valor mayor es
# rechazada). `admite_parametros_muestreo` indica si el modelo permite
# personalizar `temperature`, `top_p` y `top_k`: los modelos más recientes
# de "razonamiento adaptativo" (Sonnet 5) fuerzan
# valores internos fijos y RECHAZAN (error 400) estos parámetros si se
# envían con un valor distinto del predeterminado.

@dataclass(frozen=True)
class InfoModelo:
    """Descripción de un modelo de Claude disponible en la API."""

    id_api: str
    nombre: str
    contexto_maximo: int
    max_output_tokens: int
    admite_parametros_muestreo: bool
    notas: str = ""


MODELOS_DISPONIBLES: List[InfoModelo] = [
    InfoModelo(
        id_api="claude-sonnet-5",
        nombre="Claude Sonnet 5",
        contexto_maximo=1_000_000,
        max_output_tokens=128_000,
        admite_parametros_muestreo=False,
        notas=(
            "Modelo de gama media más reciente. Mejor equilibrio entre "
            "velocidad, coste e inteligencia. Usa razonamiento adaptativo "
            "por defecto: la API NO admite valores personalizados de "
            "temperature/top_p/top_k."
        ),
    ),
    InfoModelo(
        id_api="claude-haiku-4-5-20251001",
        nombre="Claude Haiku 4.5",
        contexto_maximo=200_000,
        max_output_tokens=64_000,
        admite_parametros_muestreo=True,
        notas=(
            "Modelo más rápido y económico, con inteligencia cercana a la "
            "de los modelos de gama alta. Admite temperature/top_p/top_k "
            "estándar."
        ),
    ),
    InfoModelo(
        id_api="claude-sonnet-4-5-20250929",
        nombre="Claude Sonnet 4.5",
        contexto_maximo=200_000,
        max_output_tokens=64_000,
        admite_parametros_muestreo=True,
        notas="Generación anterior a Sonnet 5. Admite parámetros de muestreo estándar.",
    ),
    InfoModelo(
        id_api="claude-opus-4-5-20251101",
        nombre="Claude Opus 4.5",
        contexto_maximo=200_000,
        max_output_tokens=64_000,
        admite_parametros_muestreo=True,
        notas="Modelo de gama alta. Admite parámetros de muestreo estándar.",
    ),
    InfoModelo(
        id_api="claude-opus-4-1-20250805",
        nombre="Claude Opus 4.1 (legacy)",
        contexto_maximo=200_000,
        max_output_tokens=32_000,
        admite_parametros_muestreo=True,
        notas="Modelo legacy, mantenido por compatibilidad. Admite parámetros de muestreo estándar.",
    ),
]


def listar_modelos_disponibles() -> None:
    """
    Imprime por pantalla la lista numerada de modelos disponibles en
    `MODELOS_DISPONIBLES`, para que resulte fácil elegir el índice que se
    quiere usar en `ConfiguracionModelo.indice_modelo`.
    """
    print("Modelos de Claude disponibles (usa el índice en la configuración):")
    for indice, info in enumerate(MODELOS_DISPONIBLES):
        admite = "sí" if info.admite_parametros_muestreo else "NO (valores fijos)"
        print(
            f"  [{indice}] {info.nombre}  (id API: {info.id_api})\n"
            f"        Contexto máx.: {info.contexto_maximo:,} tokens | "
            f"Salida máx.: {info.max_output_tokens:,} tokens | "
            f"Admite temperature/top_p/top_k: {admite}"
        )
    print()


def obtener_info_modelo(indice_modelo: int) -> InfoModelo:
    """
    Devuelve la `InfoModelo` correspondiente a `indice_modelo` dentro de
    `MODELOS_DISPONIBLES`.

    Parameters
    ----------
    indice_modelo : int
        Índice del modelo dentro de la lista `MODELOS_DISPONIBLES`.

    Returns
    -------
    InfoModelo
        La información del modelo seleccionado.

    Raises
    ------
    SystemExit
        Si `indice_modelo` está fuera del rango válido de la lista.
    """
    if not (0 <= indice_modelo < len(MODELOS_DISPONIBLES)):
        sys.stderr.write(
            f"\n[ERROR] Índice de modelo no válido: {indice_modelo}. "
            f"Debe ser un valor entre 0 y {len(MODELOS_DISPONIBLES) - 1}.\n\n"
        )
        listar_modelos_disponibles()
        raise SystemExit(1)
    return MODELOS_DISPONIBLES[indice_modelo]


# ===========================================================================
# CONFIGURACIÓN
# ===========================================================================
# Todos los valores de esta sección se modifican directamente aquí, editando
# el código. Se han agrupado en una única clase de configuración (dataclass)
# para que resulte sencillo modificarlos, guardarlos o pasarlos entre
# funciones.

@dataclass
class ConfiguracionModelo:
    """
    Agrupa el modelo de Claude (por índice en `MODELOS_DISPONIBLES`) y los
    parámetros de generación que se usarán en las llamadas a la API.

    Explicación de cada parámetro
    ------------------------------
    indice_modelo:
        Índice, dentro de la lista `MODELOS_DISPONIBLES` (definida más
        arriba), del modelo de Claude a utilizar. Llama a
        `listar_modelos_disponibles()` para ver la lista completa con sus
        índices, o consulta la tabla en los comentarios de
        `MODELOS_DISPONIBLES`.

    max_tokens:
        Número MÁXIMO de tokens que el modelo puede generar en su
        respuesta. No afecta a la "calidad" de la respuesta, solo limita su
        longitud máxima. Si la respuesta se corta de forma abrupta, suele
        significar que este valor es demasiado bajo para la tarea. No puede
        superar el `max_output_tokens` del modelo elegido (se valida antes
        de cada llamada).

    temperature:
        Controla la aleatoriedad/creatividad de la respuesta. Rango: 0.0 a
        1.0.
            - Valores bajos (p.ej. 0.0 - 0.3): respuestas más deterministas,
              conservadoras y repetibles. Recomendado para tareas técnicas,
              de refinado de prompts o donde se busca precisión.
            - Valores altos (p.ej. 0.7 - 1.0): respuestas más creativas y
              variadas, útiles para brainstorming o escritura creativa.
        Déjalo en `None` para usar el valor por defecto de la API. En los
        modelos que no admiten parámetros de muestreo personalizados (ver
        `InfoModelo.admite_parametros_muestreo`), este valor se ignora
        automáticamente (con aviso por pantalla) para evitar un error 400.

    top_p:
        Alternativa a `temperature` para controlar la aleatoriedad, basada
        en "nucleus sampling": el modelo solo considera el conjunto más
        pequeño de tokens cuya probabilidad acumulada supera `top_p`.
        Rango: 0.0 a 1.0. Anthropic recomienda modificar `temperature` O
        `top_p`, pero normalmente no ambos a la vez.

    top_k:
        Otra técnica de muestreo: el modelo solo considera los `top_k`
        tokens más probables en cada paso. Es un parámetro más "avanzado"
        y se usa con menos frecuencia que `temperature` o `top_p`. Si no se
        necesita un control tan fino, puede dejarse en `None` para que la
        API use su valor por defecto.
    """
#################################################################################
    indice_modelo: int = 0
    max_tokens: int = 8192
    temperature: Optional[float] = 0.7
    top_p: Optional[float] = None
    top_k: Optional[int] = None
#################################################################################

@dataclass
class ConfiguracionGeneral:
    """
    Configuración global del flujo de trabajo: prompts, rutas de salida y
    las dos configuraciones de modelo (una para cada llamada a la API).
    """

    # --- Paso 1: refinado del prompt -------------------------------------
    system_prompt_refinado: str = (
        "You are an expert prompt engineer. Your only task is to take the "
        "user's original prompt (which may be written in any language) and "
        "rewrite it as a single, clear, detailed and unambiguous prompt in "
        "English, ready to be sent to an AI assistant. Do not answer the "
        "prompt yourself. Do not add explanations, preambles or comments. "
        "Reply with ONLY the improved prompt text, nothing else."
    )
    config_modelo_refinado: ConfiguracionModelo = field(
        default_factory=lambda: ConfiguracionModelo(
            max_tokens=1024,
            temperature=0.3,  # Baja, porque aquí buscamos precisión, no creatividad.
        )
    )

    # --- Paso 2: consulta principal ---------------------------------------
    system_prompt_principal: str = (
        "Eres un asistente de inteligencia artificial experto en tecnología y sistemas operativos. "
        "Eres un experto en MacOS y en administración y y configuración del sistema operativo a bajo nivel. "
        "Responde a la solicitud del usuario de manera completa y estructurada, utilizando "
        "el formato Markdown (encabezados, listas, bloques de código, etc.) cuando sea apropiado."
    )
    config_modelo_principal: ConfiguracionModelo = field(
        default_factory=lambda: ConfiguracionModelo(
            max_tokens=4096,
            temperature=0.7,
        )
    )

    # --- Prompt original del usuario --------------------------------------
    prompt_usuario: str = (
        "Tengo un Macbokk Pro con microprocesador M4 Pro y sistema operativo macosx versión Golden Gate. "
        "Suelo trabajar o bien directamente en el portátil o bien con un monitor externo de 27 pulgadas. "
        "Nunca utilizo a configuración de pantalla estendida, es decir, cuando conecto el monitor externo,"
        "la tapa del portátil está cerrada y todo lo que hago se ve en el monitor externo. "
        "Explícame por qué me ocurre lo siguiente: "
        "Las aplicaciones, que están asignadas a spaces distintos pierden el space asignado previamente."
        "El idioma de la respuesta debe ser español, y la explicación debe ser técnica, extensa y debes"
        "aportar soluciones"
    )
    

    # --- Salida -------------------------------------------------------------
    ruta_salida: Path = field(
        default_factory=lambda: Path("./salida") / datetime.now().strftime(
            "respuesta_%Y%m%d_%H%M%S.md"
        )
    )


# ===========================================================================
# LÓGICA PRINCIPAL
# ===========================================================================

def cargar_clave_api() -> str:
    """
    Carga la clave de la API de Anthropic desde las variables de entorno.

    Primero intenta cargar un archivo `.env` (si `python-dotenv` está
    instalado), de modo que si el usuario define ANTHROPIC_API_KEY allí,
    quede disponible como variable de entorno. Después, lee la variable de
    entorno `ANTHROPIC_API_KEY`.

    Returns
    -------
    str
        La clave de API encontrada.

    Raises
    ------
    SystemExit
        Si no se encuentra ninguna clave de API configurada.
    """
    # if _DOTENV_DISPONIBLE:
    #     # `load_dotenv()` busca un archivo ".env" en el directorio actual
    #     # (o en directorios superiores) y carga sus variables al entorno.
    #     # Si el archivo no existe, simplemente no hace nada (no da error).
    #     load_dotenv()

    clave = os.environ.get("ANTHROPIC_API_KEY")

    if not clave:
        sys.stderr.write(
            "\n[ERROR] No se ha encontrado la variable de entorno "
            "ANTHROPIC_API_KEY.\n\n"
            "Soluciones posibles:\n"
            "  1. Define la variable de entorno antes de ejecutar el script:\n"
            "       export ANTHROPIC_API_KEY='sk-ant-...'   (Linux/Mac)\n"
            "       set ANTHROPIC_API_KEY=sk-ant-...        (Windows CMD)\n"
            "  2. O crea un archivo '.env' en este mismo directorio con la línea:\n"
            "       ANTHROPIC_API_KEY=sk-ant-...\n\n"
        )
        raise SystemExit(1)

    return clave


def crear_cliente(clave_api: str) -> "anthropic.Anthropic":
    """
    Crea y devuelve un cliente de la API de Anthropic.

    Parameters
    ----------
    clave_api : str
        La clave de API a utilizar para autenticar las peticiones.

    Returns
    -------
    anthropic.Anthropic
        Instancia del cliente, lista para realizar llamadas.
    """
    return anthropic.Anthropic(api_key=clave_api)


def validar_parametros_modelo(config: ConfiguracionModelo) -> ConfiguracionModelo:
    """
    Verifica que el modelo elegido y sus parámetros de generación son
    válidos, y comprueba que son compatibles entre sí antes de realizar
    la llamada a la API.

    Comprobaciones realizadas
    --------------------------
    - `indice_modelo` corresponde a un modelo real de `MODELOS_DISPONIBLES`.
    - `max_tokens` es un entero positivo y no supera el `max_output_tokens`
      del modelo elegido.
    - `temperature`, si se ha definido, está en el rango [0.0, 1.0].
    - `top_p`, si se ha definido, está en el rango [0.0, 1.0].
    - `top_k`, si se ha definido, es un entero >= 0.
    - Si el modelo elegido NO admite parámetros de muestreo personalizados
      (`InfoModelo.admite_parametros_muestreo == False`), `temperature`,
      `top_p` y `top_k` se anulan automáticamente (con un aviso por
      pantalla) para evitar que la API devuelva un error 400.

    Parameters
    ----------
    config : ConfiguracionModelo
        Configuración de modelo y parámetros a validar.

    Returns
    -------
    ConfiguracionModelo
        Una copia de `config`, ya validada y, si procede, ajustada para
        ser compatible con el modelo elegido.

    Raises
    ------
    SystemExit
        Si algún valor está fuera de su rango permitido.
    """
    info = obtener_info_modelo(config.indice_modelo)

    # --- max_tokens ---------------------------------------------------------
    if config.max_tokens < 1:
        sys.stderr.write(
            f"\n[ERROR] 'max_tokens' debe ser un entero positivo "
            f"(valor recibido: {config.max_tokens}).\n\n"
        )
        raise SystemExit(1)
    if config.max_tokens > info.max_output_tokens:
        sys.stderr.write(
            f"\n[ERROR] El modelo '{info.nombre}' admite como máximo "
            f"{info.max_output_tokens:,} tokens de salida, pero se ha "
            f"configurado max_tokens={config.max_tokens:,}.\n"
            f"Reduce 'max_tokens' a {info.max_output_tokens:,} o menos.\n\n"
        )
        raise SystemExit(1)

    # --- temperature ----------------------------------------------------------
    if config.temperature is not None and not (0.0 <= config.temperature <= 1.0):
        sys.stderr.write(
            f"\n[ERROR] 'temperature' debe estar entre 0.0 y 1.0 "
            f"(valor recibido: {config.temperature}).\n\n"
        )
        raise SystemExit(1)

    # --- top_p ------------------------------------------------------------------
    if config.top_p is not None and not (0.0 <= config.top_p <= 1.0):
        sys.stderr.write(
            f"\n[ERROR] 'top_p' debe estar entre 0.0 y 1.0 "
            f"(valor recibido: {config.top_p}).\n\n"
        )
        raise SystemExit(1)

    # --- top_k --------------------------------------------------------------
    if config.top_k is not None and config.top_k < 0:
        sys.stderr.write(
            f"\n[ERROR] 'top_k' debe ser un entero >= 0 "
            f"(valor recibido: {config.top_k}).\n\n"
        )
        raise SystemExit(1)

    # --- Compatibilidad del modelo con parámetros de muestreo -----------------
    config_validada = replace(config)  # Copia; no modificamos el original.

    if not info.admite_parametros_muestreo:
        parametros_omitidos = [
            nombre
            for nombre, valor in (
                ("temperature", config.temperature),
                ("top_p", config.top_p),
                ("top_k", config.top_k),
            )
            if valor is not None
        ]
        if parametros_omitidos:
            print(
                f"  ⚠ Aviso: el modelo '{info.nombre}' no admite valores "
                f"personalizados de {', '.join(parametros_omitidos)} (usa "
                f"razonamiento adaptativo con valores internos fijos). "
                f"Estos parámetros se omitirán en la llamada a la API.\n"
            )
        config_validada.temperature = None
        config_validada.top_p = None
        config_validada.top_k = None

    return config_validada


def _construir_parametros_llamada(config: ConfiguracionModelo) -> dict:
    """
    Construye el diccionario de parámetros que se pasará a
    `client.messages.create(...)`, resolviendo el `id_api` del modelo a
    partir de su índice e incluyendo `temperature`/`top_p`/`top_k` solo
    cuando estén definidos (`None` significa "usar el valor por defecto de
    la API" o "no soportado por este modelo").

    Se asume que `config` ya ha pasado por `validar_parametros_modelo()`.

    La versión actual del SDK de Anthropic no acepta `temperature`, `top_p`
    ni `top_k` en `messages.create()`, por lo que no se incluyen en la
    petición aunque estén definidos en la configuración.

    Parameters
    ----------
    config : ConfiguracionModelo
        Configuración de modelo y parámetros de generación, ya validada.

    Returns
    -------
    dict
        Diccionario listo para usar como `**kwargs` en la llamada a la API.
    """
    info = obtener_info_modelo(config.indice_modelo)

    parametros: dict = {
        "model": info.id_api,
        "max_tokens": config.max_tokens,
    }
    return parametros


def llamar_a_claude(
    cliente: "anthropic.Anthropic",
    system_prompt: str,
    user_prompt: str,
    config_modelo: ConfiguracionModelo,
) -> str:
    """
    Realiza una única llamada a la API de Mensajes de Anthropic y devuelve
    el texto de la respuesta.

    Parameters
    ----------
    cliente : anthropic.Anthropic
        Cliente ya inicializado con la clave de API.
    system_prompt : str
        Instrucciones de sistema para esta llamada concreta.
    user_prompt : str
        Mensaje del usuario que se enviará al modelo.
    config_modelo : ConfiguracionModelo
        Modelo y parámetros de generación a utilizar en esta llamada.

    Returns
    -------
    str
        El texto de la respuesta generada por el modelo.

    Raises
    ------
    SystemExit
        Si la llamada a la API falla (error de red, modelo inválido,
        clave incorrecta, límite de peticiones excedido, etc.).
    """
    # Se valida (y, si procede, se ajusta) la configuración ANTES de
    # construir los parámetros de la llamada, para detectar valores fuera
    # de rango o incompatibles con el modelo elegido sin gastar una
    # petición a la API.
    config_modelo = validar_parametros_modelo(config_modelo)
    info_modelo = obtener_info_modelo(config_modelo.indice_modelo)
    parametros = _construir_parametros_llamada(config_modelo)

    print(
        f"  Modelo utilizado: {info_modelo.nombre} "
        f"(índice {config_modelo.indice_modelo}, ID API: {info_modelo.id_api})"
    )

    try:
        respuesta = cliente.messages.create(
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
            **parametros,
        )
    except anthropic.AuthenticationError as exc:
        sys.stderr.write(
            f"\n[ERROR] Clave de API inválida o no autorizada: {exc}\n"
        )
        raise SystemExit(1) from exc
    except anthropic.NotFoundError as exc:
        sys.stderr.write(
            f"\n[ERROR] Modelo no encontrado ('{info_modelo.id_api}'). "
            f"Comprueba que el nombre del modelo es correcto y sigue "
            f"vigente: {exc}\n"
        )
        raise SystemExit(1) from exc
    except anthropic.RateLimitError as exc:
        sys.stderr.write(
            f"\n[ERROR] Límite de peticiones excedido. Inténtalo de nuevo "
            f"más tarde: {exc}\n"
        )
        raise SystemExit(1) from exc
    except anthropic.APIConnectionError as exc:
        sys.stderr.write(
            f"\n[ERROR] No se ha podido conectar con la API de Anthropic. "
            f"Comprueba tu conexión a internet: {exc}\n"
        )
        raise SystemExit(1) from exc
    except anthropic.APIStatusError as exc:
        sys.stderr.write(
            f"\n[ERROR] La API ha devuelto un error "
            f"(código {exc.status_code}): {exc}\n"
        )
        raise SystemExit(1) from exc

    # El campo `content` es una lista de bloques (normalmente de texto).
    # Se concatenan todos los bloques de tipo "text" por si la respuesta
    # viniera fragmentada en varios bloques.
    fragmentos_texto = [
        bloque.text for bloque in respuesta.content if bloque.type == "text"
    ]
    return "".join(fragmentos_texto).strip()


def refinar_prompt(
    cliente: "anthropic.Anthropic",
    prompt_original: str,
    system_prompt_refinado: str,
    config_modelo: ConfiguracionModelo,
) -> str:
    """
    PASO 1: envía el prompt original a Claude para obtener una versión
    mejorada y traducida al inglés.

    Parameters
    ----------
    cliente : anthropic.Anthropic
        Cliente de la API ya inicializado.
    prompt_original : str
        Prompt tal y como lo ha escrito el usuario (en cualquier idioma).
    system_prompt_refinado : str
        Instrucciones de sistema específicas para la tarea de refinado.
    config_modelo : ConfiguracionModelo
        Modelo y parámetros a usar en esta llamada.

    Returns
    -------
    str
        El prompt mejorado, en inglés.
    """
    print("→ [Paso 1/3] Refinando el prompt original con Claude...")
    prompt_mejorado = llamar_a_claude(
        cliente=cliente,
        system_prompt=system_prompt_refinado,
        user_prompt=prompt_original,
        config_modelo=config_modelo,
    )
    print("  ✓ Prompt mejorado obtenido correctamente.\n")
    return prompt_mejorado


def consultar_con_prompt_mejorado(
    cliente: "anthropic.Anthropic",
    prompt_mejorado: str,
    system_prompt_principal: str,
    config_modelo: ConfiguracionModelo,
) -> str:
    """
    PASO 2: envía el prompt ya mejorado (en inglés) a Claude para obtener
    la respuesta final que se guardará en el archivo Markdown.

    Parameters
    ----------
    cliente : anthropic.Anthropic
        Cliente de la API ya inicializado.
    prompt_mejorado : str
        Prompt mejorado obtenido en el paso 1.
    system_prompt_principal : str
        Instrucciones de sistema para la consulta principal.
    config_modelo : ConfiguracionModelo
        Modelo y parámetros a usar en esta llamada.

    Returns
    -------
    str
        La respuesta final generada por el modelo.
    """
    print("→ [Paso 2/3] Realizando la consulta principal con el prompt mejorado...")
    respuesta_final = llamar_a_claude(
        cliente=cliente,
        system_prompt=system_prompt_principal,
        user_prompt=prompt_mejorado,
        config_modelo=config_modelo,
    )
    print("  ✓ Respuesta final obtenida correctamente.\n")
    return respuesta_final


def guardar_respuesta_markdown(
    ruta_salida: Path,
    prompt_original: str,
    prompt_mejorado: str,
    respuesta_final: str,
) -> None:
    """
    PASO 3: guarda los prompts y la respuesta final en dos archivos Markdown
    independientes, con la misma fecha y hora en el nombre.

    Parameters
    ----------
    ruta_salida : Path
        Ruta completa del archivo de respuesta. El archivo de prompts se
        crea en el mismo directorio y con la misma marca temporal.
    prompt_original : str
        Prompt original escrito por el usuario.
    prompt_mejorado : str
        Prompt mejorado obtenido en el paso 1.
    respuesta_final : str
        Respuesta final obtenida en el paso 2.

    Raises
    ------
    SystemExit
        Si ocurre un error de entrada/salida al escribir el archivo.
    """
    ruta_prompts = ruta_salida.with_name(
        ruta_salida.name.replace("respuesta_", "prompts_", 1)
    )

    print(f"→ [Paso 3/3] Guardando los ficheros:\n")
    print(f"  Prompts:   {ruta_prompts}")
    print(f"  Respuesta: {ruta_salida}")

    try:
        # Se crean los directorios intermedios si no existen (equivalente
        # a `mkdir -p` en Linux).
        ruta_salida.parent.mkdir(parents=True, exist_ok=True)

        marca_temporal = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        contenido_prompts = (
            f"# Prompts utilizados\n\n"
            f"*Generado el {marca_temporal}*\n\n"
            f"## Prompt original\n\n"
            f"> {prompt_original}\n\n"
            f"## Prompt mejorado (usado para la consulta)\n\n"
            f"> {prompt_mejorado}\n"
        )
        contenido_respuesta = (
            f"# Respuesta generada por Claude\n\n"
            f"*Generado el {marca_temporal}*\n\n"
            f"## Respuesta\n\n"
            f"{respuesta_final}\n"
        )

        ruta_prompts.write_text(contenido_prompts, encoding="utf-8")
        ruta_salida.write_text(contenido_respuesta, encoding="utf-8")

    except OSError as exc:
        sys.stderr.write(
            f"\n[ERROR] No se ha podido escribir el archivo de salida "
            f"'{ruta_salida.parent}': {exc}\n"
        )
        raise SystemExit(1) from exc

    print(f"  ✓ Ficheros guardados correctamente en: {ruta_salida.parent.resolve()}\n")


# ===========================================================================
# PUNTO DE ENTRADA
# ===========================================================================

def main() -> None:
    """Orquesta el flujo completo: refinar → consultar → guardar."""

    print("=" * 70)
    print(" REFINADO DE PROMPT + CONSULTA A CLAUDE (Anthropic API)")
    print("=" * 70 + "\n")

    listar_modelos_disponibles()

    # 1. Cargar la configuración. Para modificar el prompt, el modelo, los
    #    parámetros de generación o la ruta de salida, edita directamente
    #    los valores de la clase `ConfiguracionGeneral` (sección
    #    CONFIGURACIÓN, al principio de este archivo) y vuelve a ejecutar
    #    el script desde VS Code (botón "Run" o F5).
    config = ConfiguracionGeneral()

    # 2. Cargar la clave de API y crear el cliente.
    clave_api = cargar_clave_api()
    cliente = crear_cliente(clave_api)

    print(f"Prompt original:\n  {config.prompt_usuario}\n")

    # 3. PASO 1: refinar el prompt original.
    prompt_mejorado = refinar_prompt(
        cliente=cliente,
        prompt_original=config.prompt_usuario,
        system_prompt_refinado=config.system_prompt_refinado,
        config_modelo=config.config_modelo_refinado,
    )
    print(f"Prompt mejorado (inglés):\n  {prompt_mejorado}\n")

    # 4. PASO 2: consulta principal con el prompt mejorado.
    respuesta_final = consultar_con_prompt_mejorado(
        cliente=cliente,
        prompt_mejorado=prompt_mejorado,
        system_prompt_principal=config.system_prompt_principal,
        config_modelo=config.config_modelo_principal,
    )

    # 5. PASO 3: guardar el resultado en un archivo Markdown.
    guardar_respuesta_markdown(
        ruta_salida=config.ruta_salida,
        prompt_original=config.prompt_usuario,
        prompt_mejorado=prompt_mejorado,
        respuesta_final=respuesta_final,
    )

    print("=" * 70)
    print(" PROCESO COMPLETADO CON ÉXITO")
    print("=" * 70)


if __name__ == "__main__":
    main()