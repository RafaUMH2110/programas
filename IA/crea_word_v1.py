import re

import anthropic

# ── Modelos disponibles ──────────────────────────────────────────────────────
MODELOS = {
    "haiku":  "claude-haiku-4-5-20251001",   # Rápido y barato
    "sonnet": "claude-sonnet-4-6",            # Equilibrado (recomendado)
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


def responder(
    prompt_user: str,
    modelo: str = "haiku",
    max_tokens: int = 1024,
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

    #respuesta = mensaje.content[0].text # type: ignore
    #print(respuesta)
    return {
        "texto": mensaje.content[0].text, # type: ignore
        "tokens_entrada": mensaje.usage.input_tokens,
        "tokens_salida": mensaje.usage.output_tokens,
        "razon_parada": mensaje.stop_reason,
        "modelo": mensaje  .model,
    }
    




# ── Ejemplo de uso ───────────────────────────────────────────────────────────
if __name__ == "__main__":

    cuenta_tokens = False  # Cambiar a True para contar tokens en lugar de generar respuesta
    #practica_docente = leer_fichero_markdown("/Users/rafa/Downloads/practica/practica_docente.md")
    system_prompt = """
                    Eres un experto en google, google drive y google colab.
                    """
    
    user_prompt = f"""
                        

Output only the complete Markdown content, ready to be saved as a `.md` file.
                    """

    max_tokens_available = 20000
    if cuenta_tokens:
        print(f"Tokens estimados del prompt: {contar_tokens(user_prompt)}")
        print(f"Tokens estimados del system prompt: {contar_tokens(system_prompt)}")
    else:
        resultado = responder(prompt_user=user_prompt, system=system_prompt, modelo="sonnet", max_tokens=max_tokens_available)
        print(f"📝 Respuesta     : {resultado['texto']}")
        print(f"📊 Tokens entrada: {resultado['tokens_entrada']}  |  salida: {resultado['tokens_salida']}")
        print(f"🛑 Razón de parada: {resultado['razon_parada']}")
        print(f"🤖 Modelo usado  : {resultado['modelo']}")
        
        name_file = "/Users/rafa/Programas/tmp/resultados_" + resultado['modelo'] + ".md"
        print("\n\n📄 Resumen guardado en " + name_file)
        with open(name_file, "w", encoding="utf-8") as f:
            f.write(f"{resultado['texto']}\n")
            f.close()