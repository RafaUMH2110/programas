# Generador de documentos Word (propósito general)

Genera documentos Word (`.docx`) profesionales **sobre cualquier tema**,
con un diseño visual fijo y cuidado (portada con bloque de color, índice,
títulos con jerarquía clara, cajas de aviso, encabezado/pie con
numeración de página) e imágenes ilustrativas insertadas automáticamente.

El contenido se genera con la API de Anthropic (Claude); las imágenes se
buscan en Unsplash/Pexels o, si no hay claves configuradas, se generan
localmente como ilustraciones de reserva.

## Estructura del proyecto

```
doc_generator/
├── main.py                # Punto de entrada (orquesta todo el proceso)
├── config.py               # Paleta de colores, tipografía, rutas, parámetros
├── prompts.py               # Todos los prompts, editables sin tocar la lógica
├── content_generator.py    # Llamadas a la API de Anthropic (tool use)
├── image_service.py        # Búsqueda/descarga/generación de imágenes
├── document_builder.py     # Motor de maquetación Word (python-docx)
├── requirements.txt
├── .env.example
└── README.md
```

Cada módulo tiene una única responsabilidad:

| Módulo                | Responsabilidad                                          |
|------------------------|-----------------------------------------------------------|
| `content_generator.py` | "¿Qué dice el documento?" (texto, vía IA)                 |
| `image_service.py`     | "¿Qué imágenes lo acompañan?"                              |
| `document_builder.py`  | "¿Qué aspecto tiene?" (maquetación, sin saber de dónde viene el contenido) |
| `main.py`              | Conecta los tres pasos anteriores y gestiona errores       |

## 1. Instalación

```bash
# (Recomendado) crea un entorno virtual
python -m venv .venv
source .venv/bin/activate      # En Windows: .venv\Scripts\activate

# Instala las dependencias
pip install -r requirements.txt
```

## 2. Configuración de las API keys

Copia `.env.example` como `.env` y rellena tus claves:

```bash
cp .env.example .env
```

- **`ANTHROPIC_API_KEY`** (obligatoria): genera el texto del documento.
  Consíguela en <https://console.anthropic.com>.
- **`UNSPLASH_ACCESS_KEY`** (opcional, gratuita): fotografías reales de
  alta calidad. Regístrate en <https://unsplash.com/developers>.
- **`PEXELS_API_KEY`** (opcional, gratuita): banco de imágenes alternativo,
  usado si Unsplash no está configurado o no encuentra resultados.
  Regístrate en <https://www.pexels.com/api/>.

> Si no configuras ninguna clave de imágenes, el programa sigue
> funcionando perfectamente: generará automáticamente una ilustración de
> reserva con la temática de cada figura (ver `image_service.py`), para
> que el documento nunca se quede sin imagen.

## 3. Ejecución

Desde la terminal integrada de VSCode (o cualquier terminal):

```bash
python main.py --tema "La fotosíntesis"
```

Modo interactivo (si no pasas `--tema`, se pregunta por consola):

```bash
python main.py
```

Otras opciones disponibles:

```bash
python main.py \
  --tema "Guía de onboarding para nuevos empleados" \
  --idioma "español de España" \
  --tono "formal y directo" \
  --audiencia "empleados que se incorporan a la empresa" \
  --secciones 7 \
  --instrucciones "Incluye un apartado final de checklist de la primera semana." \
  --salida "salida/onboarding.docx"
```

El documento resultante se guarda por defecto en `salida/<tema>.docx`.

### Ejecutar desde el editor de VSCode

1. Abre la carpeta del proyecto en VSCode.
2. Abre `main.py` y pulsa el botón ▶ ("Run Python File") de la esquina
   superior derecha, o usa el atajo `Ctrl+F5` / `Cmd+F5`.
3. Si no has pasado argumentos, el programa te pedirá el tema por la
   terminal integrada.

## 4. Personalización

- **Cambiar el diseño visual** (colores, tipografía, márgenes): edita
  `config.py`. Todo el resto del programa usa esas constantes, así que
  un cambio ahí se refleja en todo el documento.
- **Cambiar cómo se le pide el contenido al modelo** (tono, estructura,
  cantidad de secciones, instrucciones de estilo): edita las plantillas
  de `prompts.py`. No hace falta tocar `content_generator.py`.
- **Añadir un nuevo tipo de bloque de contenido** (por ejemplo, una
  tabla o una cita destacada): añade una función `add_xxx(...)` en
  `document_builder.py` y una rama nueva en `_renderizar_bloque`, y
  añade el tipo correspondiente al `enum` de `_BLOQUE_SCHEMA` en
  `content_generator.py`.
- **Cambiar el proveedor de imágenes o su orden de preferencia**: edita
  `config.ORDEN_PROVEEDORES_IMAGENES`.

## 5. Solución de problemas

| Síntoma                                                        | Causa probable / solución                                                                 |
|------------------------------------------------------------------|---------------------------------------------------------------------------------------------|
| `Falta la variable de entorno ANTHROPIC_API_KEY`                | No has creado el archivo `.env` o no contiene la clave. Revisa el paso 2.                    |
| `No se pudo generar el contenido tras 3 intentos`                | Problema de red o de la API (clave inválida, saldo agotado, etc.). Revisa el mensaje de error mostrado. |
| Las figuras muestran una ilustración genérica en vez de una foto | No hay `UNSPLASH_ACCESS_KEY`/`PEXELS_API_KEY`, o la búsqueda no encontró resultados para esa consulta. Es un comportamiento esperado, no un error. |
| El documento tarda bastante en generarse                          | Es normal: incluye una llamada a un modelo de lenguaje y, opcionalmente, varias descargas de imágenes. |

## 6. Notas sobre fidelidad visual

El motor de maquetación (`document_builder.py`) reproduce exactamente el
mismo diseño en cada ejecución, con independencia del tema: portada con
bloque de color y tres líneas de contexto, índice manual con números en
turquesa, títulos de sección con filete inferior, subtítulos en azul
marino suave, viñetas con guion turquesa, cajas de aviso (`teal` /
`orange`) y encabezado/pie de página con numeración automática que se
reinicia en la primera página de contenido. Solo cambian el texto y las
imágenes, nunca el estilo.
