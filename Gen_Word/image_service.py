"""
image_service.py
================================================================================
Resuelve una "consulta" en lenguaje natural (p. ej. "solar panels rooftop")
en la ruta de un archivo de imagen local, listo para insertar en el
documento.

Estrategia de resolución (en el orden definido en
``config.ORDEN_PROVEEDORES_IMAGENES``):

    1. Unsplash  — requiere UNSPLASH_ACCESS_KEY (gratuita).
    2. Pexels    — requiere PEXELS_API_KEY (gratuita).
    3. Placeholder — no requiere ninguna clave: se genera localmente con
       Pillow una ilustración plana con la temática solicitada, para que
       el documento NUNCA se quede sin imagen aunque no haya conexión a
       internet, no se hayan configurado claves, o el banco de imágenes
       no tenga resultados para esa búsqueda.

Cada imagen descargada (o generada) se cachea en disco por consulta, para
no repetir la misma llamada de red dos veces dentro de una misma ejecución
si dos figuras piden la misma `image_query`.
================================================================================
"""

from __future__ import annotations

import hashlib
import logging
import os
from dataclasses import dataclass
from typing import Optional

import requests
from PIL import Image, ImageDraw, ImageFont

import config

logger = logging.getLogger(__name__)


@dataclass
class ImageServiceConfig:
    """Claves y parámetros del servicio de imágenes. Cualquier clave puede
    dejarse en ``None``: ese proveedor simplemente se saltará."""

    unsplash_access_key: Optional[str] = None
    pexels_api_key: Optional[str] = None
    cache_dir: str = config.IMAGE_CACHE_DIR
    ancho_descarga_px: int = config.ANCHO_IMAGEN_DESCARGA_PX
    timeout_segundos: int = config.TIMEOUT_RED_SEGUNDOS


