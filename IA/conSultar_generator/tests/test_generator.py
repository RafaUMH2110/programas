"""
test_generator.py
===================
Pruebas de extremo a extremo: cargar → validar → renderizar → escribir.
Usan el `config.yaml` real del proyecto para comprobar que el generador
completo produce un archivo HTML coherente, y comprueban también que un
error de validación NO deja ningún archivo a medio escribir.
"""
import re
import tempfile
import unittest
from pathlib import Path

from generator.generator import ErrorDeGeneracion, generar_aplicacion

RUTA_CONFIG_REAL = Path(__file__).resolve().parent.parent / "config.yaml"


class TestGeneracionCompleta(unittest.TestCase):
    def setUp(self) -> None:
        self._directorio_temporal = tempfile.TemporaryDirectory()
        self.directorio_salida = Path(self._directorio_temporal.name)

    def tearDown(self) -> None:
        self._directorio_temporal.cleanup()

    def test_genera_un_archivo_html_valido(self) -> None:
        ruta_salida = generar_aplicacion(RUTA_CONFIG_REAL, directorio_salida_override=self.directorio_salida)
        self.assertIsNotNone(ruta_salida)
        self.assertTrue(ruta_salida.exists())
        self.assertEqual(ruta_salida.suffix, ".html")

        contenido = ruta_salida.read_text(encoding="utf-8")
        self.assertTrue(contenido.startswith("<!DOCTYPE html>"))
        self.assertIn('<html lang="es">', contenido)
        self.assertIn("ConSultar", contenido)

    def test_no_quedan_etiquetas_jinja_sin_resolver(self) -> None:
        """Cualquier '{%' indica una plantilla mal cerrada; los '{{marcador}}'
        legítimos de los prompts (p. ej. '{{consulta}}') SÍ deben permanecer,
        ya que los sustituye la aplicación generada en el navegador, no el
        generador Python."""
        ruta_salida = generar_aplicacion(RUTA_CONFIG_REAL, directorio_salida_override=self.directorio_salida)
        contenido = ruta_salida.read_text(encoding="utf-8")
        self.assertNotIn("{%", contenido)
        self.assertNotIn("{#", contenido)
        # Los marcadores de prompt sí deben seguir presentes:
        self.assertIn("{{consulta}}", contenido)

    def test_incluye_las_cuatro_dependencias_por_defecto(self) -> None:
        ruta_salida = generar_aplicacion(RUTA_CONFIG_REAL, directorio_salida_override=self.directorio_salida)
        contenido = ruta_salida.read_text(encoding="utf-8")
        urls = re.findall(r'<script src="([^"]+)">', contenido)
        self.assertEqual(len(urls), 4)

    def test_modo_validate_no_escribe_archivo(self) -> None:
        resultado = generar_aplicacion(RUTA_CONFIG_REAL, directorio_salida_override=self.directorio_salida, solo_validar=True)
        self.assertIsNone(resultado)
        self.assertEqual(list(self.directorio_salida.glob("*")), [])

    def test_configuracion_invalida_no_genera_archivo_parcial(self) -> None:
        with tempfile.TemporaryDirectory() as directorio_config:
            ruta_config_mala = Path(directorio_config) / "config.yaml"
            ruta_config_mala.write_text("aplicacion:\n  nombre: ''\n", encoding="utf-8")

            with self.assertRaises(ErrorDeGeneracion):
                generar_aplicacion(ruta_config_mala, directorio_salida_override=self.directorio_salida)

            self.assertEqual(list(self.directorio_salida.glob("*")), [])

    def test_modelo_html_select_contiene_los_modelos_configurados(self) -> None:
        ruta_salida = generar_aplicacion(RUTA_CONFIG_REAL, directorio_salida_override=self.directorio_salida)
        contenido = ruta_salida.read_text(encoding="utf-8")
        self.assertIn("Claude Sonnet 5", contenido)
        self.assertIn("Claude Opus 4.1 (legacy)", contenido)


if __name__ == "__main__":
    unittest.main()
