"""
config.py
================================================================================
Configuración central del generador de documentos Word.

Este módulo NO contiene lógica de negocio: es el único lugar donde se
definen constantes de estilo (colores, tipografías, tamaños de página),
rutas de trabajo y parámetros por defecto. Si en el futuro quieres dar
al documento otra identidad visual (otra paleta, otra universidad, otro
logotipo de portada), este es el archivo que hay que tocar — el resto
del programa no necesita cambiar.

La fidelidad visual del documento original (portada con bloque de color,
índice manual, cajas de aviso, encabezado/pie con número de página) se
conserva íntegramente: lo único que ahora es "genérico" es el CONTENIDO
(tema, textos e imágenes), no el DISEÑO.
================================================================================
"""

from __future__ import annotations

import os
from dataclasses import dataclass


# ==============================================================================
# RUTAS DE TRABAJO
# ==============================================================================

#: Directorio base del proyecto (donde vive este archivo).
BASE_DIR: str = os.path.dirname(os.path.abspath(__file__))

#: Directorio donde se guardan los documentos generados.
OUTPUT_DIR: str = os.path.join(BASE_DIR, "salida")

#: Directorio donde se cachean las imágenes descargadas/generadas, para no
#: volver a descargar la misma imagen dos veces dentro de la misma sesión
#: de trabajo (se organiza por proyecto/tema en tiempo de ejecución).
IMAGE_CACHE_DIR: str = os.path.join(OUTPUT_DIR, "img_cache")


# ==============================================================================
# TIPOGRAFÍA
# ==============================================================================

FONT_NAME: str = "Calibri"       # Fuente de párrafos, títulos y portada.
FONT_MONO: str = "Consolas"      # Fuente para fragmentos de código / URLs.


# ==============================================================================
# PALETA DE COLORES (idéntica a la plantilla original)
# ==============================================================================

@dataclass(frozen=True)
class Paleta:
    """Colores corporativos del documento, en formato hexadecimal 'RRGGBB'
    (sin '#', que es el formato que exige python-docx / OOXML)."""

    navy: str = "1A2A44"         # Azul marino — portada y títulos H1.
    navy_soft: str = "34496C"    # Azul marino suave — subtítulos H2.
    teal: str = "279594"         # Verde azulado — acentos, viñetas, filetes.
    teal_light: str = "D6F0EF"   # Verde azulado claro — subtítulo de portada.
    orange: str = "E9892F"       # Naranja — avisos de tipo "importante".
    orange_light: str = "FBEEDF"
    gray: str = "6B7480"         # Gris — texto secundario, pies de figura.
    gray_light: str = "E1E5E9"   # Gris claro — bordes y separadores sutiles.
    text: str = "212936"         # Color de texto principal del cuerpo.
    note_bg: str = "F2F8F7"      # Fondo de cajas de nota/consejo.


PALETA = Paleta()


# ==============================================================================
# PÁGINA Y MAQUETACIÓN
# ==============================================================================

@dataclass(frozen=True)
class Maquetacion:
    """Medidas de página, márgenes y tamaños por defecto (en centímetros,
    salvo que se indique lo contrario)."""

    ancho_pagina_cm: float = 21.0     # A4
    alto_pagina_cm: float = 29.7      # A4

    margen_portada_cm: float = 2.0
    margen_superior_cm: float = 2.3
    margen_inferior_cm: float = 2.1
    margen_lateral_cm: float = 2.3

    ancho_figura_cm_defecto: float = 12.0   # Ancho por defecto de una imagen.


MAQUETACION = Maquetacion()


# ==============================================================================
# MODELO DE LENGUAJE (ANTHROPIC)
# ==============================================================================

#: Modelo usado para generar el contenido del documento. Ver
#: https://docs.claude.com para el listado de modelos disponibles.
MODELO_ANTHROPIC: str = "claude-sonnet-5"

#: Límite de tokens de salida. El contenido de un documento con varias
#: secciones puede ser extenso; se deja margen amplio para evitar que la
#: respuesta se corte a mitad de una sección.
MAX_TOKENS_CONTENIDO: int = 8000

#: Reintentos ante errores transitorios de red/servidor al llamar a la API.
REINTENTOS_API: int = 3


# ==============================================================================
# BÚSQUEDA DE IMÁGENES
# ==============================================================================

#: Proveedores de imágenes admitidos, en orden de preferencia. Si el
#: primero no está configurado (sin API key) o falla, se prueba el
#: siguiente; si todos fallan, se genera una imagen de marcador de
#: posición (ver image_service.py) para que el documento nunca se quede
#: sin ilustración.
ORDEN_PROVEEDORES_IMAGENES: tuple[str, ...] = ("unsplash", "pexels", "placeholder")

#: Tamaño (px) al que se solicitan/redimensionan las imágenes descargadas.
ANCHO_IMAGEN_DESCARGA_PX: int = 1600

#: Tiempo máximo (segundos) de espera por una respuesta de red.
TIMEOUT_RED_SEGUNDOS: int = 15
