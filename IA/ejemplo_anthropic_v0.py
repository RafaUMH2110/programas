import anthropic

# ── Modelos disponibles ──────────────────────────────────────────────────────
MODELOS = {
    "haiku":  "claude-haiku-4-5-20251001",   # Rápido y barato
    "sonnet": "claude-sonnet-4-6",            # Equilibrado (recomendado)
    "opus":   "claude-opus-4-6",              # Más potente
}


def crear_cliente() -> anthropic.Anthropic:
    """Crea el cliente de Anthropic. La API key se lee de la variable
    de entorno ANTHROPIC_API_KEY automáticamente."""
    return anthropic.Anthropic()


def responder_ideas(
    ideas: list[str],
    modelo: str = "haiku",
    max_tokens: int = 1024,
    system: str = (
        "Eres un asistente creativo y conciso. "),
) -> list[dict]:
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

    for i, idea in enumerate(ideas, 1):
        print(f"\n💡 Idea {i}: {idea}")
        print("-" * 40)

        mensaje = client.messages.create(
            model=model_id,
            max_tokens=max_tokens,
            system=system,
            messages=[
                {"role": "user", "content": idea}
            ],
        )

        respuesta = mensaje.content[0].text # type: ignore
        print(respuesta)

        resultados.append({"idea": idea, "respuesta": respuesta})

    return resultados


# ── Ejemplo de uso ───────────────────────────────────────────────────────────
if __name__ == "__main__":

    mis_ideas = [
        "Diseña una falda vaquera talla 40 con un toque vintage y genera una descripción de cómo sería.",
        "Crea un concepto para una chaqueta de cuero que combine estilo clásico con detalles modernos, y escribe una breve descripción de su diseño.",
    ]

    system_promp = ("""
                    Eres un diseñador de moda experto en tendencias actuales.
                    Para cada idea, genera un concepto creativo y una breve descripción.
                    Responde de forma clara y concisa.
                    """)
                    
    # Cambia "sonnet" por "haiku" u "opus" según tus necesidades
    resultados = responder_ideas(mis_ideas, modelo="haiku")

    # Opcional: guardar resultados en un archivo
    print("\n\n📄 Resumen guardado en resultados.txt")
    with open("resultados.txt", "w", encoding="utf-8") as f:
        for r in resultados:
            f.write(f"IDEA: {r['idea']}\n")
            f.write(f"RESPUESTA:\n{r['respuesta']}\n")
            f.write("-" * 60 + "\n")
        f.close()