# Generador de presentaciones GRAFCET (.docx → .pptx con LLM)

Convierte un documento `.docx` (por ejemplo, una práctica de laboratorio)
en una presentación `.pptx` profesional, manteniendo el estilo visual
**"Editorial Noir / Automatización Industrial"**: fondo oscuro en portada
y cierre, fondo claro en el contenido, acentos en ámbar y turquesa,
iconos en círculo, diagramas de proceso y diagramas GRAFCET.

El contenido de la presentación se estructura automáticamente mediante
un modelo de lenguaje (LLM). **Existen dos variantes equivalentes**,
según el proveedor de LLM que prefieras usar:

| Variante | Proveedor | Archivos |
|---|---|---|
| **Anthropic** | Claude, vía la API de Anthropic | `generate_pptx_common.py`, `generate_presentation_vscode.py`, `generate_presentation_cli.py`, `requirements.txt` |
| **OpenAI** | GPT, vía la API de OpenAI | `generate_pptx_common_openai.py`, `generate_presentation_vscode_openai.py`, `generate_presentation_cli_openai.py`, `requirements_openai.txt` |

Ambas variantes producen presentaciones idénticas en estilo y
estructura; solo cambia el proveedor del LLM utilizado para generar el
contenido. Puedes instalar y usar una, la otra, o ambas en el mismo
proyecto (no interfieren entre sí).

## Archivos del proyecto

| Archivo | Descripción |
|---|---|
| `generate_pptx_common.py` | Módulo compartido (**Anthropic**): estilos, utilidades de `python-pptx`, lectura de `.docx`, prompt y llamada a la API de Anthropic, generadores de diapositivas. |
| `generate_presentation_vscode.py` | Versión **Anthropic** para VS Code (configuración editable arriba del archivo, sin argumentos de consola). |
| `generate_presentation_cli.py` | Versión **Anthropic** de línea de comandos, con `argparse`. |
| `requirements.txt` | Dependencias de Python para la variante Anthropic. |
| `generate_pptx_common_openai.py` | Módulo compartido (**OpenAI**): idéntico al anterior salvo en la llamada al LLM. |
| `generate_presentation_vscode_openai.py` | Versión **OpenAI** para VS Code. |
| `generate_presentation_cli_openai.py` | Versión **OpenAI** de línea de comandos, con `argparse`. |
| `requirements_openai.txt` | Dependencias de Python para la variante OpenAI. |

Cada script de entrada importa su propio módulo común
(`generate_pptx_common.py` o `generate_pptx_common_openai.py`, según
corresponda), así que todos los archivos deben residir en el **mismo
directorio**.

## Instalación

```bash
# Variante Anthropic
pip install -r requirements.txt

# Variante OpenAI
pip install -r requirements_openai.txt
```

## Configuración de la clave de la API

### Anthropic

Se obtiene en https://console.anthropic.com

```bash
# Linux / macOS
export ANTHROPIC_API_KEY="sk-ant-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"

# Windows (PowerShell)
setx ANTHROPIC_API_KEY "sk-ant-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
```

### OpenAI

Se obtiene en https://platform.openai.com/api-keys

```bash
# Linux / macOS
export OPENAI_API_KEY="sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"

# Windows (PowerShell)
setx OPENAI_API_KEY "sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
```

En ambos casos, la clave también puede definirse en un archivo `.env`
(si se instala `python-dotenv`), detectado automáticamente por las
versiones VS Code:

```
ANTHROPIC_API_KEY=sk-ant-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

## Uso — Versión VS Code

```text
Anthropic:  abre generate_presentation_vscode.py
OpenAI:     abre generate_presentation_vscode_openai.py
```

1. Edita la sección `CONFIGURACIÓN` (rutas de entrada/salida, modelo, tokens).
2. Ejecuta con F5 o el botón "Run Python File".

## Uso — Versión CLI

```bash
# Anthropic
python generate_presentation_cli.py --input practica.docx --output presentacion.pptx \
    --model claude-sonnet-5 --max-tokens 16000 --temperature 0.4 --save-json --verbose

# OpenAI
python generate_presentation_cli_openai.py --input practica.docx --output presentacion.pptx \
    --model gpt-4o --max-tokens 16000 --temperature 0.4 --save-json --verbose
