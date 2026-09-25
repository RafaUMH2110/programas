"""
config.py
=========
Modelos de datos de configuración y función de carga del generador de
ConSultar.

Se ha elegido **YAML** como formato principal de configuración (con soporte
adicional para JSON) porque:

  * Es mucho más legible que JSON para humanos, especialmente en un archivo
    con decenas de claves anidadas como el que necesita este proyecto.
  * Admite comentarios (`#`), algo esencial para documentar cada opción
    directamente en el propio archivo `config.yaml`.
  * Es el formato de facto para la configuración de herramientas de
    desarrollo (CI/CD, contenedores, etc.), por lo que resulta familiar.

JSON se admite igualmente (detectado por la extensión del archivo) para
quien prefiera no añadir la dependencia de PyYAML o integrar la
configuración con otras herramientas que ya generen JSON.

Todos las clases de este módulo son `dataclasses` inmutables desde el punto
de vista conceptual (no se modifican tras construirse) que representan,
de forma tipada, cada sección del archivo de configuración.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

try:
    import yaml  # type: ignore
    _PYYAML_DISPONIBLE = True
except ImportError:  # pragma: no cover - se informa de forma clara en tiempo de ejecución
    yaml = None  # type: ignore
    _PYYAML_DISPONIBLE = False


class ErrorDeConfiguracion(Exception):
    """Se lanza cuando el archivo de configuración no existe, no se puede
    interpretar o le falta información imprescindible para construir el
    objeto de configuración (independientemente de si los VALORES son o no
    válidos; eso lo comprueba `validators.py`)."""


# ---------------------------------------------------------------------------
# Modelos de datos (una dataclass por sección del archivo de configuración)
# ---------------------------------------------------------------------------

@dataclass
class ModeloInfo:
    """Un modelo de IA disponible para elegir en la interfaz generada."""
    id: str
    nombre: str
    max_output_tokens: int
    notas: str = ""


@dataclass
class ModelosConfig:
    disponibles: list[ModeloInfo]
    modelo_por_defecto: str


@dataclass
class ApiConfig:
    proveedor: str
    endpoint: str
    version_api: str
    api_key_env: str
    timeout_segundos: int
    reintentos: int


@dataclass
class PromptConfig:
    """Configuración de una de las dos consultas del flujo (mejora o final).

    `system` y `user` son PLANTILLAS con marcadores de posición del tipo
    ``{{consulta}}`` que la aplicación generada sustituye en tiempo de
    ejecución (en el navegador), no en tiempo de generación. Ver la sección
    "Plantillas de prompts" del README para la lista completa de
    marcadores admitidos.

    `modelo`, si se indica, fuerza el uso de ese modelo (por id) para esta
    llamada concreta, independientemente del modelo que la persona elija en
    la interfaz. Si se deja vacío, se usa el modelo seleccionado en pantalla.
    """
    system: str
    user: str
    max_tokens: int
    temperature: Optional[float] = None
    modelo: Optional[str] = None


@dataclass
class PromptsConfig:
    mejora: PromptConfig
    final: PromptConfig


@dataclass
class TextosUI:
    """Todos los textos visibles de la interfaz generada, en un único lugar
    para poder traducir o adaptar la aplicación sin tocar las plantillas."""
    titulo: str
    subtitulo: str
    descripcion_cabecera: str

    titulo_seccion_config: str
    subtitulo_seccion_config: str
    titulo_seccion_consulta: str
    subtitulo_seccion_consulta: str
    titulo_seccion_resultado: str
    subtitulo_seccion_resultado: str

    etiqueta_api_key: str
    ayuda_api_key: str
    aviso_seguridad: str

    etiqueta_modelo: str
    etiqueta_tokens: str

    etiqueta_exportar_checkbox: str
    etiqueta_formato_exportacion: str
    etiqueta_nombre_archivo: str
    ayuda_nombre_archivo: str

    etiqueta_rol: str
    ayuda_rol: str
    valor_por_defecto_rol: str

    etiqueta_consulta: str
    placeholder_consulta: str
    ayuda_consulta: str

    boton_consultar: str
    boton_mostrar_clave: str
    boton_ocultar_clave: str
    boton_exportar: str

    placeholder_resultado: str

    mensaje_paso_1: str
    mensaje_paso_2: str
    mensaje_exito: str
    mensaje_export_sin_resultado: str
    mensaje_export_checkbox_desactivado: str
    mensaje_export_generado: str

    texto_pie_pagina: str
    correo_pie_pagina: str


@dataclass
class VisibilidadConfig:
    mostrar_aviso_seguridad: bool
    mostrar_exportacion: bool


@dataclass
class TemaConfig:
    color_primario: str
    color_primario_hover: str
    color_secundario: str
    color_fondo: str
    color_texto: str
    color_texto_tenue: str
    color_borde: str
    color_acento: str
    familia_tipografica: str
    familia_monoespaciada: str
    radio_borde: str
    sombra: str
    ancho_maximo: str


@dataclass
class FormatoExportConfig:
    activo: bool


@dataclass
class ExportsConfig:
    markdown: FormatoExportConfig
    word: FormatoExportConfig
    pdf: FormatoExportConfig
    formato_por_defecto: str
    nombre_archivo_por_defecto: str
    pdf_tamano_pagina: str
    pdf_margen_pt: int
    pdf_fuente: str
    word_fuente: str
    word_tamano_fuente_pt: int


@dataclass
class LibreriaConfig:
    activa: bool
    url: str


@dataclass
class LibreriasConfig:
    markdown: LibreriaConfig
    sanitizador: LibreriaConfig
    docx: LibreriaConfig
    jspdf: LibreriaConfig


@dataclass
class AplicacionConfig:
    nombre: str
    descripcion: str
    idioma_html: str
    idioma_interfaz: str
    archivo_salida: str
    directorio_salida: str


@dataclass
class ConfiguracionApp:
    """Raíz del árbol de configuración: agrupa todas las secciones."""
    aplicacion: AplicacionConfig
    modelos: ModelosConfig
    api: ApiConfig
    prompts: PromptsConfig
    ui: TextosUI
    visibilidad: VisibilidadConfig
    tema: TemaConfig
    exports: ExportsConfig
    librerias: LibreriasConfig


# ---------------------------------------------------------------------------
# Carga desde archivo
# ---------------------------------------------------------------------------

def _obtener(datos: dict[str, Any], clave: str, por_defecto: Any) -> Any:
    """Acceso tolerante a un diccionario anidado: si la clave no existe (por
    ejemplo, porque la persona ha editado `config.yaml` a mano y ha borrado
    una sección), se usa un valor por defecto razonable en lugar de fallar
    con un `KeyError`. Los errores por valores inválidos (no ausentes) los
    detecta `validators.py`, no esta función."""
    valor = datos.get(clave, por_defecto)
    return por_defecto if valor is None else valor


def _leer_archivo(ruta: Path) -> dict[str, Any]:
    if not ruta.exists():
        raise ErrorDeConfiguracion(
            f"No se encuentra el archivo de configuración: '{ruta}'.\n"
            f"Comprueba la ruta o indica otra con --config."
        )

    texto = ruta.read_text(encoding="utf-8")
    sufijo = ruta.suffix.lower()

    if sufijo in (".yaml", ".yml"):
        if not _PYYAML_DISPONIBLE:
            raise ErrorDeConfiguracion(
                "El archivo de configuración es YAML, pero el paquete 'PyYAML' "
                "no está instalado. Instala las dependencias con:\n"
                "    pip install -r requirements.txt"
            )
        try:
            datos = yaml.safe_load(texto)
        except yaml.YAMLError as exc:  # type: ignore[union-attr]
            raise ErrorDeConfiguracion(f"El archivo YAML no es válido:\n{exc}") from exc
    elif sufijo == ".json":
        try:
            datos = json.loads(texto)
        except json.JSONDecodeError as exc:
            raise ErrorDeConfiguracion(f"El archivo JSON no es válido:\n{exc}") from exc
    else:
        raise ErrorDeConfiguracion(
            f"Formato de configuración no soportado: '{ruta.suffix}'. "
            f"Usa un archivo .yaml, .yml o .json."
        )

    if datos is None:
        datos = {}
    if not isinstance(datos, dict):
        raise ErrorDeConfiguracion(
            "El archivo de configuración debe contener un mapa/objeto en su nivel raíz "
            "(por ejemplo, claves como 'aplicacion:', 'modelos:', etc.)."
        )
    return datos


def _construir_modelos(datos: dict[str, Any]) -> ModelosConfig:
    bruto = _obtener(datos, "modelos", {})
    disponibles_bruto = _obtener(bruto, "disponibles", [])
    disponibles = [
        ModeloInfo(
            id=str(_obtener(m, "id", "")),
            nombre=str(_obtener(m, "nombre", "")),
            max_output_tokens=int(_obtener(m, "max_output_tokens", 0)),
            notas=str(_obtener(m, "notas", "")),
        )
        for m in disponibles_bruto
    ]
    return ModelosConfig(
        disponibles=disponibles,
        modelo_por_defecto=str(_obtener(bruto, "modelo_por_defecto", "")),
    )


def _construir_api(datos: dict[str, Any]) -> ApiConfig:
    bruto = _obtener(datos, "api", {})
    return ApiConfig(
        proveedor=str(_obtener(bruto, "proveedor", "anthropic")),
        endpoint=str(_obtener(bruto, "endpoint", "https://api.anthropic.com/v1/messages")),
        version_api=str(_obtener(bruto, "version_api", "2023-06-01")),
        api_key_env=str(_obtener(bruto, "api_key_env", "ANTHROPIC_API_KEY")),
        timeout_segundos=int(_obtener(bruto, "timeout_segundos", 60)),
        reintentos=int(_obtener(bruto, "reintentos", 2)),
    )


def _construir_prompt(bruto: dict[str, Any]) -> PromptConfig:
    temperatura = _obtener(bruto, "temperature", None)
    return PromptConfig(
        system=str(_obtener(bruto, "system", "")),
        user=str(_obtener(bruto, "user", "")),
        max_tokens=int(_obtener(bruto, "max_tokens", 4096)),
        temperature=float(temperatura) if temperatura is not None else None,
        modelo=_obtener(bruto, "modelo", None),
    )


def _construir_prompts(datos: dict[str, Any]) -> PromptsConfig:
    bruto = _obtener(datos, "prompts", {})
    return PromptsConfig(
        mejora=_construir_prompt(_obtener(bruto, "mejora", {})),
        final=_construir_prompt(_obtener(bruto, "final", {})),
    )


def _construir_ui(datos: dict[str, Any]) -> TextosUI:
    b = _obtener(datos, "ui", {})
    return TextosUI(
        titulo=str(_obtener(b, "titulo", "ConSultar")),
        subtitulo=str(_obtener(b, "subtitulo", "")),
        descripcion_cabecera=str(_obtener(b, "descripcion_cabecera", "")),
        titulo_seccion_config=str(_obtener(b, "titulo_seccion_config", "Configuración")),
        subtitulo_seccion_config=str(_obtener(b, "subtitulo_seccion_config", "")),
        titulo_seccion_consulta=str(_obtener(b, "titulo_seccion_consulta", "Consulta")),
        subtitulo_seccion_consulta=str(_obtener(b, "subtitulo_seccion_consulta", "")),
        titulo_seccion_resultado=str(_obtener(b, "titulo_seccion_resultado", "Resultado")),
        subtitulo_seccion_resultado=str(_obtener(b, "subtitulo_seccion_resultado", "")),
        etiqueta_api_key=str(_obtener(b, "etiqueta_api_key", "Clave de API")),
        ayuda_api_key=str(_obtener(b, "ayuda_api_key", "")),
        aviso_seguridad=str(_obtener(b, "aviso_seguridad", "")),
        etiqueta_modelo=str(_obtener(b, "etiqueta_modelo", "Elegir Modelo")),
        etiqueta_tokens=str(_obtener(b, "etiqueta_tokens", "Número de tokens")),
        etiqueta_exportar_checkbox=str(_obtener(b, "etiqueta_exportar_checkbox", "Exportar resultado")),
        etiqueta_formato_exportacion=str(_obtener(b, "etiqueta_formato_exportacion", "Formato de exportación")),
        etiqueta_nombre_archivo=str(_obtener(b, "etiqueta_nombre_archivo", "Nombre del archivo")),
        ayuda_nombre_archivo=str(_obtener(b, "ayuda_nombre_archivo", "")),
        etiqueta_rol=str(_obtener(b, "etiqueta_rol", "Rol del usuario")),
        ayuda_rol=str(_obtener(b, "ayuda_rol", "")),
        valor_por_defecto_rol=str(_obtener(b, "valor_por_defecto_rol", "")),
        etiqueta_consulta=str(_obtener(b, "etiqueta_consulta", "Consulta")),
        placeholder_consulta=str(_obtener(b, "placeholder_consulta", "")),
        ayuda_consulta=str(_obtener(b, "ayuda_consulta", "")),
        boton_consultar=str(_obtener(b, "boton_consultar", "Consultar")),
        boton_mostrar_clave=str(_obtener(b, "boton_mostrar_clave", "Mostrar")),
        boton_ocultar_clave=str(_obtener(b, "boton_ocultar_clave", "Ocultar")),
        boton_exportar=str(_obtener(b, "boton_exportar", "Exportar fichero")),
        placeholder_resultado=str(_obtener(b, "placeholder_resultado", "")),
        mensaje_paso_1=str(_obtener(b, "mensaje_paso_1", "")),
        mensaje_paso_2=str(_obtener(b, "mensaje_paso_2", "")),
        mensaje_exito=str(_obtener(b, "mensaje_exito", "")),
        mensaje_export_sin_resultado=str(_obtener(b, "mensaje_export_sin_resultado", "")),
        mensaje_export_checkbox_desactivado=str(_obtener(b, "mensaje_export_checkbox_desactivado", "")),
        mensaje_export_generado=str(_obtener(b, "mensaje_export_generado", "")),
        texto_pie_pagina=str(_obtener(b, "texto_pie_pagina", "")),
        correo_pie_pagina=str(_obtener(b, "correo_pie_pagina", "")),
    )


def _construir_visibilidad(datos: dict[str, Any]) -> VisibilidadConfig:
    b = _obtener(datos, "visibilidad", {})
    return VisibilidadConfig(
        mostrar_aviso_seguridad=bool(_obtener(b, "mostrar_aviso_seguridad", True)),
        mostrar_exportacion=bool(_obtener(b, "mostrar_exportacion", True)),
    )


def _construir_tema(datos: dict[str, Any]) -> TemaConfig:
    b = _obtener(datos, "tema", {})
    return TemaConfig(
        color_primario=str(_obtener(b, "color_primario", "#2E6DA4")),
        color_primario_hover=str(_obtener(b, "color_primario_hover", "#24567F")),
        color_secundario=str(_obtener(b, "color_secundario", "#EAF3FB")),
        color_fondo=str(_obtener(b, "color_fondo", "#F4F9FC")),
        color_texto=str(_obtener(b, "color_texto", "#1E2A38")),
        color_texto_tenue=str(_obtener(b, "color_texto_tenue", "#57708A")),
        color_borde=str(_obtener(b, "color_borde", "#D8E6F1")),
        color_acento=str(_obtener(b, "color_acento", "#DCEBF7")),
        familia_tipografica=str(_obtener(b, "familia_tipografica", "'Inter', system-ui, sans-serif")),
        familia_monoespaciada=str(_obtener(b, "familia_monoespaciada", "ui-monospace, Menlo, Consolas, monospace")),
        radio_borde=str(_obtener(b, "radio_borde", "14px")),
        sombra=str(_obtener(b, "sombra", "0 1px 2px rgba(30,64,102,0.06), 0 8px 24px rgba(30,64,102,0.05)")),
        ancho_maximo=str(_obtener(b, "ancho_maximo", "980px")),
    )


def _construir_formato_export(bruto: dict[str, Any]) -> FormatoExportConfig:
    return FormatoExportConfig(activo=bool(_obtener(bruto, "activo", True)))


def _construir_exports(datos: dict[str, Any]) -> ExportsConfig:
    b = _obtener(datos, "exports", {})
    return ExportsConfig(
        markdown=_construir_formato_export(_obtener(b, "markdown", {})),
        word=_construir_formato_export(_obtener(b, "word", {})),
        pdf=_construir_formato_export(_obtener(b, "pdf", {})),
        formato_por_defecto=str(_obtener(b, "formato_por_defecto", "markdown")),
        nombre_archivo_por_defecto=str(_obtener(b, "nombre_archivo_por_defecto", "resultado")),
        pdf_tamano_pagina=str(_obtener(b, "pdf_tamano_pagina", "a4")),
        pdf_margen_pt=int(_obtener(b, "pdf_margen_pt", 50)),
        pdf_fuente=str(_obtener(b, "pdf_fuente", "helvetica")),
        word_fuente=str(_obtener(b, "word_fuente", "Calibri")),
        word_tamano_fuente_pt=int(_obtener(b, "word_tamano_fuente_pt", 11)),
    )


def _construir_libreria(bruto: dict[str, Any], url_por_defecto: str) -> LibreriaConfig:
    return LibreriaConfig(
        activa=bool(_obtener(bruto, "activa", True)),
        url=str(_obtener(bruto, "url", url_por_defecto)),
    )


def _construir_librerias(datos: dict[str, Any]) -> LibreriasConfig:
    b = _obtener(datos, "librerias", {})
    return LibreriasConfig(
        markdown=_construir_libreria(
            _obtener(b, "markdown", {}), "https://cdn.jsdelivr.net/npm/marked/marked.min.js"
        ),
        sanitizador=_construir_libreria(
            _obtener(b, "sanitizador", {}), "https://cdnjs.cloudflare.com/ajax/libs/dompurify/3.2.6/purify.min.js"
        ),
        docx=_construir_libreria(
            _obtener(b, "docx", {}), "https://cdn.jsdelivr.net/npm/docx@9.0.3/build/index.umd.js"
        ),
        jspdf=_construir_libreria(
            _obtener(b, "jspdf", {}), "https://cdnjs.cloudflare.com/ajax/libs/jspdf/3.0.0/jspdf.umd.min.js"
        ),
    )


def _construir_aplicacion(datos: dict[str, Any]) -> AplicacionConfig:
    b = _obtener(datos, "aplicacion", {})
    return AplicacionConfig(
        nombre=str(_obtener(b, "nombre", "ConSultar")),
        descripcion=str(_obtener(b, "descripcion", "")),
        idioma_html=str(_obtener(b, "idioma_html", "es")),
        idioma_interfaz=str(_obtener(b, "idioma_interfaz", "es-ES")),
        archivo_salida=str(_obtener(b, "archivo_salida", "consultar.html")),
        directorio_salida=str(_obtener(b, "directorio_salida", "output")),
    )


def construir_configuracion(datos: dict[str, Any]) -> ConfiguracionApp:
    """Convierte el diccionario "crudo" leído del archivo de configuración
    en el árbol tipado `ConfiguracionApp`. No valida los VALORES (eso es
    responsabilidad de `validators.validar_configuracion`); aquí solo se
    resuelven claves ausentes con valores por defecto razonables."""
    return ConfiguracionApp(
        aplicacion=_construir_aplicacion(datos),
        modelos=_construir_modelos(datos),
        api=_construir_api(datos),
        prompts=_construir_prompts(datos),
        ui=_construir_ui(datos),
        visibilidad=_construir_visibilidad(datos),
        tema=_construir_tema(datos),
        exports=_construir_exports(datos),
        librerias=_construir_librerias(datos),
    )


def cargar_configuracion(ruta: Path) -> ConfiguracionApp:
    """Punto de entrada público: lee el archivo indicado y devuelve el árbol
    de configuración tipado. Lanza `ErrorDeConfiguracion` si el archivo no
    existe, no se puede interpretar o no tiene la forma de un mapa/objeto."""
    datos = _leer_archivo(ruta)
    return construir_configuracion(datos)
