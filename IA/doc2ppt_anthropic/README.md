# Generador de presentaciones GRAFCET (.docx → .pptx con LLM)

Convierte un documento `.docx` (por ejemplo, una práctica de laboratorio)
en una presentación `.pptx` profesional, manteniendo el estilo visual
**"Editorial Noir / Automatización Industrial"**: fondo oscuro en portada
y cierre, fondo claro en el contenido, acentos en ámbar y turquesa,
iconos en círculo, diagramas de proceso y diagramas GRAFCET.

El contenido de la presentación se estructura automáticamente mediante
un modelo de lenguaje (LLM): **Claude, a través de la API de Anthropic**.

## Archivos del proyecto

| Archivo | Descripción |
|---|---|
| `generate_pptx_common.py` | Módulo compartido: estilos, utilidades de `python-pptx`, lectura de `.docx`, prompt y llamada a la API de Anthropic, generadores de diapositivas. |
| `generate_presentation_vscode.py` | Versión pensada para ejecutarse desde VS Code (configuración editable arriba del archivo, sin argumentos de consola). |
| `generate_presentation_cli.py` | Versión de línea de comandos, con `argparse`. |
| `requirements.txt` | Dependencias de Python. |

Los tres archivos `.py` deben residir en el **mismo directorio**, ya que
los dos scripts de entrada importan `generate_pptx_common.py`.

## Instalación

```bash
pip install -r requirements.txt
```

## Configuración de la clave de la API

La clave se obtiene en la consola de Anthropic: https://console.anthropic.com

```bash
# Linux / macOS
export ANTHROPIC_API_KEY="sk-ant-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"

# Windows (PowerShell)
setx ANTHROPIC_API_KEY "sk-ant-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
```

También puede definirse en un archivo `.env` (si se instala
`python-dotenv`), solo detectado automáticamente por la versión VS Code:

```
ANTHROPIC_API_KEY=sk-ant-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

## Uso — Versión VS Code

1. Abre `generate_presentation_vscode.py`.
2. Edita la sección `CONFIGURACIÓN` (rutas de entrada/salida, modelo, tokens).
3. Ejecuta con F5 o el botón "Run Python File".

## Uso — Versión CLI

```bash
python generate_presentation_cli.py --input practica.docx --output presentacion.pptx

# Con opciones avanzadas
python generate_presentation_cli.py \
    -i practica.docx \
    -o presentacion.pptx \
    --model claude-sonnet-5 \
    --max-tokens 16000 \
    --temperature 0.4 \
    --save-json \
    --verbose
```

Ejecuta `python generate_presentation_cli.py --help` para ver todas las opciones.

## Modelos de Claude disponibles

| Modelo | Uso recomendado |
|---|---|
| `claude-sonnet-5` | Valor por defecto: buen equilibrio entre calidad y coste. |
| `claude-opus-4-8` | Máxima calidad, para contenido muy denso o complejo. |
| `claude-haiku-4-5-20251001` | Más rápido y económico, para pruebas rápidas. |

Los nombres de modelo pueden cambiar con el tiempo; consulta la
documentación oficial de Anthropic (https://docs.claude.com) para la
lista actualizada.

## Notas de diseño

- **Estilos**: colores, tipografías (Cambria/Calibri) y disposición de
  diapositivas replican la presentación de referencia sobre GRAFCET.
- **Formato JSON forzado**: la API de Anthropic no dispone de un modo
  `response_format=json_object` como otras APIs, así que se utiliza la
  técnica de "prefill": se entrega a Claude un turno de asistente que ya
  comienza por `"{"`, forzando a que su continuación sea el resto de un
  objeto JSON válido (ver `generar_estructura_presentacion()` en
  `generate_pptx_common.py`).
- **Iconos**: por simplicidad y para no requerir dependencias adicionales,
  los iconos se representan como glifos Unicode centrados en círculos de
  color (equivalente ligero a los iconos vectoriales `react-icons`
  usados en la versión Node.js del pipeline). Si se desea el mismo nivel
  de detalle gráfico, `agregar_icono_circular()` puede sustituirse por
  una función que renderice SVGs reales (p. ej. con `cairosvg` + `Pillow`)
  e inserte el resultado como imagen PNG.
- **Tipos de diapositiva admitidos** (ver `ESQUEMA_JSON_DESCRIPCION` en
  `generate_pptx_common.py`): `section`, `bullets_two_col`, `process_flow`,
  `table`, `cards`, `grafcet_diagram`, `closing` (además de la portada,
  generada automáticamente a partir de `meta`).
- **Reintentos**: si el LLM devuelve un JSON malformado o falla la
  llamada de red, el proceso reintenta automáticamente hasta el número
  de veces configurado (`--retries` / `intentos_maximos`).