```

Ejecuta `--help` sobre cualquiera de los dos scripts para ver todas las opciones.

## Modelos disponibles

### Anthropic (Claude)

| Modelo | Uso recomendado |
|---|---|
| `claude-sonnet-5` | Valor por defecto: buen equilibrio entre calidad y coste. |
| `claude-opus-4-8` | Máxima calidad, para contenido muy denso o complejo. |
| `claude-haiku-4-5-20251001` | Más rápido y económico, para pruebas rápidas. |

Documentación oficial: https://docs.claude.com

### OpenAI (GPT)

| Modelo | Uso recomendado |
|---|---|
| `gpt-4o` | Valor por defecto: buen equilibrio entre calidad y coste. |
| `gpt-4.1` | Ventana de contexto muy amplia, ideal para documentos largos. |
| `gpt-4o-mini` | Más rápido y económico, para pruebas rápidas. |
| `o3` / `o4-mini` | Modelos de razonamiento; el código se adapta automáticamente a sus particularidades (ver más abajo). |

Documentación oficial: https://platform.openai.com/docs

Los nombres de modelo de ambos proveedores pueden cambiar con el
tiempo; consulta siempre la documentación oficial para la lista
actualizada.

## Consumo de tokens de la consulta

Al finalizar, todos los scripts muestran en el log un resumen del
consumo de tokens de la llamada al LLM, por ejemplo:

```
Consumo de tokens de la consulta: 1 llamada(s) a la API · tokens de entrada: 8342 · tokens de salida: 5120 · tokens totales: 13462
```

Este dato se obtiene de la clase `UsoTokens` (presente en ambos módulos
comunes), que acumula los tokens de entrada y salida devueltos por la
API en `respuesta.usage`, incluso si hubo reintentos por errores de red
o por incompatibilidades de parámetros con el modelo. La función
`generar_presentacion_desde_docx()` devuelve un objeto
`ResultadoGeneracion` con dos campos:

- `ruta_pptx`: ruta del archivo `.pptx` generado.
- `uso_tokens`: instancia de `UsoTokens`, con `tokens_entrada`,
  `tokens_salida`, `tokens_totales` (propiedad) y `resumen()` (cadena
  legible lista para mostrar en consola o guardar en un log).

## Adaptación automática a particularidades de cada modelo

Ambas variantes detectan automáticamente, a partir de los errores 400
devueltos por la API, ciertas incompatibilidades de parámetros según el
modelo concreto que se use, y se adaptan sobre la marcha sin gastar un
intento de los disponibles para fallos genuinos:

- **Anthropic**: modelos que no admiten `temperature`, o que no admiten
  "prefill" del mensaje del asistente (usado para forzar una salida
  JSON limpia).
- **OpenAI**: modelos que no admiten `temperature`, que requieren
  `max_completion_tokens` en lugar de `max_tokens`, o que no admiten
  `response_format={"type": "json_object"}` (típico de los modelos de
  razonamiento `o3` / `o4-mini`).

En ambos casos, si la API no fuerza un JSON limpio por otros medios, la
función `_extraer_json()` de cada módulo común analiza la respuesta de
forma tolerante (quitando vallas de código Markdown, recortando texto
sobrante antes o después del objeto JSON, etc.).

## Notas de diseño

- **Estilos**: colores, tipografías (Cambria/Calibri) y disposición de
  diapositivas replican la presentación de referencia sobre GRAFCET, y
  son idénticos en ambas variantes.
- **Iconos**: por simplicidad y para no requerir dependencias adicionales,
  los iconos se representan como glifos Unicode centrados en círculos de
  color (equivalente ligero a los iconos vectoriales `react-icons`
  usados en la versión Node.js del pipeline). Si se desea el mismo nivel
  de detalle gráfico, `agregar_icono_circular()` puede sustituirse por
  una función que renderice SVGs reales (p. ej. con `cairosvg` + `Pillow`)
  e inserte el resultado como imagen PNG.
- **Tipos de diapositiva admitidos** (ver `ESQUEMA_JSON_DESCRIPCION` en
  cualquiera de los dos módulos comunes): `section`, `bullets_two_col`,
  `process_flow`, `table`, `cards`, `grafcet_diagram`, `closing` (además
  de la portada, generada automáticamente a partir de `meta`).
- **Reintentos**: si el LLM devuelve un JSON malformado o falla la
  llamada de red, el proceso reintenta automáticamente hasta el número
  de veces configurado (`--retries` / `intentos_maximos`).
