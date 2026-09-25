"""
test_config.py
===============
Pruebas de `generator.config`: carga de archivos YAML/JSON, resolución de
valores por defecto ante claves ausentes, y detección de errores de
lectura (archivo inexistente, formato no soportado, YAML/JSON mal
formado).
"""
import json
import tempfile
import unittest
from pathlib import Path

from generator.config import (
    ErrorDeConfiguracion,
    cargar_configuracion,
    construir_configuracion,
)


class TestCargaDeConfiguracion(unittest.TestCase):
    def setUp(self) -> None:
        self._directorio_temporal = tempfile.TemporaryDirectory()
        self.directorio = Path(self._directorio_temporal.name)

    def tearDown(self) -> None:
        self._directorio_temporal.cleanup()

    def test_archivo_inexistente_lanza_error(self) -> None:
        with self.assertRaises(ErrorDeConfiguracion):
            cargar_configuracion(self.directorio / "no-existe.yaml")

    def test_extension_no_soportada_lanza_error(self) -> None:
        ruta = self.directorio / "config.txt"
        ruta.write_text("aplicacion: {}", encoding="utf-8")
        with self.assertRaises(ErrorDeConfiguracion):
            cargar_configuracion(ruta)

    def test_json_valido_se_carga_correctamente(self) -> None:
        datos = {
            "aplicacion": {"nombre": "MiApp", "archivo_salida": "salida.html"},
            "modelos": {
                "modelo_por_defecto": "m1",
                "disponibles": [{"id": "m1", "nombre": "Modelo Uno", "max_output_tokens": 1000}],
            },
        }
        ruta = self.directorio / "config.json"
        ruta.write_text(json.dumps(datos), encoding="utf-8")

        config = cargar_configuracion(ruta)
        self.assertEqual(config.aplicacion.nombre, "MiApp")
        self.assertEqual(config.modelos.disponibles[0].id, "m1")

    def test_json_mal_formado_lanza_error(self) -> None:
        ruta = self.directorio / "config.json"
        ruta.write_text("{ esto no es json valido", encoding="utf-8")
        with self.assertRaises(ErrorDeConfiguracion):
            cargar_configuracion(ruta)

    def test_raiz_no_es_un_mapa_lanza_error(self) -> None:
        ruta = self.directorio / "config.json"
        ruta.write_text(json.dumps(["esto", "es", "una", "lista"]), encoding="utf-8")
        with self.assertRaises(ErrorDeConfiguracion):
            cargar_configuracion(ruta)


class TestValoresPorDefecto(unittest.TestCase):
    """`construir_configuracion` debe resolver, con valores por defecto
    razonables, cualquier clave ausente en el diccionario de entrada."""

    def test_configuracion_vacia_no_lanza_excepcion(self) -> None:
        config = construir_configuracion({})
        self.assertEqual(config.aplicacion.nombre, "ConSultar")
        self.assertEqual(config.aplicacion.archivo_salida, "consultar.html")
        self.assertEqual(config.modelos.disponibles, [])
        self.assertTrue(config.visibilidad.mostrar_exportacion)
        self.assertTrue(config.librerias.markdown.activa)

    def test_valores_indicados_sobrescriben_los_por_defecto(self) -> None:
        config = construir_configuracion({
            "aplicacion": {"nombre": "OtraApp"},
            "tema": {"color_primario": "#123456"},
        })
        self.assertEqual(config.aplicacion.nombre, "OtraApp")
        self.assertEqual(config.tema.color_primario, "#123456")
        # Un campo no indicado en 'tema' debe conservar su valor por defecto:
        self.assertEqual(config.tema.color_fondo, "#F4F9FC")

    def test_modelo_sin_notas_usa_cadena_vacia(self) -> None:
        config = construir_configuracion({
            "modelos": {"disponibles": [{"id": "m1", "nombre": "Uno", "max_output_tokens": 100}]}
        })
        self.assertEqual(config.modelos.disponibles[0].notas, "")


if __name__ == "__main__":
    unittest.main()
