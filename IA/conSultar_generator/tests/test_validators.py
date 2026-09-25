"""
test_validators.py
====================
Pruebas de `generator.validators`: una configuración válida no debe
lanzar ninguna excepción, y cada regla de validación relevante debe
detectar su caso inválido correspondiente.
"""
import unittest

from generator.config import construir_configuracion
from generator.validators import ErrorDeValidacion, validar_configuracion

CONFIG_MINIMA_VALIDA = {
    "aplicacion": {"nombre": "ConSultar", "archivo_salida": "consultar.html"},
    "modelos": {
        "modelo_por_defecto": "m1",
        "disponibles": [{"id": "m1", "nombre": "Modelo Uno", "max_output_tokens": 4096}],
    },
    "api": {"endpoint": "https://api.anthropic.com/v1/messages"},
    "prompts": {
        "mejora": {"system": "system 1", "user": "{{consulta}}", "max_tokens": 512},
        "final": {"system": "{{rol_usuario}}", "user": "{{consulta_mejorada}}", "max_tokens": 4096},
    },
    "tema": {"color_primario": "#2E6DA4"},
    "exports": {"formato_por_defecto": "markdown"},
}


def _config_valida(sobrescribir: dict | None = None) -> "ConfiguracionApp":  # type: ignore[name-defined]
    import copy
    datos = copy.deepcopy(CONFIG_MINIMA_VALIDA)
    if sobrescribir:
        _fusionar(datos, sobrescribir)
    return construir_configuracion(datos)


def _fusionar(base: dict, extra: dict) -> None:
    for clave, valor in extra.items():
        if isinstance(valor, dict) and isinstance(base.get(clave), dict):
            _fusionar(base[clave], valor)
        else:
            base[clave] = valor


class TestConfiguracionValida(unittest.TestCase):
    def test_configuracion_minima_no_lanza_excepcion(self) -> None:
        config = _config_valida()
        advertencias = validar_configuracion(config)
        self.assertIsInstance(advertencias, list)


class TestErroresDetectados(unittest.TestCase):
    def _esperar_error(self, sobrescribir: dict, fragmento: str) -> None:
        config = _config_valida(sobrescribir)
        with self.assertRaises(ErrorDeValidacion) as ctx:
            validar_configuracion(config)
        self.assertIn(fragmento, str(ctx.exception))

    def test_nombre_de_aplicacion_vacio(self) -> None:
        self._esperar_error({"aplicacion": {"nombre": ""}}, "aplicacion.nombre")

    def test_archivo_salida_sin_extension_html(self) -> None:
        self._esperar_error({"aplicacion": {"archivo_salida": "salida"}}, "archivo_salida")

    def test_sin_modelos_disponibles(self) -> None:
        self._esperar_error({"modelos": {"disponibles": []}}, "modelos.disponibles")

    def test_modelo_por_defecto_no_coincide(self) -> None:
        self._esperar_error({"modelos": {"modelo_por_defecto": "no-existe"}}, "modelo_por_defecto")

    def test_color_invalido(self) -> None:
        self._esperar_error({"tema": {"color_primario": "no-es-un-color"}}, "color_primario")

    def test_ancho_maximo_invalido(self) -> None:
        self._esperar_error({"tema": {"ancho_maximo": "muy-ancho"}}, "ancho_maximo")

    def test_formato_por_defecto_no_reconocido(self) -> None:
        self._esperar_error({"exports": {"formato_por_defecto": "excel"}}, "formato_por_defecto")

    def test_formato_por_defecto_desactivado(self) -> None:
        self._esperar_error(
            {"exports": {"formato_por_defecto": "pdf", "pdf": {"activo": False}}},
            "formato_por_defecto",
        )

    def test_exportacion_visible_sin_formatos_activos(self) -> None:
        self._esperar_error(
            {
                "visibilidad": {"mostrar_exportacion": True},
                "exports": {
                    "markdown": {"activo": False},
                    "word": {"activo": False},
                    "pdf": {"activo": False},
                },
            },
            "mostrar_exportacion",
        )

    def test_sanitizador_desactivado(self) -> None:
        self._esperar_error({"librerias": {"sanitizador": {"activa": False}}}, "sanitizador")

    def test_word_activo_sin_libreria_docx(self) -> None:
        self._esperar_error(
            {"exports": {"word": {"activo": True}}, "librerias": {"docx": {"activa": False}}},
            "librerias.docx",
        )

    def test_temperatura_fuera_de_rango(self) -> None:
        self._esperar_error({"prompts": {"mejora": {"temperature": 1.5}}}, "temperature")


if __name__ == "__main__":
    unittest.main()
