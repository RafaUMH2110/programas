"""
templates.py
============
Configuración del entorno Jinja2 y renderizado de las plantillas que
componen la aplicación web ConSultar generada.

Arquitectura de plantillas
--------------------------
``templates/index.html.j2`` es la plantilla principal: define la estructura
HTML completa e incluye, mediante ``{% include %}``, tanto
``templates/styles.css.j2`` (dentro de un bloque ``<style>``) como
``templates/app.js.j2`` (dentro de un bloque ``<script>``). Mantenerlas en
archivos separados permite editar el HTML, el CSS y el JavaScript de forma
independiente, aunque las tres compartan el mismo contexto de Jinja2 (el
objeto ``config``).

Seguridad al insertar valores de configuración
-----------------------------------------------
El entorno se crea con ``autoescape=False`` porque una misma plantilla
combina HTML, CSS y JavaScript, y cada lenguaje necesita un escapado
distinto. En su lugar, cada plantilla aplica el filtro adecuado de forma
explícita en cada punto donde se inserta un valor que proviene de la
configuración (y que, por tanto, no se puede asumir seguro):

  * ``| e``  → escapa HTML (texto de etiquetas y valores de atributos).
  * ``| js`` → serializa el valor como literal JavaScript seguro (JSON,
    neutralizando además la secuencia ``</`` para que un valor de
    configuración no pueda cerrar prematuramente la etiqueta ``<script>``).

Los colores, medidas y nombres de fuente del tema, así como los
identificadores de modelo, se insertan directamente en el CSS/JS sin pasar
por ``| js`` ni ``| e`` porque `validators.py` ya obliga a que cumplan un
formato estricto (por ejemplo, un color debe ser ``#RRGGBB``) antes de que
la generación llegue a esta fase; de lo contrario, `generar_aplicacion`
nunca invoca al renderizador.
"""
from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from .config import ConfiguracionApp

RUTA_PLANTILLAS = Path(__file__).resolve().parent.parent / "templates"


def _filtro_js(valor) -> str:
    """Serializa `valor` como literal JavaScript seguro para insertarlo
    dentro de un bloque <script> (ver docstring del módulo)."""
    return json.dumps(valor, ensure_ascii=False).replace("</", "<\\/")


def crear_entorno() -> Environment:
    """Crea y configura el entorno Jinja2 usado para renderizar las tres
    plantillas del proyecto (HTML, CSS y JavaScript)."""
    entorno = Environment(
        loader=FileSystemLoader(str(RUTA_PLANTILLAS)),
        autoescape=False,
        undefined=StrictUndefined,  # una variable no definida debe fallar, no generar "None" silencioso
        trim_blocks=True,
        lstrip_blocks=True,
    )
    entorno.filters["js"] = _filtro_js
    return entorno


def _construir_datos_js(config: ConfiguracionApp) -> dict:
    """Aplana las partes de la configuración que `app.js.j2` necesita como
    literales JavaScript (objetos/listas JSON) en un único diccionario
    compuesto solo por tipos nativos de Python (str, int, float, bool,
    None, list, dict), que es lo único que `json.dumps` puede serializar.
    Las dataclasses (`ModeloInfo`, etc.) se convierten explícitamente con
    `dataclasses.asdict`."""
    return {
        "modelos": [asdict(modelo) for modelo in config.modelos.disponibles],
        "modeloPorDefecto": config.modelos.modelo_por_defecto,
        "api": {
            "endpoint": config.api.endpoint,
            "version": config.api.version_api,
            "timeoutMs": config.api.timeout_segundos * 1000,
            "reintentos": config.api.reintentos,
        },
        "prompts": {
            "mejora": {
                "system": config.prompts.mejora.system,
                "user": config.prompts.mejora.user,
                "maxTokens": config.prompts.mejora.max_tokens,
                "temperature": config.prompts.mejora.temperature,
                "modelo": config.prompts.mejora.modelo,
            },
            "final": {
                "system": config.prompts.final.system,
                "user": config.prompts.final.user,
                "maxTokens": config.prompts.final.max_tokens,
                "temperature": config.prompts.final.temperature,
                "modelo": config.prompts.final.modelo,
            },
        },
        "mensajes": {
            "paso1": config.ui.mensaje_paso_1,
            "paso2": config.ui.mensaje_paso_2,
            "exito": config.ui.mensaje_exito,
            "exportSinResultado": config.ui.mensaje_export_sin_resultado,
            "exportCheckboxDesactivado": config.ui.mensaje_export_checkbox_desactivado,
            "exportGenerado": config.ui.mensaje_export_generado,
            "botonConsultar": config.ui.boton_consultar,
        },
        "exports": {
            "markdownActivo": config.exports.markdown.activo,
            "wordActivo": config.exports.word.activo,
            "pdfActivo": config.exports.pdf.activo,
            "formatoPorDefecto": config.exports.formato_por_defecto,
            "nombreArchivoPorDefecto": config.exports.nombre_archivo_por_defecto,
        },
        "visibilidad": {
            "mostrarExportacion": config.visibilidad.mostrar_exportacion,
        },
    }


def renderizar_aplicacion(config: ConfiguracionApp) -> str:
    """Renderiza `index.html.j2` (que a su vez incluye las plantillas de CSS
    y JavaScript) y devuelve el documento HTML completo como una única
    cadena de texto, lista para escribirse en el archivo de salida."""
    entorno = crear_entorno()
    plantilla = entorno.get_template("index.html.j2")
    return plantilla.render(config=config, datos_js=_construir_datos_js(config))

