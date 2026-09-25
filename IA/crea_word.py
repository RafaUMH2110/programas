import io
import re
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

try:
    from PIL import Image
except ImportError:  # pragma: no cover
    Image = None

try:
    from docx.enum.section import WD_SECTION_START
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.shared import Pt, RGBColor
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
except ImportError:  # pragma: no cover - depende del entorno local
    WD_SECTION_START = None
    WD_ALIGN_PARAGRAPH = None
    Pt = RGBColor = None
    OxmlElement = None
    qn = None

import anthropic

# ── Modelos disponibles ──────────────────────────────────────────────────────
MODELOS = {
    "haiku":  "claude-haiku-4-5-20251001",   # Rápido y barato
    "sonnet": "claude-sonnet-4-6",            # Equilibrado (recomendado)
    "sonnet-5": "claude-sonnet-5",          # Más potente y preciso
    "opus":   "claude-opus-4-6",              # Más potente
}

def leer_fichero_markdown(ruta: str) -> str:
    """Lee un fichero Markdown y devuelve su contenido como texto."""
    try:
        with open(ruta, "r", encoding="utf-8") as archivo:
            return archivo.read()
    except FileNotFoundError as exc:
        raise FileNotFoundError(f"No se encontró el fichero Markdown: {ruta}") from exc


def crear_cliente() -> anthropic.Anthropic:
    """Crea el cliente de Anthropic. La API key se lee de la variable
    de entorno ANTHROPIC_API_KEY automáticamente."""
    return anthropic.Anthropic()


def contar_tokens(texto: str) -> int:
    """Estima el número de tokens de un texto mediante una heurística simple."""
    if not texto:
        return 0
    return len(re.findall(r"\w+|[^\w\s]", texto))


def _aniadir_numero_pagina(documento) -> None:
    """Añade un número de página dinámico en el pie del documento."""
    section = documento.sections[0]
    footer = section.footer
    paragraph = footer.paragraphs[0]
    assert WD_ALIGN_PARAGRAPH is not None
    paragraph.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    paragraph.text = ""

    fld_simple = OxmlElement("w:fldSimple") # type: ignore
    fld_simple.set(qn("w:instr"), "PAGE") # type: ignore
    fld_simple.set(qn("w:dirty"), "true") # type: ignore

    r = OxmlElement("w:r") # type: ignore
    r_pr = OxmlElement("w:rPr") # type: ignore
    r_style = OxmlElement("w:rStyle") # type: ignore
    r_style.set(qn("w:val"), "Strong") # type: ignore
    r_pr.append(r_style)
    r.append(r_pr)
    fld_simple.append(r)
    paragraph._p.append(fld_simple)


def _extension_por_tipo_contenido(content_type: str | None) -> str:
    """Devuelve la extensión adecuada para la imagen según el tipo MIME."""
    if content_type is None:
        return ".jpg"
    tipo = content_type.lower().split(";", 1)[0].strip()
    mapa = {
        "image/jpeg": ".jpg",
        "image/jpg": ".jpg",
        "image/png": ".png",
        "image/gif": ".gif",
        "image/webp": ".webp",
        "image/bmp": ".bmp",
        "image/svg+xml": ".svg",
    }
    return mapa.get(tipo, ".jpg")


def _nombre_archivo_imagen_desde_url(ruta_imagen: str, content_type: str | None = None) -> str:
    """Genera un nombre de archivo seguro y con extensión válida para una URL de imagen."""
    parsed = urlparse(ruta_imagen)
    nombre_base = Path(parsed.path).name.strip()
    nombre_base = re.sub(r"[^A-Za-z0-9._-]", "_", nombre_base) if nombre_base else "imagen"
    base_sin_ext = Path(nombre_base).stem or "imagen"
    extension = Path(nombre_base).suffix.lower() or _extension_por_tipo_contenido(content_type)
    if not nombre_base:
        nombre_base = f"{base_sin_ext}{extension}"
    elif Path(nombre_base).suffix.lower() == "":
        nombre_base = f"{base_sin_ext}{extension}"
    return nombre_base or "imagen.jpg"