class ImageService:
    """Busca, descarga y cachea imágenes para ilustrar el documento.

    Ejemplo:
        >>> servicio = ImageService(ImageServiceConfig(unsplash_access_key="..."))
        >>> ruta = servicio.obtener_imagen("mountain lake sunrise")
    """

    def __init__(self, cfg: ImageServiceConfig) -> None:
        self._cfg = cfg
        os.makedirs(cfg.cache_dir, exist_ok=True)

    # -- API pública -----------------------------------------------------

    def obtener_imagen(self, query: str, *, indice_figura: int = 0) -> str:
        """Devuelve la ruta local de una imagen relevante para ``query``.

        Prueba los proveedores en el orden de
        ``config.ORDEN_PROVEEDORES_IMAGENES``. Cualquier fallo (sin clave,
        error de red, sin resultados) se registra como aviso y se pasa
        al siguiente proveedor; el "placeholder" final nunca falla, así
        que este método siempre devuelve una ruta válida.
        """
        query_normalizada = query.strip() or "abstract background"
        ruta_cache = self._ruta_cache(query_normalizada)
        if os.path.exists(ruta_cache):
            logger.info("Imagen en caché para %r → %s", query_normalizada, ruta_cache)
            return ruta_cache

        proveedores = {
            "unsplash": self._descargar_de_unsplash,
            "pexels": self._descargar_de_pexels,
            "placeholder": self._generar_placeholder,
        }

        for nombre in config.ORDEN_PROVEEDORES_IMAGENES:
            funcion = proveedores.get(nombre)
            if funcion is None:
                continue
            try:
                datos = funcion(query_normalizada, indice_figura)
            except Exception as exc:  # noqa: BLE001 — cualquier fallo cae al siguiente proveedor
                logger.warning("Proveedor %r falló para %r: %s", nombre, query_normalizada, exc)
                continue
            if datos:
                with open(ruta_cache, "wb") as f:
                    f.write(datos)
                logger.info("Imagen de %r obtenida vía %r → %s", query_normalizada, nombre, ruta_cache)
                return ruta_cache

        # Esto no debería ocurrir nunca (el placeholder siempre produce
        # datos), pero se deja como red de seguridad explícita.
        raise RuntimeError(f"No se pudo obtener ninguna imagen para: {query_normalizada!r}")

    # -- Proveedores -------------------------------------------------------

    def _descargar_de_unsplash(self, query: str, _indice: int) -> Optional[bytes]:
        """Busca una foto en Unsplash y devuelve sus bytes, o None si el
        proveedor no está configurado o no hay resultados."""
        if not self._cfg.unsplash_access_key:
            return None

        resp = requests.get(
            "https://api.unsplash.com/search/photos",
            params={"query": query, "per_page": 1, "orientation": "landscape"},
            headers={"Authorization": f"Client-ID {self._cfg.unsplash_access_key}"},
            timeout=self._cfg.timeout_segundos,
        )
        resp.raise_for_status()
        resultados = resp.json().get("results", [])
        if not resultados:
            return None

        url_imagen = resultados[0]["urls"]["regular"]
        return self._descargar_bytes(url_imagen)

    def _descargar_de_pexels(self, query: str, _indice: int) -> Optional[bytes]:
        """Busca una foto en Pexels y devuelve sus bytes, o None si el
        proveedor no está configurado o no hay resultados."""
        if not self._cfg.pexels_api_key:
            return None

        resp = requests.get(
            "https://api.pexels.com/v1/search",
            params={"query": query, "per_page": 1, "orientation": "landscape"},
            headers={"Authorization": self._cfg.pexels_api_key},
            timeout=self._cfg.timeout_segundos,
        )
        resp.raise_for_status()
        fotos = resp.json().get("photos", [])
        if not fotos:
            return None

        url_imagen = fotos[0]["src"]["large"]
        return self._descargar_bytes(url_imagen)

    def _descargar_bytes(self, url: str) -> bytes:
        resp = requests.get(url, timeout=self._cfg.timeout_segundos)
        resp.raise_for_status()
        return resp.content

    def _generar_placeholder(self, query: str, indice: int) -> bytes:
        """Genera localmente (sin red) una ilustración plana que sirve de
        imagen de reserva: un fondo con degradado suave en la paleta del
        documento y el texto de la consulta, a modo de "figura pendiente
        de foto". Nunca falla."""
        ancho, alto = 1200, 750
        img = Image.new("RGB", (ancho, alto), self._hex_a_rgb(config.PALETA.teal_light))
        draw = ImageDraw.Draw(img)

        # Banda superior de color sólido, a modo de "cabecera" de la imagen.
        banda_h = 90
        colores_banda = [config.PALETA.navy, config.PALETA.teal, config.PALETA.orange]
        color_banda = colores_banda[indice % len(colores_banda)]
        draw.rectangle([0, 0, ancho, banda_h], fill=self._hex_a_rgb(color_banda))

        # Icono decorativo simple (marco de "foto") centrado.
        icono_w, icono_h = 220, 160
        icono_x = (ancho - icono_w) // 2
        icono_y = (alto - icono_h) // 2 - 40
        draw.rounded_rectangle(
            [icono_x, icono_y, icono_x + icono_w, icono_y + icono_h],
            radius=16, outline=self._hex_a_rgb(config.PALETA.navy_soft), width=6,
        )
        draw.ellipse(
            [icono_x + 30, icono_y + 25, icono_x + 70, icono_y + 65],
            outline=self._hex_a_rgb(config.PALETA.navy_soft), width=6,
        )
        draw.polygon(
            [
                (icono_x + 20, icono_y + icono_h - 20),
                (icono_x + 90, icono_y + 70),
                (icono_x + 140, icono_y + 110),
                (icono_x + 180, icono_y + 70),
                (icono_x + icono_w - 20, icono_y + icono_h - 20),
            ],
            outline=self._hex_a_rgb(config.PALETA.navy_soft), width=6,
        )

        # Texto con la consulta (a modo de descripción de la imagen).
        fuente = self._fuente(28, bold=True)
        texto = query if len(query) <= 40 else query[:37] + "…"
        bbox = draw.textbbox((0, 0), texto, font=fuente)
        tw = bbox[2] - bbox[0]
        draw.text(
            ((ancho - tw) / 2, icono_y + icono_h + 30),
            texto, font=fuente, fill=self._hex_a_rgb(config.PALETA.text),
        )

        import io
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        return buffer.getvalue()

    # -- Utilidades internas ------------------------------------------------

    def _ruta_cache(self, query: str) -> str:
        clave = hashlib.md5(query.lower().encode("utf-8")).hexdigest()
        return os.path.join(self._cfg.cache_dir, f"{clave}.img")

    @staticmethod
    def _hex_a_rgb(hex_color: str) -> tuple[int, int, int]:
        return tuple(int(hex_color[i:i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]

    @staticmethod
    def _fuente(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
        nombre = "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"
        ruta = f"/usr/share/fonts/truetype/dejavu/{nombre}"
        try:
            return ImageFont.truetype(ruta, size)
        except OSError:
            return ImageFont.load_default()
