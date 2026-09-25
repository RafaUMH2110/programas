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
    practica_docente = leer_fichero_markdown("/Users/rafa/Downloads/practica/practica_docente.md")
    system_prompt = ("""
                    Eres un experto en automatización industrial y en la creación de GRAFCETs.
                    Tu tarea es analizar las ideas proporcionadas y generar un GRAFCET detallado para cada una de ellas,
                    incluyendo los pasos, transiciones y acciones necesarias para implementar el proceso descrito. 
                    Asegúrate de que cada GRAFCET sea claro, preciso y fácil de entender, utilizando la notación estándar de GRAFCET. 
                    Además, proporciona una breve explicación de cada paso y transición, así como cualquier recomendación 
                    adicional para optimizar el proceso.  
                    """)
    
    user_prompt = f"""
                        Analiza la práctica docente de automatización industrial siguiente {practica_docente} que está en formato Markdown 
                        y genera un GRAFCET detallado queresuelva la práctica propuesta. Describe las etapas y acciones necesarias para 
                        implementar el proceso descrito.
                        Asegúrate de que cada GRAFCET sea claro, preciso y fácil de entender, utilizando la notación estándar de GRAFCET. 
                        Además, proporciona una breve explicación de cada paso y transición, así como cualquier recomendación adicional para 
                        optimizar el proceso. La respuesta debe estar en formato Markdown y contener un diagrama de GRAFCET representado
                        con gráficos en formato mermaid.
                    """

    max_tokens_available = 16000
    if cuenta_tokens:
        print(f"Tokens estimados del prompt: {contar_tokens(user_prompt)}")
        print(f"Tokens estimados del system prompt: {contar_tokens(system_prompt)}")
    else:
        resultado = responder(prompt_user=user_prompt, system=system_prompt, modelo="haiku", max_tokens=max_tokens_available)
        print(f"📝 Respuesta     : {resultado['texto']}")
        print(f"📊 Tokens entrada: {resultado['tokens_entrada']}  |  salida: {resultado['tokens_salida']}")
        print(f"🛑 Razón de parada: {resultado['razon_parada']}")
        print(f"🤖 Modelo usado  : {resultado['modelo']}")
        # Opcional: guardar resultados en un archivo
        print("\n\n📄 Resumen guardado en resultados.md")
        with open("/Users/rafa/Downloads/practica/resultados.md", "w", encoding="utf-8") as f:
            #f.write(f"IDEA: {practica_docente}\n")
            #f.write("-" * 60 + "\n")
            f.write(f"RESPUESTA:\n{resultado['texto']}\n")
            #f.write("-" * 60 + "\n")
            f.close()