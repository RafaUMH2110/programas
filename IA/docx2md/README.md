# Conversor Word (.docx) → Markdown + Mermaid

Convierte un documento Word (`.docx`) que contiene imágenes incrustadas
(diagramas, organigramas, gráficos...) en un archivo Markdown (`.md`) limpio
y bien estructurado, intentando transformar los diagramas detectados en
bloques de código [Mermaid](https://mermaid.js.org/) y conservando el resto
de imágenes como archivos organizados junto al documento.

Se entregan **dos versiones** del script, ambas construidas sobre el mismo
núcleo compartido (`docx_a_md_core.py`):

| Archivo                  | Uso previsto                                                     |
|--------------------------|--------------------------------------------------------------------|
| `docx_a_md_core.py`  | Núcleo compartido — no se ejecuta directamente.                    |
| `convertir_docx_a_md_vscode.py`    | **Versión 1**: pensada para ejecutar/depurar desde VS Code (F5), configurable con `config_docx_a_md.json` o variables de entorno. |
| `convertir_docx_a_md_cli.py`       | **Versión 2**: interfaz de línea de comandos con `argparse`, pensada para terminal / automatización / CI. |

---

## 1. Instalación de dependencias

### 1.1. Dependencia externa (obligatoria, no se instala con pip)

**Pandoc** — motor de conversión Word → Markdown:

```bash
# Windows
winget install --id JohnMacFarlane.Pandoc

# macOS
brew install pandoc

# Linux (Debian/Ubuntu)
sudo apt install pandoc
```

### 1.2. Dependencias de Python

```bash
pip install -r requirements.txt
```

Esto instala:
- `opencv-python-headless`, `Pillow`, `numpy` — necesarias para la heurística de detección de diagramas.
- `python-docx` — necesaria para extraer descripciones de imagen y para la corrección de respaldo de encabezados.
- `anthropic` — **opcional**, solo necesaria si quieres usar IA con visión para una conversión a Mermaid más fiel (ver sección 4).

---

## 2. Versión 1 — Uso desde VS Code

1. Abre la carpeta del proyecto en VS Code.
2. (Opcional) Copia `config_docx_a_md.ejemplo.json` a `config_docx_a_md.json` y ajusta las rutas:

   ```json
   {
       "input": "ejemplo/entrada_ejemplo.docx",
       "output": "salida/documento.md",
       "images_dir": "salida/imagenes",
       "umbral_mermaid": 0.5,
       "usar_ia": true,
       "mantener_temporales": false,
       "verbose": true
   }
   ```

3. Abre `convertir_docx_a_md_vscode.py` y pulsa **F5** (o "Run Python File").

También puedes configurar rutas mediante variables de entorno (útil en
`launch.json`):

```json
{
    "name": "Python: convertir_docx_a_md_vscode",
    "type": "debugpy",
    "request": "launch",
    "program": "${workspaceFolder}/convertir_docx_a_md_vscode.py",
    "env": {
        "DOCX_MD_INPUT": "${workspaceFolder}/ejemplo/entrada_ejemplo.docx",
        "DOCX_MD_OUTPUT": "${workspaceFolder}/salida/documento.md"
    }
}
```

Orden de prioridad: **argumentos CLI opcionales** > **variables de entorno** > **config_docx_a_md.json** > valores por defecto.

---

## 3. Versión 2 — Uso desde terminal (CLI)

```bash
python convertir_docx_a_md_cli.py --input entrada.docx --output salida/documento.md
```

### Opciones disponibles

| Flag                    | Corto | Descripción                                                              | Por defecto        |
|-------------------------|-------|----------------------------------------------------------------------------|---------------------|
| `--input`               | `-i`  | Ruta del documento Word (.docx) de entrada (**obligatorio**)                | —                   |
| `--output`              | `-o`  | Ruta del archivo Markdown (.md) de salida (**obligatorio**)                 | —                   |
| `--images-dir`          |       | Carpeta para las imágenes que NO se conviertan a Mermaid                    | `<salida>/imagenes` |
| `--mermaid-threshold`   |       | Sensibilidad (0.0-1.0) de la heurística de detección de diagramas           | `0.5`               |
| `--no-ia`               |       | Desactiva la IA con visión aunque esté configurada; usa siempre la heurística| (IA activada)       |
| `--keep-temp`           |       | Conserva la carpeta de medios bruta extraída por Pandoc                     | `False`             |
| `--verbose`             | `-v`  | Salida detallada (comandos ejecutados, puntuaciones de cada imagen, etc.)   | `False`             |
| `--version`             |       | Muestra la versión del script                                              | —                   |

### Ejemplo completo

```bash
python convertir_docx_a_md_cli.py \
    -i manual.docx \
    -o salida/manual.md \
    --images-dir salida/imagenes \
    --mermaid-threshold 0.6 \
    --verbose
```

---

## 4. Conversión a Mermaid: heurística vs. IA con visión

Convertir automáticamente una imagen arbitraria a sintaxis Mermaid **real y
fiel** (con las etiquetas de texto correctas en cada caja, las flechas en la
dirección correcta, etc.) es, en general, un problema muy difícil sin un
modelo de IA con capacidad de visión: una heurística de procesamiento de
imagen puede estimar razonablemente bien SI una imagen "parece" un diagrama,
pero no puede "leer" su contenido semántico.

Por eso, este proyecto ofrece **dos niveles**:

1. **Modo heurístico (por defecto, sin configuración adicional)**: se genera
   un **esqueleto Mermaid aproximado** (con nodos genéricos "Paso A", "Paso
   B"... conectados en secuencia, en la orientación horizontal/vertical más
   probable según la proporción de la imagen). Este esqueleto está pensado
   como **punto de partida editable**: cada bloque incluye un comentario
   claro indicando que debes revisarlo y completarlo consultando la imagen
   original (que se conserva junto al Markdown para ese fin).

2. **Modo IA con visión (opcional)**: si instalas el paquete `anthropic` y
   configuras una clave de API válida en la variable de entorno
   `ANTHROPIC_API_KEY`, el script enviará cada imagen candidata a un modelo
   de IA con visión, pidiéndole que transcriba fielmente el diagrama a
   sintaxis Mermaid. Esto produce resultados mucho más precisos (con las
   etiquetas de texto reales), aunque sigue recomendándose revisar el
   resultado.

   ```bash
   export ANTHROPIC_API_KEY="tu-clave-aquí"     # Linux/macOS
   set ANTHROPIC_API_KEY=tu-clave-aquí          # Windows (cmd)

   python convertir_docx_a_md_cli.py -i entrada.docx -o salida.md
   ```

   Si el paquete o la clave no están disponibles, el script lo detecta
   automáticamente y recurre al modo heurístico sin interrumpir la ejecución.

### ¿Cómo decide el script qué imágenes son "candidatas" a Mermaid?

La función `es_candidato_a_mermaid` (en `docx_a_md_core.py`) combina
varias métricas calculadas con OpenCV sobre cada imagen extraída:

- **Fondo mayoritariamente claro** (típico de diagramas exportados).
- **Pocos colores únicos** (paleta plana, no fotográfica).
- **Alta proporción de líneas horizontales/verticales** (cajas y flechas).
- **Presencia de suficientes líneas rectas** para parecer un diagrama de cajas.

El resultado es una puntuación entre 0 y 1; si supera el umbral configurado
(`--mermaid-threshold`, por defecto `0.5`), la imagen se trata como
diagrama. Puedes ajustar este umbral según tus documentos:
- Súbelo (p. ej. `0.65`) si el script está convirtiendo a Mermaid imágenes
  que en realidad son fotografías o capturas de pantalla complejas.
- Bájalo (p. ej. `0.35`) si el script está dejando como imagen normal
  diagramas que sí te gustaría intentar convertir.

---

## 5. Cómo funciona el pipeline internamente

1. **Verificación** de que Pandoc esté instalado.
2. **Conversión estructural** del `.docx` a Markdown con Pandoc (formato
   GFM), que preserva encabezados, párrafos, listas y tablas, y extrae
   automáticamente todas las imágenes incrustadas a una carpeta temporal.
3. **Corrección de respaldo de encabezados**: si Pandoc no reconoce los
   estilos de encabezado del documento (puede ocurrir con documentos
   generados por ciertas herramientas de terceros), se reconstruyen
   automáticamente leyendo los estilos reales con `python-docx`.
4. **Extracción de descripciones/alt-text** reales del `.docx` original
   (a menudo más útiles que las que deja Pandoc por defecto).
5. **Localización de imágenes** en el Markdown generado (Pandoc puede
   representarlas como `![alt](ruta)` o como etiquetas `<img>` si tienen
   un tamaño explícito; el script reconoce ambos formatos).
6. **Análisis heurístico** de cada imagen (métricas de OpenCV).
7. Para las **candidatas a diagrama**: generación de Mermaid (IA si está
   disponible, o esqueleto heurístico en caso contrario), conservando
   además una copia de la imagen original para referencia.
8. Para el **resto de imágenes**: se copian organizadamente a la carpeta
   de imágenes de salida, con nombres limpios.
9. **Reconstrucción** del Markdown final con todas las sustituciones.
10. **Limpieza** de archivos temporales (salvo `--keep-temp`).

---

## 6. Solución de problemas

| Síntoma                                                        | Causa probable / solución                                                                 |
|-------------------------------------------------------------------|--------------------------------------------------------------------------------------------|
| `HerramientaNoEncontradaError`                                    | Falta Pandoc en el PATH. Revisa la sección 1.1.                                            |
| Ninguna imagen se convierte a Mermaid                              | Prueba a bajar `--mermaid-threshold` (p. ej. a `0.35`) o revisa las puntuaciones con `--verbose`. |
| Se convierten a Mermaid imágenes que en realidad son fotos          | Sube `--mermaid-threshold` (p. ej. a `0.65`).                                               |
| Los encabezados no aparecen como `#`, `##`... en el Markdown        | El script ya intenta corregir esto automáticamente; si persiste, revisa que el .docx use estilos de encabezado reales (`Heading 1`, `Heading 2`...) y no solo texto en negrita. |
| El bloque Mermaid generado no es fiel al diagrama original          | Es esperable en modo heurístico (esqueleto aproximado): revisa y completa manualmente, o configura la IA con visión (sección 4). |
| `ModuleNotFoundError: No module named 'anthropic'`                 | Solo ocurre si activas el modo IA; instala con `pip install anthropic` o usa `--no-ia`.     |

---

## 7. Archivo de ejemplo

`ejemplo/entrada_ejemplo.docx` (no incluido por defecto; añade aquí tu
propio documento Word de prueba) puede convertirse con:

```bash
python convertir_docx_a_md_cli.py -i ejemplo/entrada_ejemplo.docx -o salida/documento.md --verbose
```
