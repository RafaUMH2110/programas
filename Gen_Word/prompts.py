"""
prompts.py
================================================================================
Todos los textos que se envían al modelo de lenguaje viven en este archivo,
y solo en este archivo. Si quieres cambiar el tono, el idioma por defecto,
la cantidad de secciones que pide, o las instrucciones de estilo, edita
las plantillas de abajo — no hace falta tocar `content_generator.py`.

Las plantillas usan `str.format(**kwargs)`, así que cualquier '{' o '}'
literal debe escribirse duplicado ('{{' / '}}'), tal y como ya se hace en
los pocos sitios donde aparecen en el JSON de ejemplo.
================================================================================
"""

from __future__ import annotations

# ------------------------------------------------------------------------------
# Prompt de sistema: define el "rol" y las reglas generales del redactor.
# ------------------------------------------------------------------------------
SYSTEM_PROMPT: str = (
    "Eres un redactor técnico y editorial experto en producir documentos "
    "profesionales, claros y bien estructurados sobre cualquier materia. "
    "Escribes en un {idioma} correcto, con un tono {tono}. "
    "Debes llamar SIEMPRE a la herramienta 'guardar_contenido_documento' "
    "con el contenido completo que se te pide, sin dejar ninguna sección "
    "a medias y sin repetir literalmente el enunciado del usuario. "
    "Respeta EXACTAMENTE la forma del esquema: 'secciones' es una lista "
    "de OBJETOS, cada uno con las claves 'titulo' (texto) y 'bloques' "
    "(lista de OBJETOS con clave 'tipo'); nunca uses cadenas de texto "
    "sueltas donde el esquema pide un objeto."
)

# ------------------------------------------------------------------------------
# Prompt de usuario: describe la tarea concreta (tema, audiencia, estructura).
# Placeholders disponibles: {tema}, {audiencia}, {num_secciones}, {idioma},
# {tono}, {instrucciones_adicionales}.
# ------------------------------------------------------------------------------
USER_PROMPT_TEMPLATE: str = """
Redacta el contenido completo de un documento profesional en formato Word
sobre el siguiente tema:

    TEMA: {tema}

Va dirigido a: {audiencia}.

Estructura el documento en {num_secciones} secciones numeradas, con una
progresión lógica (de lo general a lo específico, o en el orden natural
en que se explicaría el tema a alguien que lo aborda por primera vez).
Cada sección debe tener un título claro y descriptivo.

Dentro de cada sección, combina con criterio editorial los siguientes
tipos de bloque (no es necesario usarlos todos en cada sección):

  - "parrafo": texto explicativo, párrafos breves (máx. 4-5 líneas).
  - "subtitulo": un subapartado dentro de la sección.
  - "vinetas": una lista de puntos breves y accionables.
  - "nota": una caja de aviso destacada (usa "estilo": "teal" para
    consejos/información y "estilo": "orange" para advertencias
    importantes). Úsala con moderación (como mucho 1-2 por sección).
  - "url_destacada": una URL o fragmento de código corto, centrado y
    resaltado (solo si el tema lo justifica, p. ej. una web de
    referencia).
  - "figura": una imagen ilustrativa. Para cada figura, proporciona:
      · "image_query": 2-4 palabras clave EN INGLÉS, concretas y
        visuales, que describan exactamente lo que debería mostrar la
        fotografía (esto se usa para buscarla en un banco de imágenes,
        así que evita términos abstractos: mejor "solar panels
        rooftop" que "renewable energy concept").
      · "pie": el pie de figura, en el mismo idioma que el resto del
        documento, con el formato "Figura N. Descripción.".
      · "ancho_cm": opcional, ancho sugerido en centímetros (10-14).
  Incluye entre 2 y 5 figuras en total, repartidas en las secciones
  donde más aporten (no hace falta que todas las secciones tengan una).

Además, redacta:
  - Una portada con: un "kicker" (línea corta en mayúsculas que sitúe la
    categoría o el ámbito del tema), un título en dos líneas cortas
    ("titulo_linea_1" + "titulo_linea_2"), un subtítulo, y hasta tres
    líneas de pie de portada (organización/autoría/contexto) en
    "linea_1", "linea_2" (opcional) y "linea_3" (opcional).
  - Un índice con una entrada por cada sección (mismo texto que el
    título de la sección, sin el número).

{instrucciones_adicionales}

Llama a la herramienta 'guardar_contenido_documento' con todo este
contenido, en {idioma}, con un tono {tono}.
""".strip()

# ------------------------------------------------------------------------------
# Valores por defecto para los placeholders anteriores. `main.py` los usa
# si el usuario no especifica algo distinto por línea de comandos.
# ------------------------------------------------------------------------------
DEFAULTS: dict[str, str | int] = {
    "idioma": "español de España",
    "tono": "claro, cercano y profesional",
    "audiencia": "un público general con interés en el tema, sin conocimientos previos",
    "num_secciones": 6,
    "instrucciones_adicionales": "",
}


def construir_mensajes(
    tema: str,
    *,
    idioma: str | None = None,
    tono: str | None = None,
    audiencia: str | None = None,
    num_secciones: int | None = None,
    instrucciones_adicionales: str | None = None,
) -> tuple[str, str]:
    """Rellena las plantillas de prompt con los parámetros de la petición.

    Args:
        tema: El tema principal del documento (obligatorio).
        idioma: Idioma de redacción (por defecto, español de España).
        tono: Registro/tono deseado.
        audiencia: A quién va dirigido el documento.
        num_secciones: Número de secciones a generar.
        instrucciones_adicionales: Cualquier requisito extra en texto libre
            (p. ej. "incluye un apartado de bibliografía al final").

    Returns:
        Una tupla ``(system_prompt, user_prompt)`` lista para enviar a la API.
    """
    valores = {
        "tema": tema,
        "idioma": idioma or DEFAULTS["idioma"],
        "tono": tono or DEFAULTS["tono"],
        "audiencia": audiencia or DEFAULTS["audiencia"],
        "num_secciones": num_secciones or DEFAULTS["num_secciones"],
        "instrucciones_adicionales": instrucciones_adicionales or DEFAULTS["instrucciones_adicionales"],
    }
    system = SYSTEM_PROMPT.format(**valores)
    user = USER_PROMPT_TEMPLATE.format(**valores)
    return system, user
