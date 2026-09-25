#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ref_cons.py
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
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

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
# CONFIGURACIÓN
# ===========================================================================
# Todos los valores de esta sección se modifican directamente aquí, editando
# el código. Se han agrupado en una única clase de configuración (dataclass)
# para que resulte sencillo modificarlos, guardarlos o pasarlos entre
# funciones.

@dataclass
class ConfiguracionModelo:
    """
    Agrupa el modelo de Claude y los parámetros de generación que se usarán
    en las llamadas a la API.

    Explicación de cada parámetro
    ------------------------------
    modelo:
        Identificador del modelo de Claude a utilizar. Algunos ejemplos
        válidos en la API de Anthropic (comprobar siempre la documentación
        oficial, ya que Anthropic publica nuevos modelos con frecuencia):

            - "claude-sonnet-5"   -> Modelo de gama media, buen equilibrio
                                     entre velocidad, coste e inteligencia.
                                     Es el valor por defecto de este script.
            - "claude-opus-5"     -> Modelo más potente, pensado para tareas
                                     complejas de razonamiento y agentes de
                                     larga duración. Más lento y más caro.
            - "claude-haiku-4-5-20251001" -> Modelo más rápido y económico,
                                     con una inteligencia cercana a la de
                                     los modelos de gama alta.

    max_tokens:
        Número MÁXIMO de tokens que el modelo puede generar en su
        respuesta. No afecta a la "calidad" de la respuesta, solo limita su
        longitud máxima. Si la respuesta se corta de forma abrupta, suele
        significar que este valor es demasiado bajo para la tarea.

    temperature:
        Controla la aleatoriedad/creatividad de la respuesta. Rango: 0.0 a
        1.0.
            - Valores bajos (p.ej. 0.0 - 0.3): respuestas más deterministas,
              conservadoras y repetibles. Recomendado para tareas técnicas,
              de refinado de prompts o donde se busca precisión.
            - Valores altos (p.ej. 0.7 - 1.0): respuestas más creativas y
              variadas, útiles para brainstorming o escritura creativa.

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

    modelo: str = "claude-sonnet-5"
    max_tokens: int = 4096
    temperature: float = 0.7
    top_p: Optional[float] = None
    top_k: Optional[int] = None


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
            modelo="claude-sonnet-5",
            max_tokens=1024,
            temperature=0.3,  # Baja, porque aquí buscamos precisión, no creatividad.
        )
    )

    # --- Paso 2: consulta principal ---------------------------------------
    system_prompt_principal: str = (
        "You are a helpful, precise and knowledgeable assistant. Answer the "
        "user's request thoroughly and in a well-structured way, using "
        "Markdown formatting (headings, lists, code blocks, etc.) where "
        "appropriate."
    )
    config_modelo_principal: ConfiguracionModelo = field(
        default_factory=lambda: ConfiguracionModelo(
            modelo="claude-sonnet-5",
            max_tokens=4096,
            temperature=0.7,
        )
    )

    # --- Prompt original del usuario --------------------------------------
    prompt_usuario: str = (
        "Explícame qué es la automatización textil y pon dos ejemplos "
        "prácticos aplicados a la confección de prendas de moda."
    )

    # --- Salida -------------------------------------------------------------
    ruta_salida: Path = field(
        default_factory=lambda: Path("./salida/respuesta.md")
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
    if _DOTENV_DISPONIBLE:
        # `load_dotenv()` busca un archivo ".env" en el directorio actual
        # (o en directorios superiores) y carga sus variables al entorno.
        # Si el archivo no existe, simplemente no hace nada (no da error).
        load_dotenv()

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


def _construir_parametros_llamada(
    config: ConfiguracionModelo,
) -> dict:
    """
    Construye el diccionario de parámetros que se pasará a
    `client.messages.create(...)`, incluyendo solo los parámetros opcionales
    (`top_p`, `top_k`) cuando el usuario los haya definido (distintos de
    `None`). Esto evita enviar parámetros vacíos que la API podría rechazar.

    Parameters
    ----------
    config : ConfiguracionModelo
        Configuración de modelo y parámetros de generación.

    Returns
    -------
    dict
        Diccionario listo para usar como `**kwargs` en la llamada a la API.
    """
    parametros: dict = {
        "model": config.modelo,
        "max_tokens": config.max_tokens,
        "temperature": config.temperature,
    }
    if config.top_p is not None:
        parametros["top_p"] = config.top_p
    if config.top_k is not None:
        parametros["top_k"] = config.top_k
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
    parametros = _construir_parametros_llamada(config_modelo)

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
            f"\n[ERROR] Modelo no encontrado ('{config_modelo.modelo}'). "
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
    PASO 3: guarda la respuesta final en un archivo Markdown, incluyendo
    también, a modo de referencia, el prompt original y el prompt mejorado.

    Parameters
    ----------
    ruta_salida : Path
        Ruta completa (incluyendo nombre de archivo) donde se guardará el
        Markdown. Si el directorio no existe, se crea automáticamente.
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
    print(f"→ [Paso 3/3] Guardando la respuesta en: {ruta_salida}")

    try:
        # Se crean los directorios intermedios si no existen (equivalente
        # a `mkdir -p` en Linux).
        ruta_salida.parent.mkdir(parents=True, exist_ok=True)

        marca_temporal = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        contenido_markdown = (
            f"# Respuesta generada por Claude\n\n"
            f"*Generado el {marca_temporal}*\n\n"
            f"## Prompt original\n\n"
            f"> {prompt_original}\n\n"
            f"## Prompt mejorado (usado para la consulta)\n\n"
            f"> {prompt_mejorado}\n\n"
            f"## Respuesta\n\n"
            f"{respuesta_final}\n"
        )

        ruta_salida.write_text(contenido_markdown, encoding="utf-8")

    except OSError as exc:
        sys.stderr.write(
            f"\n[ERROR] No se ha podido escribir el archivo de salida "
            f"'{ruta_salida}': {exc}\n"
        )
        raise SystemExit(1) from exc

    print(f"  ✓ Archivo guardado correctamente en: {ruta_salida.resolve()}\n")


# ===========================================================================
# PUNTO DE ENTRADA
# ===========================================================================

def main() -> None:
    """Orquesta el flujo completo: refinar → consultar → guardar."""

    print("=" * 70)
    print(" REFINADO DE PROMPT + CONSULTA A CLAUDE (Anthropic API)")
    print("=" * 70 + "\n")

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