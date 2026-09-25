# Conversor Markdown + Mermaid → Word (es-ES)

Convierte un archivo Markdown que contiene diagramas [Mermaid](https://mermaid.js.org/)
en un documento Word (`.docx`) en español, renderizando cada diagrama como una
imagen PNG de alta calidad e insertándola exactamente donde estaba el bloque
de código original, conservando el resto del contenido (títulos, texto,
tablas, listas, etc.).

Se entregan **dos versiones** del script, ambas construidas sobre el mismo
núcleo compartido (`mermaid_docx_core.py`):

| Archivo               | Uso previsto                                            |
|-----------------------|----------------------------------------------------------|
| `mermaid_docx_core.py`| Núcleo compartido — no se ejecuta directamente.           |
| `convertir_vscode.py` | **Versión 1**: pensada para ejecutar/depurar desde VS Code (F5), configurable con `config.json` o variables de entorno. |
| `convertir_cli.py`    | **Versión 2**: interfaz de línea de comandos con `argparse`, pensada para terminal / automatización / CI. |

---

## 1. Instalación de dependencias

### 1.1. Dependencias externas (obligatorias, no se instalan con pip)

**Pandoc** — motor de conversión Markdown → Word:

```bash
# Windows
winget install --id JohnMacFarlane.Pandoc

# macOS
brew install pandoc

# Linux (Debian/Ubuntu)
sudo apt install pandoc
```

**Mermaid CLI (`mmdc`)** — renderizado de diagramas a PNG (requiere Node.js ≥ 16):

```bash
npm install -g @mermaid-js/mermaid-cli

# Verificar instalación
mmdc --version
```

> **Nota sobre Docker / CI en Linux**: si `mmdc` falla con un error relacionado
> con el sandbox de Chromium (`No usable sandbox`), ejecuta el script con la
> opción `--no-sandbox` (versión CLI) o `"sin_sandbox": true` en `config.json`
> (versión VS Code).

### 1.2. Dependencias de Python

```bash
pip install -r requirements.txt
```

Actualmente solo se requiere `python-docx`, usada para reforzar el idioma
es-ES directamente en el `.docx` generado (además del metadato `lang` que ya
aplica Pandoc).

---

## 2. Ajuste automático del tamaño de las imágenes a una página

Cada diagrama renderizado se mide (con Pillow) y, si excede el área útil de
una página (tamaño de página menos márgenes), se reescala automáticamente
**preservando la relación de aspecto**, de modo que ningún diagrama ocupe
más de una página en el documento final. Si el diagrama ya es más pequeño
que el área útil, no se toca (nunca se amplía una imagen).

Opciones relacionadas:

| Flag (CLI)     | Clave (`config.json`) | Descripción                                   | Por defecto |
|----------------|------------------------|------------------------------------------------|-------------|
| `--page-size`  | `tamano_pagina`         | Tamaño de página de referencia: `A4` o `Carta` | `A4`        |
| `--margin`     | `margen_cm`             | Margen por lado, en centímetros                | `2.5`       |

> **Nota técnica**: sin una plantilla de referencia explícita, Pandoc aplica
> un límite interno propio de ancho de imagen (~14.8 cm) que no siempre
> coincide con el área útil real calculada a partir del tamaño de página y
> margen indicados. Para evitarlo, el script genera automáticamente una
> plantilla de referencia temporal (a partir de la plantilla por defecto de
> Pandoc) con la geometría de página exacta, de modo que el ancho calculado
> se respete fielmente en el `.docx` final. Si el usuario aporta su propia
> plantilla con `--reference-doc`, se usa tal cual y el límite de tamaño
> pasa a depender de la geometría de página definida en esa plantilla.

---

## 3. Versión 1 — Uso desde VS Code

1. Abre la carpeta del proyecto en VS Code.
2. (Opcional) Copia `config.ejemplo.json` a `config.json` y ajusta las rutas:

   ```json
   {
       "input": "ejemplo/entrada_ejemplo.md",
       "output": "salida/documento_final.docx",
       "tema": "neutral",
       "ancho": 1400,
       "alto": 900,
       "escala": 2.0,
       "fondo": "white",
       "idioma": "es-ES",
       "plantilla_referencia": null,
       "mantener_temporales": false,
       "sin_sandbox": false,
       "verbose": true
   }
   ```

3. Abre `convertir_vscode.py` y pulsa **F5** (o usa "Run Python File").
   Si no existe `config.json`, el script usa valores por defecto de ejemplo.

También puedes configurar rutas mediante variables de entorno (útil en
`launch.json`):

```json
{
    "name": "Python: convertir_vscode",
    "type": "debugpy",
    "request": "launch",
    "program": "${workspaceFolder}/convertir_vscode.py",
    "env": {
        "MERMAID_DOCX_INPUT": "${workspaceFolder}/ejemplo/entrada_ejemplo.md",
        "MERMAID_DOCX_OUTPUT": "${workspaceFolder}/salida/documento_final.docx",
        "MERMAID_DOCX_THEME": "neutral"
    }
}
```

Orden de prioridad de configuración: **argumentos CLI opcionales** >
**variables de entorno** > **config.json** > valores por defecto.

---

## 4. Versión 2 — Uso desde terminal (CLI)

```bash
python convertir_cli.py --input ejemplo/entrada_ejemplo.md --output salida/documento_final.docx
```

### Opciones disponibles

| Flag                  | Corto | Descripción                                                        | Por defecto |
|-----------------------|-------|---------------------------------------------------------------------|-------------|
| `--input`             | `-i`  | Ruta del Markdown de entrada (**obligatorio**)                       | —           |
| `--output`            | `-o`  | Ruta del `.docx` de salida (**obligatorio**)                         | —           |
| `--theme`             |       | Tema Mermaid: `default`, `dark`, `neutral`, `forest`, `base`          | `default`   |
| `--width`             |       | Ancho del lienzo en píxeles                                          | `1200`      |
| `--height`            |       | Alto del lienzo en píxeles                                           | `800`       |
| `--scale`             |       | Factor de escala (nitidez de la imagen)                              | `2.0`       |
| `--background`        |       | Color de fondo (`white`, `transparent`, `#RRGGBB`...)                | `white`     |
| `--lang`              |       | Idioma BCP-47 del documento final                                    | `es-ES`     |
| `--page-size`         |       | Tamaño de página límite para las imágenes: `A4` o `Carta`             | `A4`        |
| `--margin`            |       | Margen de página (cm) usado para calcular el área útil                | `2.5`       |
| `--reference-doc`     |       | Plantilla `.docx` opcional para aplicar estilos corporativos          | —           |
| `--keep-temp`         |       | Conserva los PNG y el Markdown intermedio (no los borra)              | `False`     |
| `--no-sandbox`        |       | Desactiva el sandbox de Chromium (Docker/CI en Linux)                | `False`     |
| `--verbose`           | `-v`  | Salida detallada (comandos ejecutados, avisos de Pandoc, etc.)        | `False`     |
| `--version`           |       | Muestra la versión del script                                        | —           |

### Ejemplo completo

```bash
python convertir_cli.py \
    -i manual.md \
    -o manual_final.docx \
    --theme neutral \
    --width 1400 --height 900 --scale 2.5 \
    --reference-doc plantilla_corporativa.docx \
    --verbose
```

### Uso de una plantilla corporativa (`--reference-doc`)

Para heredar estilos de una plantilla existente (tipografías, colores,
márgenes corporativos), genera primero una plantilla base y personalízala en
Word:

```bash
pandoc -o plantilla_corporativa.docx --print-default-data-file reference.docx
```

Edita `plantilla_corporativa.docx` en Word (cambia estilos "Título 1",
"Normal", etc.) y pásala luego con `--reference-doc`.

---

## 5. Cómo funciona el pipeline internamente

1. **Lectura** del Markdown de entrada.
2. **Extracción** de todos los bloques ```` ```mermaid ... ``` ```` mediante
   expresiones regulares, registrando su posición exacta en el texto.
3. **Renderizado** de cada diagrama a PNG con `mmdc` (Mermaid CLI), en un
   directorio temporal, con el tema y la resolución indicados.
4. **Medición y ajuste de tamaño**: se mide el PNG real con Pillow y, si
   excede el área útil de una página (`--page-size` / `--margin`), se
   calcula un ancho reducido que preserva la relación de aspecto.
5. **Sustitución** de cada bloque de código por una referencia de imagen
   Markdown (`![Diagrama N](ruta.png){width=...cm}`) en la posición exacta
   donde estaba.
6. **Metadatos de idioma**: se antepone un bloque YAML (`lang: es-ES`) al
   Markdown resultante.
7. **Geometría de página**: si no se indicó `--reference-doc`, se genera una
   plantilla de referencia temporal con el tamaño de página y márgenes
   exactos, para que Pandoc respete el ancho calculado en el paso 4.
8. **Conversión con Pandoc** del Markdown final (texto + tablas + imágenes)
   al documento `.docx`, usando esa plantilla de referencia.
9. **Post-procesado con `python-docx`**: se refuerza el idioma es-ES tanto en
   las propiedades del documento como en cada `run` de texto (para que el
   corrector ortográfico de Word trate todo el contenido como español).
10. **Limpieza** de archivos temporales (PNG, Markdown intermedio y
    plantilla de referencia generada), salvo que se indique `--keep-temp` /
    `"mantener_temporales": true`.

---

## 6. Solución de problemas

| Síntoma                                                      | Causa probable / solución                                                                 |
|---------------------------------------------------------------|--------------------------------------------------------------------------------------------|
| `HerramientaNoEncontradaError`                                | Falta Pandoc o `mmdc` en el PATH. Revisa la sección 1.1.                                    |
| `mmdc` falla con error de sandbox de Chromium                 | Ejecuta con `--no-sandbox` (CLI) o `"sin_sandbox": true` (VS Code).                          |
| `mmdc` falla con "Could not find Chrome"                      | Ejecuta `npx puppeteer browsers install chrome-headless-shell` (o `chrome`) una sola vez.    |
| Las imágenes no aparecen en el `.docx`                        | Comprueba que Pandoc use `--resource-path` (ya gestionado automáticamente por el script).     |
| El documento no parece estar en español al abrirlo            | Verifica que tu Word tenga instalado el paquete de idioma español; el metadato ya está fijado.|

---

## 7. Archivo de ejemplo

`ejemplo/entrada_ejemplo.md` contiene un Markdown de prueba con dos diagramas
Mermaid (`flowchart` y `sequenceDiagram`) y una tabla, ideal para validar la
instalación:

```bash
python convertir_cli.py -i ejemplo/entrada_ejemplo.md -o salida/prueba.docx --verbose
```
