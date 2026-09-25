"""
content_generator.py
================================================================================
Encapsula toda la comunicación con la API de Anthropic. Es el único módulo
que sabe que existe un modelo de lenguaje detrás: `document_builder.py` y
`image_service.py` no importan nada de este archivo, solo reciben datos ya
resueltos (un diccionario de contenido). Esta separación permite, por
ejemplo, sustituir el proveedor de IA en el futuro sin tocar el resto del
programa.

Por qué "tool use" y no "pedir JSON como texto"
-------------------------------------------------
Una versión anterior de este generador pedía al modelo que "devolviera
JSON como texto". Con documentos largos (varias secciones, viñetas, notas)
la respuesta podía cortarse a mitad de una cadena si se agotaba
`max_tokens`, y `json.loads()` fallaba con `Unterminated string`.

Usando la función de "tool use" (function calling) de la API, se define
un `input_schema` (JSON Schema real) para una herramienta y se obliga al
modelo a invocarla. La API valida y trocea la respuesta por nosotros: el
argumento de la llamada llega ya como un `dict` de Python, sin parseo
manual ni riesgo de JSON mal formado.
================================================================================
"""

from __future__ import annotations

import time
from typing import Any

try:
    from anthropic import Anthropic, APIError, APIStatusError
except ImportError:  # pragma: no cover - se valida en tiempo de ejecución
    Anthropic = None
    APIError = APIStatusError = Exception

import config
import prompts


class ContentGenerationError(RuntimeError):
    """Error de alto nivel para cualquier fallo al generar el contenido
    (SDK no instalado, API key ausente, respuesta inválida, etc.)."""


# ------------------------------------------------------------------------------
# Esquema JSON (JSON Schema) de la herramienta que el modelo debe rellenar.
# Es deliberadamente genérico: no menciona ningún tema concreto, por lo que
# sirve para CUALQUIER documento que se le pida generar.
# ------------------------------------------------------------------------------

_BLOQUE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "description": "Un bloque de contenido dentro de una sección del documento.",
    "properties": {
        "tipo": {
            "type": "string",
            "enum": ["parrafo", "subtitulo", "url_destacada", "vinetas", "nota", "figura"],
        },
        "texto": {
            "type": "string",
            "description": "Usado en parrafo, subtitulo, url_destacada y nota.",
        },
        "items": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Usado en vinetas.",
        },
        "titulo": {"type": "string", "description": "Usado en nota."},
        "estilo": {
            "type": "string",
            "enum": ["teal", "orange"],
            "description": "Usado en nota (teal = información, orange = advertencia).",
        },
        "image_query": {
            "type": "string",
            "description": (
                "Usado en figura. 2-4 palabras clave EN INGLÉS, concretas y "
                "visuales, para buscar la fotografía en un banco de imágenes."
            ),
        },
        "ancho_cm": {"type": "number", "description": "Usado en figura."},
        "pie": {"type": "string", "description": "Usado en figura (pie de figura)."},
    },
    "required": ["tipo"],
}

_SECCION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "titulo": {"type": "string", "description": "Título de la sección, con su número (p. ej. '1. Introducción')."},
        "bloques": {"type": "array", "items": _BLOQUE_SCHEMA},
    },
    "required": ["titulo", "bloques"],
}

HERRAMIENTA_CONTENIDO: dict[str, Any] = {
    "name": "guardar_contenido_documento",
    "description": (
        "Guarda el contenido completo y ya redactado de un documento "
        "profesional, listo para maquetar en Word."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "portada": {
                "type": "object",
                "properties": {
                    "kicker": {"type": "string"},
                    "titulo_linea_1": {"type": "string"},
                    "titulo_linea_2": {"type": "string"},
                    "subtitulo": {"type": "string"},
                    "linea_1": {"type": "string"},
                    "linea_2": {"type": "string"},
                    "linea_3": {"type": "string"},
                },
                "required": ["kicker", "titulo_linea_1", "titulo_linea_2", "subtitulo", "linea_1"],
            },
            "indice": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "numero": {"type": "string"},
                        "texto": {"type": "string"},
                    },
                    "required": ["numero", "texto"],
                },
            },
            "secciones": {"type": "array", "items": _SECCION_SCHEMA},
        },
        "required": ["portada", "indice", "secciones"],
    },
}


