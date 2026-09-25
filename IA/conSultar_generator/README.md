# Generador de ConSultar

Este proyecto es un **generador de aplicaciones web** escrito en Python: lee
un archivo de configuración (`config.yaml`) y produce un único archivo HTML
autocontenido —la aplicación **ConSultar**— que mejora automáticamente la
consulta de una persona y la envía en dos pasos a la IA de Anthropic,
mostrando el resultado en Markdown y permitiendo exportarlo a Markdown,
Word o PDF.

El generador no contiene ningún dato "fijo" en el código: absolutamente
todo lo que ve o hace la aplicación generada (textos, modelos disponibles,
colores, prompts, formatos de exportación, librerías externas...) se
controla desde `config.yaml`.

> **Importante — separación de responsabilidades.** Este programa Python
> **genera** la aplicación web; no realiza ninguna llamada a la IA por sí
> mismo. Es la aplicación HTML/JavaScript resultante la que, ya en el
> navegador de quien la use, habla con la API de Anthropic. Ver la sección
> [Seguridad](#seguridad) para los motivos y las implicaciones de este
> diseño.

---

## Índice

1. [Instalación](#instalación)
2. [Ejecución](#ejecución)
3. [Estructura del proyecto](#estructura-del-proyecto)
4. [Configuración](#configuración)
5. [Plantillas de prompts](#plantillas-de-prompts)
6. [Cómo funciona la aplicación generada](#cómo-funciona-la-aplicación-generada)
7. [Seguridad](#seguridad)
8. [Pruebas](#pruebas)
9. [Solución de problemas](#solución-de-problemas)

---

## Instalación

### Requisitos

* **Python 3.10 o superior** (se usan anotaciones de tipo modernas como
  `str | None`).
* Cualquier sistema operativo: Windows, macOS o Linux.

### Pasos (desde una terminal o desde el terminal integrado de VS Code)

```bash
# 1. Sitúate en la carpeta del proyecto
cd conSultar-generator

# 2. Crea un entorno virtual
python3 -m venv .venv

# 3. Actívalo
#    En Linux/macOS:
source .venv/bin/activate
#    En Windows (cmd):
.venv\Scripts\activate.bat
#    En Windows (PowerShell):
.venv\Scripts\Activate.ps1

# 4. Instala las dependencias
pip install -r requirements.txt
```

Las dos dependencias externas son:

| Paquete  | Para qué se usa                                                                 |
|----------|----------------------------------------------------------------------------------|
| `PyYAML` | Leer `config.yaml` (YAML no forma parte de la librería estándar de Python).       |
| `Jinja2` | Motor de plantillas: genera el HTML/CSS/JS de forma mantenible, sin concatenar cadenas de texto a mano. |

Si prefieres no instalar `PyYAML`, puedes usar un `config.json` equivalente
(mismo contenido, formato JSON) y omitir esa dependencia; el generador
detecta el formato por la extensión del archivo.

---

## Ejecución

### Desde VS Code

1. Abre la carpeta del proyecto en VS Code.
2. Abre `main.py`.
3. Pulsa **Run Python File** (▷) o `F5`.

Esto ejecuta `python main.py` sin argumentos, que:

1. Carga `config.yaml`.
2. Valida su contenido.
3. Genera `output/consultar.html`.

### Desde una terminal

```bash
# Generar con la configuración por defecto
python main.py

# Usar un archivo de configuración distinto
python main.py --config mi_config.yaml

# Cambiar el directorio de salida (sobrescribe el de la configuración)
python main.py --output ./dist

# Solo validar la configuración, sin generar ningún archivo
python main.py --validate

# Ver información adicional de depuración
python main.py --verbose

# Ver la versión del generador
python main.py --version
```

Al terminar correctamente, verás un mensaje como:

```
✔ Aplicación generada en: output/consultar.html
```

El archivo resultante (`consultar.html` por defecto) es autocontenido:
puedes abrirlo directamente en cualquier navegador moderno, o distribuirlo
como un único archivo.

---

## Estructura del proyecto

```
conSultar-generator/
│
├── main.py                  # Punto de entrada de línea de comandos
├── config.yaml               # Configuración (única fuente de verdad)
├── requirements.txt
├── README.md
│
├── templates/                 # Plantillas Jinja2
│   ├── index.html.j2          #   Estructura HTML (incluye las otras dos)
│   ├── styles.css.j2          #   Hoja de estilos (tema visual)
│   └── app.js.j2              #   Lógica de la aplicación generada
│
├── generator/                  # Paquete Python del generador
│   ├── __init__.py
│   ├── config.py               #   Carga y modelado tipado de la configuración
│   ├── validators.py           #   Validación semántica de la configuración
│   ├── templates.py            #   Entorno Jinja2 y renderizado
│   └── generator.py            #   Orquestación: cargar → validar → renderizar → escribir
│
├── tests/                      # Pruebas (unittest)
│   ├── test_config.py
│   ├── test_validators.py
│   └── test_generator.py
│
└── output/                     # Aquí se escribe el archivo generado
    └── consultar.html
```

**Por qué esta arquitectura:**

* `config.py`, `validators.py` y `templates.py` no se conocen entre sí:
  cada uno se puede probar y modificar por separado.
* Las plantillas (`templates/*.j2`) están completamente separadas del
  código Python: para cambiar el aspecto o los textos de la aplicación
  generada casi nunca hace falta tocar un archivo `.py`, basta con editar
  `config.yaml`.
* `generator.py` es el único módulo que combina los demás, siguiendo
  siempre el mismo orden: **cargar → validar → renderizar → escribir**. Si
  la validación falla, no se escribe ningún archivo (nunca se genera una
  aplicación a medias).

---

## Configuración

Toda la configuración vive en `config.yaml`, dividido en nueve secciones.
El archivo que se entrega ya contiene una configuración completa y
comentada; aquí se explica cada sección con más detalle.

### 1. `aplicacion`

| Clave | Descripción |
|---|---|
| `nombre` | Nombre de la aplicación (aparece en el título de la pestaña, etc.). |
| `descripcion` | Meta-descripción HTML. |
| `idioma_html` | Valor de `<html lang="...">`. |
| `idioma_interfaz` | Solo documental (los textos reales están en `ui`). |
| `archivo_salida` | Nombre del archivo `.html` generado. |
| `directorio_salida` | Carpeta donde se escribe (relativa al directorio desde el que ejecutes `main.py`, salvo que uses `--output`). |

### 2. `modelos`

Catálogo de modelos de IA que aparecerán en el desplegable "Elegir
Modelo". Cada modelo necesita `id` (el identificador que espera la API),
`nombre` (el texto visible) y `max_output_tokens` (límite de tokens de
salida de ese modelo; el campo "Número de tokens" de la aplicación se
valida contra este límite). `modelo_por_defecto` debe coincidir con el
`id` de uno de los modelos de la lista.

### 3. `api`

Conexión con el proveedor de IA: `endpoint`, `version_api` (cabecera
`anthropic-version`), `timeout_segundos` (tiempo máximo de espera de cada
llamada) y `reintentos` (reintentos automáticos ante errores 429/5xx o de
red, con espera progresiva entre intentos). `api_key_env` es solo
documental — ver [Seguridad](#seguridad).

### 4. `prompts`

Ver la sección [Plantillas de prompts](#plantillas-de-prompts) más abajo.

### 5. `ui`

Todos los textos visibles de la aplicación: títulos, subtítulos, etiquetas
de campo, textos de ayuda, texto de los botones, mensajes de progreso/éxito
y el texto del pie de página. Cambiar el idioma de la aplicación generada
(o simplemente su redacción) consiste en editar únicamente esta sección.

### 6. `visibilidad`

Dos interruptores para mostrar/ocultar controles opcionales:

* `mostrar_aviso_seguridad`: el recuadro de aviso junto al campo de clave de API.
* `mostrar_exportacion`: la casilla "Exportar resultado" y todo lo relacionado (si es `false`, el botón "Exportar fichero" tampoco aparece).

### 7. `tema`

Apariencia visual: colores (en hexadecimal `#RRGGBB`), familias
tipográficas, radio de borde, sombra y ancho máximo de página. El tema por
defecto usa una paleta de azules muy claros con blanco y gris claro, tal y
como se pidió originalmente.

### 8. `exports`

Qué formatos de exportación están activos (`markdown`, `word`, `pdf`),
cuál es el formato y el nombre de archivo por defecto, y ajustes propios
de cada formato (tamaño de página y márgenes del PDF, fuente y tamaño de
fuente del documento Word).

### 9. `librerias`

URLs (y activación) de las cuatro dependencias JavaScript cargadas desde
CDN: `marked` (Markdown → HTML), `sanitizador` (DOMPurify), `docx` (Word) y
`jspdf` (PDF). `markdown` y `sanitizador` son obligatorias. `docx` y
`jspdf` solo son necesarias si el formato correspondiente está activo en
`exports` — si lo desactivas, el propio generador omite su etiqueta
`<script>` del HTML final para no cargar peso innecesario.

### Ejemplo de configuración completo

`config.yaml` (el que se entrega con el proyecto) **es** el ejemplo
completo; puedes copiarlo como punto de partida y modificar solo lo que
necesites, ya que cualquier clave que no incluyas conserva un valor por
defecto razonable. Un ejemplo mínimo, para ilustrar la estructura general:

```yaml
aplicacion:
  nombre: "MiConSultor"
  archivo_salida: "mi_consultor.html"

modelos:
  modelo_por_defecto: "claude-sonnet-4-5-20250929"
  disponibles:
    - id: "claude-sonnet-4-5-20250929"
      nombre: "Claude Sonnet 4.5"
      max_output_tokens: 64000

prompts:
  mejora:
    system: "Reescribe la consulta del usuario de forma clara y en inglés."
    user: "{{consulta}}"
    max_tokens: 1024
  final:
    system: "{{rol_usuario}}"
    user: "{{consulta_mejorada}}"
    max_tokens: 4096

ui:
  titulo: "MiConSultor"
  subtitulo: "Mejora y ejecuta tus consultas mediante IA"
  boton_consultar: "Consultar"
  boton_exportar: "Exportar fichero"
  # ...(el resto de textos de "ui" toman su valor por defecto si se omiten)

tema:
  color_primario: "#2563EB"
  color_fondo: "#F8FAFC"

exports:
  markdown: { activo: true }
  word: { activo: true }
  pdf: { activo: true }
```

Después de editar la configuración, valida los cambios antes de generar:

```bash
python main.py --validate
```

---

## Plantillas de prompts

La sección `prompts` de `config.yaml` define las dos llamadas del flujo:
`mejora` (paso 1: reescribe/mejora la consulta original) y `final` (paso
2: la consulta definitiva, usando el resultado del paso 1).

`system` y `user` son **plantillas de texto**, no el valor final: contienen
marcadores de posición de doble llave que la propia aplicación generada
sustituye en el navegador, en el momento de realizar cada llamada (no
durante la generación del HTML). Los marcadores admitidos son:

| Marcador | Se sustituye por... |
|---|---|
| `{{consulta}}` | El texto que la persona escribe en el campo "Consulta". |
| `{{consulta_mejorada}}` | El resultado del primer paso (la consulta ya mejorada). |
| `{{rol_usuario}}` | El texto que la persona escribe en el campo "Rol del usuario". |
| `{{modelo}}` | El nombre visible del modelo elegido en la interfaz. |

Un marcador que no reconozca la aplicación se deja tal cual (no se
sustituye por una cadena vacía), lo que facilita detectar errores de
escritura en la configuración.

**Ejemplos de uso:**

```yaml
prompts:
  mejora:
    system: "Rewrite the user's prompt in clear, detailed English."
    user: "{{consulta}}"
    max_tokens: 1024
    temperature: 0.3

  final:
    system: "{{rol_usuario}}"
    # Se puede envolver el marcador con texto adicional:
    user: "Ten en cuenta que el modelo usado es {{modelo}}.\n\n{{consulta_mejorada}}"
    max_tokens: 4096
```

`modelo` (opcional, dentro de `prompts.mejora` o `prompts.final`): si se
indica el `id` de un modelo, esa llamada concreta se realiza siempre con
ese modelo, sin importar el que la persona elija en la interfaz. Déjalo
vacío (`null`) —el valor por defecto— para usar el modelo seleccionado en
pantalla en ambas llamadas.

---

## Cómo funciona la aplicación generada

1. **Entrada del usuario.** La persona escribe su clave de API, elige un
   modelo y un límite de tokens, escribe el "Rol del usuario" (system
   prompt de la respuesta final) y su "Consulta".
2. **Primera consulta a la IA (mejora).** Al pulsar "Consultar", la
   aplicación rellena la plantilla `prompts.mejora` con la consulta
   original y la envía a la API. La respuesta es la "consulta mejorada".
3. **Mejora del prompt.** Ese resultado se usa, sin mostrarlo, como
   entrada del siguiente paso.
4. **Segunda consulta a la IA (final).** La aplicación rellena la
   plantilla `prompts.final` con la consulta mejorada y el "Rol del
   usuario", y la envía a la API con el modelo y el número de tokens
   elegidos en pantalla.
5. **Renderizado en Markdown.** La respuesta final se interpreta como
   Markdown (con la librería `marked`), se sanea con `DOMPurify` para
   evitar código HTML/JavaScript malicioso, y se muestra en la sección
   "Resultado".
6. **Exportación (opcional).** Si se activó "Exportar resultado", el botón
   "Exportar fichero" convierte esa misma respuesta a `.md`, `.docx` (con
   `docx.js`) o `.pdf` (con `jsPDF`), añadiendo automáticamente la
   extensión correcta y evitando duplicados como `resultado.md.md`.

Toda esta lógica reside en `app.js.j2` y se ejecuta enteramente en el
navegador de quien usa la aplicación: el generador Python no interviene en
ningún momento en las llamadas a la IA.

---

## Seguridad

**La aplicación generada llama a la API de Anthropic directamente desde el
navegador**, usando la cabecera `anthropic-dangerous-direct-browser-access`
que Anthropic ofrece para este caso de uso. Esto tiene una implicación
importante:

> Cualquier persona con acceso a las herramientas de desarrollo del
> navegador (o al propio archivo HTML, si se sirve desde un servidor sin
> más protección) puede ver la clave de API que se haya introducido en el
> campo correspondiente mientras la pestaña está abierta.

Por eso:

* **La configuración nunca contiene una clave real.** `api.api_key_env`
  es puramente documental: indica qué variable de entorno usarías si en el
  futuro añadieras un backend propio. El generador jamás incrusta un
  secreto en el HTML.
* **Cada persona introduce su propia clave** en un campo de tipo
  contraseña, que solo existe en la memoria de su navegador durante esa
  sesión (no se guarda en `localStorage` ni en ningún otro sitio, y no
  viaja a ningún servidor que no sea `api.endpoint`).
* Este patrón ("trae tu propia clave") es razonable para **uso personal o
  interno con personas de confianza**, pero **no es apropiado para una
  aplicación pública** con usuarios distintos de quien la despliega: en
  ese caso, cualquier visitante necesitaría su propia clave, y no hay forma
  de ocultarla del todo en un cliente puramente estático.
* **Si necesitas una aplicación pública o multiusuario**, la arquitectura
  recomendada es añadir un pequeño backend/proxy (por ejemplo, una función
  serverless) que guarde la clave de API como secreto del lado servidor y
  reenvíe las peticiones; el navegador nunca vería la clave real. Nada en
  este proyecto lo impide: bastaría con cambiar `api.endpoint` para que
  apunte a ese proxy en lugar de a `https://api.anthropic.com/v1/messages`,
  y el proxy sería responsable de añadir la clave verdadera antes de
  reenviar la petición a Anthropic.

**Otras medidas de seguridad aplicadas:**

* **Sin XSS por configuración:** `templates.py` no usa "autoescape"
  automático porque una misma plantilla combina HTML, CSS y JavaScript
  (cada uno necesita un escapado distinto). En su lugar, cada valor de
  configuración que se inserta en HTML pasa explícitamente por el filtro
  `| e` (escapado HTML), y cada uno que se inserta como literal
  JavaScript pasa por el filtro `| js` (codificación JSON, neutralizando
  además la secuencia `</` para que un valor de configuración no pueda
  cerrar prematuramente la etiqueta `<script>`).
* **Sin XSS por respuesta de la IA:** el HTML que genera `marked` a partir
  de la respuesta de la IA se pasa siempre por `DOMPurify.sanitize()`
  antes de insertarse en la página. `validators.py` impide generar la
  aplicación si se desactiva esta librería.
* **Validación estricta de valores libres:** colores, medidas CSS y
  nombres de fuente se validan con expresiones regulares restrictivas
  antes de insertarse en la hoja de estilos, para que un valor de
  configuración manipulado no pueda inyectar CSS/JS arbitrario.

---

## Pruebas

El proyecto incluye pruebas con el framework estándar `unittest`, sin
dependencias adicionales.

```bash
# Ejecutar toda la batería de pruebas
python -m unittest discover -s tests -v

# Ejecutar solo un archivo de pruebas
python -m unittest tests.test_validators -v
```

Qué cubre cada archivo:

* **`test_config.py`** — carga de YAML/JSON, errores de lectura (archivo
  inexistente, formato no soportado, JSON mal formado) y resolución de
  valores por defecto ante configuraciones parciales o vacías.
* **`test_validators.py`** — una configuración mínima válida no lanza
  ninguna excepción; cada regla de validación (nombre vacío, modelo por
  defecto inexistente, color inválido, formato de exportación
  inconsistente, librerías obligatorias desactivadas, temperatura fuera de
  rango, etc.) detecta correctamente su caso inválido.
* **`test_generator.py`** — pruebas de extremo a extremo: genera la
  aplicación real a partir de `config.yaml`, comprueba que el HTML
  resultante es válido y contiene lo esperado (DOCTYPE, idioma, modelos
  configurados, las cuatro dependencias por defecto), que no quedan
  etiquetas Jinja sin resolver, que `--validate` no escribe ningún
  archivo, y que una configuración inválida tampoco deja un archivo a
  medio generar.

---

## Solución de problemas

**`ModuleNotFoundError: No module named 'yaml'`**
Falta instalar las dependencias: ejecuta `pip install -r requirements.txt`
dentro de tu entorno virtual. Alternativamente, usa un `config.json` en
lugar de `config.yaml` para no depender de PyYAML.

**`No se pudo cargar la configuración: No se encuentra el archivo...`**
Comprueba que ejecutas `python main.py` desde la carpeta del proyecto (o
usa `--config ruta/completa/a/config.yaml`).

**`La configuración no es válida: ...`**
El mensaje de error lista, en español, cada problema encontrado (puede
haber varios a la vez). Corrígelos todos y vuelve a ejecutar
`python main.py --validate` hasta que no queden errores.

**El botón "Consultar" de la aplicación generada muestra "Clave de API
inválida o no autorizada".**
Comprueba que la clave de API introducida en el navegador es correcta y
empieza por `sk-ant-`. Este error viene directamente de la API de
Anthropic (código HTTP 401), no del generador.

**El botón "Consultar" muestra "No se ha podido conectar con la API".**
Comprueba la conexión a internet del navegador y que `api.endpoint` en la
configuración apunta a una URL accesible. Si usas un proxy propio,
confirma que admite CORS para el origen desde el que sirvas el HTML.

**Al exportar a Word o PDF no ocurre nada, o aparece un error en la
consola del navegador sobre `docx` o `jspdf` no definidos.**
Asegúrate de que `librerias.docx.activa` / `librerias.jspdf.activa` están
en `true` en `config.yaml` si `exports.word.activo` / `exports.pdf.activo`
también lo están (el generador ya lo exige en la validación, pero si has
editado el HTML generado a mano en lugar de regenerarlo, esta relación
puede haberse roto).

**He cambiado `config.yaml` pero la aplicación generada no refleja los
cambios.**
Recuerda que `output/consultar.html` es un archivo **generado**: cada vez
que edites la configuración, vuelve a ejecutar `python main.py` para
regenerarlo. Editar el HTML de salida directamente es posible, pero esos
cambios se perderán la próxima vez que se ejecute el generador.