def _normalizar_bytes_imagen(contenido: bytes) -> tuple[bytes, str] | None:
    """Valida que el contenido sea una imagen y devuelve bytes con extensión compatible."""
    if not contenido:
        return None

    if contenido.startswith(b"\x89PNG\r\n\x1a\n"):
        return contenido, ".png"
    if contenido.startswith(b"\xff\xd8\xff"):
        return contenido, ".jpg"
    if contenido.startswith((b"GIF87a", b"GIF89a")):
        return contenido, ".gif"
    if contenido.startswith(b"RIFF") and contenido[8:12] == b"WEBP":
        return contenido, ".webp"
    if contenido.startswith(b"BM"):
        return contenido, ".bmp"

    if Image is not None:
        try:
            with Image.open(io.BytesIO(contenido)) as imagen:
                formato = (imagen.format or "PNG").upper()
                extensiones = {"JPEG": ".jpg", "JPG": ".jpg", "PNG": ".png", "WEBP": ".webp", "GIF": ".gif", "BMP": ".bmp"}
                if formato not in extensiones:
                    return None
                buffer = io.BytesIO()
                imagen.save(buffer, format=formato)
                return buffer.getvalue(), extensiones[formato]
        except Exception:
            return None

    return None


def _resolver_ruta_imagen(ruta_imagen: str, ruta_base: Path | None = None) -> Path | None:
    """Devuelve una ruta local para una imagen de URL o de disco."""
    if ruta_imagen.startswith("http://") or ruta_imagen.startswith("https://"):
        if ruta_base is None:
            ruta_base = Path.cwd()
        carpeta = ruta_base / "imagenes"
        carpeta.mkdir(parents=True, exist_ok=True)

        solicitud = urllib.request.Request(
            ruta_imagen,
            headers={"User-Agent": "Mozilla/5.0"},
        )
        try:
            with urllib.request.urlopen(solicitud) as respuesta:
                contenido = respuesta.read()
                resultado = _normalizar_bytes_imagen(contenido)
                if resultado is None:
                    return None
                contenido_normalizado, extension = resultado
                nombre = _nombre_archivo_imagen_desde_url(ruta_imagen, respuesta.headers.get_content_type())
                nombre_path = Path(nombre)
                if nombre_path.suffix.lower() not in {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"}:
                    nombre = f"{nombre_path.stem or 'imagen'}{extension}"
        except (OSError, urllib.error.URLError):
            return None

        destino = carpeta / nombre
        if not destino.exists():
            try:
                with destino.open("wb") as archivo:
                    archivo.write(contenido_normalizado)
            except OSError:
                return None
        return destino

    ruta = Path(ruta_imagen)
    if not ruta.is_absolute() and ruta_base is not None:
        ruta = (Path(ruta_base) / ruta).resolve()
    return ruta if ruta.exists() else None


def _normalizar_markdown_documento(texto: str) -> str:
    """Elimina separadores horizontales, líneas vacías y artefactos del Markdown."""
    if not texto:
        return ""

    texto = texto.replace("\r\n", "\n").replace("\r", "\n")
    lineas = texto.split("\n")
    salida: list[str] = []

    for linea in lineas:
        texto_limpio = linea.strip()
        if not texto_limpio:
            continue
        if re.fullmatch(r"[-*_]{3,}", texto_limpio):
            continue
        if texto_limpio in {"```", "```markdown"}:
            continue
        salida.append(linea.rstrip())

    texto_normalizado = "\n".join(salida).strip()
    return texto_normalizado + ("\n" if texto_normalizado else "")


def crear_prompt_documento_word(
    titulo: str,
    audiencia: str,
    objetivo: str,
    estilo: str = "elegante, claro y ligero",
    incluir_imagenes: bool = True,
) -> str:
    """Genera un prompt listo para que Claude devuelva Markdown estructurado para Word."""
    return f"""
    Genera un documento profesional en español (es-ES), dirigido a: {audiencia}.
    Título principal: {titulo}
    Objetivo: {objetivo}
    Estilo visual: {estilo}.

    Requisitos obligatorios:
    1) Responde ÚNICAMENTE en Markdown listo para Word.
    2) Usa una estructura clara con títulos principales y subsecciones:
       # Título
       ## Sección 1
       ### Apartado
    3) Escribe en un tono pedagógico, cercano y útil para estudiantes.
    4) Incluye texto explicativo breve y preciso, sin divagar.
    5) Usa listas con "-" y numeradas con "1."
    6) Añade al menos 3 referencias de imágenes con formato Markdown: ![Descripción](https://ejemplo.com/imagen.jpg)
    7) Las imágenes deben ser relevantes para el contenido y compatibles con Word.
    8) No añadas comentarios fuera del documento ni frases tipo: 'Aquí tienes el documento'.
    9) No uses tablas complejas; prioriza claridad visual.
    10) El documento debe verse bien al importarlo a Word.

    Formato esperado:
    # Título
    ## Introducción
    ...
    ### Paso 1
    ...
    ![Descripción de la imagen](https://ejemplo.com/imagen.jpg)
    ...
    """


def _anadir_texto_enriquecido(documento, parrafo, texto: str, ruta_base: Path | None = None) -> None:
    """Añade texto con soporte básico para Markdown inline y eventualmente imágenes."""
    patron_imagen = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")
    ultimo = 0
    for match in patron_imagen.finditer(texto):
        if match.start() > ultimo:
            _anadir_texto_enriquecido(documento, parrafo, texto[ultimo:match.start()], ruta_base)

        alt = match.group(1).strip() or "Imagen"
        ruta_imagen = match.group(2).strip()
        ruta_imagen_path = _resolver_ruta_imagen(ruta_imagen, ruta_base)
        if ruta_imagen_path is not None:
            try:
                img_parrafo = documento.add_paragraph()
                img_parrafo.alignment = WD_ALIGN_PARAGRAPH.CENTER # type: ignore
                img_parrafo.add_run().add_picture(str(ruta_imagen_path), width=Pt(420)) # type: ignore
                caption_parrafo = documento.add_paragraph()
                caption_parrafo.add_run(alt)
            except Exception:
                parrafo.add_run(f"[Imagen: {alt}]")
        else:
            parrafo.add_run(f"[Imagen: {alt}]")
        ultimo = match.end()

    if ultimo < len(texto):
        texto_restante = texto[ultimo:]
        patron = re.compile(r"(\*\*([^*]+)\*\*|__([^_]+)__|\*([^*]+)\*|_([^_]+)_|\[([^\]]+)\]\(([^)]+)\))")
        ultimo_texto = 0
        for match in patron.finditer(texto_restante):
            if match.start() > ultimo_texto:
                parrafo.add_run(texto_restante[ultimo_texto:match.start()])

            if match.group(1).startswith("**") or match.group(1).startswith("__"):
                valor = match.group(2) or match.group(3)
                run = parrafo.add_run(valor)
                run.bold = True
            elif match.group(1).startswith("*") or match.group(1).startswith("_"):
                valor = match.group(4) or match.group(5)
                run = parrafo.add_run(valor)
                run.italic = True
            else:
                texto_enlace = match.group(6)
                run = parrafo.add_run(texto_enlace)
                run.font.underline = True
                run.font.color.rgb = RGBColor(0, 0, 255) # pyright: ignore[reportOptionalCall]
            ultimo_texto = match.end()

        if ultimo_texto < len(texto_restante):
            parrafo.add_run(texto_restante[ultimo_texto:])


def respuesta_a_word(
    texto: str,
    ruta_salida: str | Path,
    titulo: str = "Documento generado",
    ruta_base: str | Path | None = None,
) -> str:
    """Guarda el texto recibido en un archivo Word (.docx) con estilo profesional.

    Admite encabezados Markdown, listas, énfasis y referencias a imágenes locales
    con el formato `![alt](ruta/imagen.png)`.
    """
    try:
        from docx import Document
    except ImportError as exc:
        raise ModuleNotFoundError(
            "Falta la dependencia 'python-docx'. Instálala con: pip install python-docx"
        ) from exc

    if WD_SECTION_START is None or WD_ALIGN_PARAGRAPH is None:
        raise ModuleNotFoundError(
            "Falta la dependencia 'python-docx'. Instálala con: pip install python-docx"
        )

    ruta = Path(ruta_salida)
    if ruta.suffix.lower() != ".docx":
        ruta = ruta.with_suffix(".docx")
    ruta.parent.mkdir(parents=True, exist_ok=True)

    documento = Document()
    documento.styles["Normal"].font.name = "Calibri" # pyright: ignore[reportAttributeAccessIssue]
    documento.styles["Normal"].font.size = Pt(11) # type: ignore

    if ruta_base is None:
        ruta_base = ruta.parent

    titulo_parrafo = documento.add_paragraph()
    titulo_run = titulo_parrafo.add_run(titulo)
    titulo_run.bold = True
    titulo_run.font.size = Pt(24) # type: ignore
    titulo_run.font.color.rgb = RGBColor(0, 61, 104) # type: ignore
    titulo_parrafo.alignment = WD_ALIGN_PARAGRAPH.CENTER

    documento.add_paragraph()

    texto = _normalizar_markdown_documento(texto)
    if texto and texto.strip():
        lineas = texto.splitlines()
        bloque_texto: list[str] = []

        def flush_bloque_texto() -> None:
            if not bloque_texto:
                return
            parrafo = documento.add_paragraph()
            contenido = " ".join(bloque_texto).strip()
            _anadir_texto_enriquecido(documento, parrafo, contenido, Path(ruta_base) if ruta_base is not None else None)
            bloque_texto.clear()

        for linea in lineas:
            texto_limpio = linea.strip()
            if not texto_limpio:
                continue

            if texto_limpio.startswith("### "):
                flush_bloque_texto()
                parrafo = documento.add_heading(level=3)
                _anadir_texto_enriquecido(
                    documento, parrafo, texto_limpio[4:].strip(),
                    Path(ruta_base) if ruta_base is not None else None,
                )
            elif texto_limpio.startswith("## "):
                flush_bloque_texto()
                parrafo = documento.add_heading(level=2)
                _anadir_texto_enriquecido(
                    documento, parrafo, texto_limpio[3:].strip(),
                    Path(ruta_base) if ruta_base is not None else None,
                )
            elif texto_limpio.startswith("# "):
                flush_bloque_texto()
                parrafo = documento.add_heading(level=1)
                _anadir_texto_enriquecido(
                    documento, parrafo, texto_limpio[2:].strip(),
                    Path(ruta_base) if ruta_base is not None else None,
                )
            elif texto_limpio.startswith("- "):
                flush_bloque_texto()
                parrafo = documento.add_paragraph(style="List Bullet")
                _anadir_texto_enriquecido(
                    documento, parrafo, texto_limpio[2:].strip(),
                    Path(ruta_base) if ruta_base is not None else None,
                )
            elif re.match(r"^\d+\.\s", texto_limpio):
                flush_bloque_texto()
                parrafo = documento.add_paragraph(style="List Number")
                _anadir_texto_enriquecido(
                    documento, parrafo, texto_limpio,
                    Path(ruta_base) if ruta_base is not None else None,
                )
            elif re.fullmatch(r"!\[[^\]]*\]\([^)]+\)", texto_limpio):
                flush_bloque_texto()
                match = re.fullmatch(r"!\[([^\]]*)\]\(([^)]+)\)", texto_limpio)
                assert match is not None
                alt = match.group(1).strip() or "Imagen"
                ruta_imagen_path = _resolver_ruta_imagen(
                    match.group(2).strip(),
                    Path(ruta_base) if ruta_base is not None else None,
                )
                if ruta_imagen_path is not None:
                    try:
                        parrafo = documento.add_paragraph()
                        parrafo.alignment = WD_ALIGN_PARAGRAPH.CENTER
                        parrafo.add_run().add_picture(str(ruta_imagen_path), width=Pt(420)) # type: ignore
                        documento.add_paragraph(alt)
                    except Exception:
                        documento.add_paragraph(f"[Imagen: {alt}]")
                else:
                    documento.add_paragraph(f"[Imagen: {alt}]")
            else:
                bloque_texto.append(texto_limpio)

        flush_bloque_texto()

    documento.sections[0].start_type = WD_SECTION_START.CONTINUOUS
    _aniadir_numero_pagina(documento)
    documento.save(str(ruta))
    return str(ruta)


def responder(
    prompt_user: str,
    modelo: str = "sonnet-5",
    max_tokens: int = 4096,
    system: str = (
        "Eres un asistente creativo y conciso. "),
) -> dict:
    """
    Lee una lista de ideas y devuelve una respuesta de Claude para cada una.

    Args:
        ideas:      Lista de ideas o preguntas.
        modelo:     "haiku", "sonnet" u "opus".
        max_tokens: Límite de tokens por respuesta.

    Returns:
        Lista de dicts con {"idea": ..., "respuesta": ...}.
    """
    if modelo not in MODELOS:
        raise ValueError(f"Modelo '{modelo}' no válido. Elige: {list(MODELOS)}")

    model_id = MODELOS[modelo]
    client = crear_cliente()
    resultados = []

    print(f"\n🤖 Modelo: {model_id}")
    print("=" * 60)

    mensaje = client.messages.create(
            model=model_id,
            max_tokens=max_tokens,
            system=system,
            messages=[
                {"role": "user", "content": prompt_user}
            ],
    )

    bloques = getattr(mensaje, "content", []) or []
    textos = []
    for bloque in bloques:
        tipo = getattr(bloque, "type", None)
        if tipo == "text":
            texto_bloque = getattr(bloque, "text", None)
            if texto_bloque:
                textos.append(texto_bloque)
        elif isinstance(bloque, dict):
            if bloque.get("type") == "text" and isinstance(bloque.get("text"), str):
                textos.append(bloque["text"])

    texto_respuesta = "\n".join(textos).strip()
    texto_respuesta = _normalizar_markdown_documento(texto_respuesta)
    if not texto_respuesta:
        texto_respuesta = ""

    return {
        "texto": texto_respuesta,
        "tokens_entrada": mensaje.usage.input_tokens,
        "tokens_salida": mensaje.usage.output_tokens,
        "razon_parada": mensaje.stop_reason,
        "modelo": mensaje.model,
    }
    




# ── Ejemplo de uso ───────────────────────────────────────────────────────────
if __name__ == "__main__":

    cuenta_tokens = False  # Cambiar a True para contar tokens en lugar de generar respuesta
    #practica_docente = leer_fichero_markdown("/Users/rafa/Downloads/practica/practica_docente.md")
    system_prompt = """
                   Eres un experto en google, google drive y google colab.
                    """
    
    user_prompt = crear_prompt_documento_word(
        titulo="Acceso a Google Colab para alumnos de Tecnología en Moda",
        audiencia="alumnos de Tecnología en Moda de la UMH sin conocimientos previos sobre Google Colab",
        objetivo="Explicar detalladamente cómo acceder a Google Colab con la cuenta institucional de la UMH y usarlo de forma segura y práctica.",
        estilo="elegante, claro, ligero y orientado a estudiantes",
        incluir_imagenes=True,
    )

    max_tokens_available = 20000
    if cuenta_tokens:
        print(f"Tokens estimados del prompt: {contar_tokens(user_prompt)}")
        print(f"Tokens estimados del system prompt: {contar_tokens(system_prompt)}")
    else:
        resultado = responder(prompt_user=user_prompt, system=system_prompt, modelo="sonnet-5", max_tokens=max_tokens_available)
        print(f"📝 Respuesta     : {resultado['texto']}")
        print(f"📊 Tokens entrada: {resultado['tokens_entrada']}  |  salida: {resultado['tokens_salida']}")
        print(f"🛑 Razón de parada: {resultado['razon_parada']}")
        print(f"🤖 Modelo usado  : {resultado['modelo']}")
        
        name_file = "/Users/rafa/Programas/tmp/documento_colab_" + resultado['modelo'] + ".md"
        ruta_markdown = Path(name_file)
        ruta_markdown.parent.mkdir(parents=True, exist_ok=True)
        print("\n\n📄 Resumen guardado en " + str(ruta_markdown))
        with open(ruta_markdown, "w", encoding="utf-8") as f:
            f.write(f"{resultado['texto']}\n")

        word_file = "/Users/rafa/Programas/tmp/documento_colab_" + resultado['modelo'] + ".docx"
        ruta_base = Path("/Users/rafa/Programas/tmp")
        ruta_base.mkdir(parents=True, exist_ok=True)
        ruta_word = respuesta_a_word(
            resultado["texto"],
            word_file,
            titulo="Documento de configuración de Google Colab",
            ruta_base=ruta_base,
        )
        print(f"📄 Documento Word generado en: {ruta_word}")