class ContentGenerator:
    """Genera el contenido de un documento (portada, índice y secciones)
    a partir de un tema, usando la API de Anthropic.

    Ejemplo:
        >>> generator = ContentGenerator(api_key="sk-ant-...")
        >>> contenido = generator.generate("La fotosíntesis", num_secciones=5)
    """

    def __init__(self, api_key: str, modelo: str = config.MODELO_ANTHROPIC) -> None:
        if Anthropic is None:
            raise ContentGenerationError(
                "No se encuentra instalado el paquete 'anthropic'. Instálalo con:\n"
                "    pip install anthropic"
            )
        if not api_key:
            raise ContentGenerationError(
                "Falta la API key de Anthropic. Defínela en la variable de "
                "entorno ANTHROPIC_API_KEY (ver README.md)."
            )
        self._cliente = Anthropic(api_key=api_key)
        self._modelo = modelo

    def generate(
        self,
        tema: str,
        *,
        idioma: str | None = None,
        tono: str | None = None,
        audiencia: str | None = None,
        num_secciones: int | None = None,
        instrucciones_adicionales: str | None = None,
    ) -> dict[str, Any]:
        """Genera el contenido completo del documento para ``tema``.

        Args:
            tema: Tema principal del documento. Puede ser cualquier cosa,
                desde "Historia del jazz" hasta "Guía de onboarding para
                nuevos empleados".
            idioma, tono, audiencia, num_secciones, instrucciones_adicionales:
                Ver `prompts.construir_mensajes`.

        Returns:
            Un diccionario con las claves ``portada``, ``indice`` y
            ``secciones``, listo para pasar a
            ``document_builder.construir_documento``.

        Raises:
            ContentGenerationError: si la API falla de forma persistente o
                devuelve una respuesta que no se ajusta al esquema esperado.
        """
        if not tema or not tema.strip():
            raise ContentGenerationError("El tema del documento no puede estar vacío.")

        system, user = prompts.construir_mensajes(
            tema,
            idioma=idioma,
            tono=tono,
            audiencia=audiencia,
            num_secciones=num_secciones,
            instrucciones_adicionales=instrucciones_adicionales,
        )

        ultimo_error: Exception | None = None
        for intento in range(1, config.REINTENTOS_API + 1):
            try:
                return self._llamar_api(system, user)
            except (APIStatusError, APIError, ContentGenerationError) as exc:
                ultimo_error = exc
                if intento < config.REINTENTOS_API:
                    espera = 2 ** intento  # backoff exponencial: 2s, 4s, 8s...
                    time.sleep(espera)

        raise ContentGenerationError(
            f"No se pudo generar el contenido tras {config.REINTENTOS_API} "
            f"intentos. Último error: {ultimo_error}"
        ) from ultimo_error

    def _llamar_api(self, system: str, user: str) -> dict[str, Any]:
        """Realiza una única llamada a la API y valida la respuesta."""
        respuesta = self._cliente.messages.create(
            model=self._modelo,
            max_tokens=config.MAX_TOKENS_CONTENIDO,
            system=system,
            tools=[HERRAMIENTA_CONTENIDO],
            tool_choice={"type": "tool", "name": "guardar_contenido_documento"},
            messages=[{"role": "user", "content": user}],
        )

        if respuesta.stop_reason == "max_tokens":
            raise ContentGenerationError(
                "La respuesta del modelo se cortó por alcanzar el límite de "
                "max_tokens. Aumenta config.MAX_TOKENS_CONTENIDO o reduce "
                "num_secciones."
            )

        for bloque in respuesta.content:
            if bloque.type == "tool_use" and bloque.name == "guardar_contenido_documento":
                return self._validar_contenido(bloque.input)

        raise ContentGenerationError(
            "La API no devolvió una llamada a la herramienta esperada "
            "('guardar_contenido_documento')."
        )

    @staticmethod
    def _validar_contenido(contenido: dict[str, Any]) -> dict[str, Any]:
        """Valida en profundidad la respuesta de la API antes de pasarla
        al maquetador.

        El `input_schema` de la herramienta orienta al modelo, pero no
        garantiza al 100% la forma interna de la respuesta (por ejemplo,
        el modelo podría devolver "secciones" como una lista de simples
        cadenas de texto en vez de objetos con "titulo"/"bloques"). Esta
        validación detecta cualquier desviación y lanza
        ``ContentGenerationError``, que el bucle de reintentos de
        ``generate()`` captura para pedir el contenido de nuevo — así, un
        problema de forma se resuelve con un reintento automático en vez
        de reventar más adelante con un `AttributeError` críptico dentro
        de `resolver_imagenes` o `document_builder`.
        """
        # -- Nivel 0: claves de primer nivel ------------------------------
        campos_obligatorios = ("portada", "indice", "secciones")
        faltantes = [campo for campo in campos_obligatorios if campo not in contenido]
        if faltantes:
            raise ContentGenerationError(
                f"La respuesta de la API no incluye los campos obligatorios: {faltantes}"
            )

        if not isinstance(contenido["portada"], dict):
            raise ContentGenerationError(
                f"'portada' debería ser un objeto y se recibió {type(contenido['portada']).__name__}."
            )

        if not isinstance(contenido["indice"], list):
            raise ContentGenerationError(
                f"'indice' debería ser una lista y se recibió {type(contenido['indice']).__name__}."
            )

        # -- Nivel 1: secciones --------------------------------------------
        secciones = contenido["secciones"]
        if not isinstance(secciones, list) or not secciones:
            raise ContentGenerationError("La respuesta de la API no incluye ninguna sección válida.")

        for i, seccion in enumerate(secciones, start=1):
            if not isinstance(seccion, dict):
                raise ContentGenerationError(
                    f"La sección {i} debería ser un objeto con 'titulo' y 'bloques', "
                    f"pero se recibió un valor de tipo {type(seccion).__name__} ({seccion!r})."
                )
            if "titulo" not in seccion or "bloques" not in seccion:
                raise ContentGenerationError(f"La sección {i} no tiene 'titulo' y/o 'bloques'.")

            # -- Nivel 2: bloques dentro de cada sección --------------------
            bloques = seccion["bloques"]
            if not isinstance(bloques, list):
                raise ContentGenerationError(
                    f"Los 'bloques' de la sección {i} deberían ser una lista y se "
                    f"recibió {type(bloques).__name__}."
                )
            for j, bloque in enumerate(bloques, start=1):
                if not isinstance(bloque, dict) or "tipo" not in bloque:
                    raise ContentGenerationError(
                        f"El bloque {j} de la sección {i} no es un objeto válido "
                        f"con clave 'tipo' (se recibió {bloque!r})."
                    )

        return contenido
