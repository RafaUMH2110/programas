ANTHROPIC_MODELS = {
    # --- Claude 1 / Instant (obsoletos, retirados) ---
    "Claude 1": [
        "claude-v1", "claude-v1.0", "claude-v1.2", "claude-v1.3", "claude-v1-100k",
    ],
    "Claude Instant 1": [
        "claude-instant-v1", "claude-instant-v1.0", "claude-instant-v1.1",
        "claude-instant-v1.2", "claude-instant-1", "claude-instant-1.2",
    ],

    # --- Claude 2 (obsoletos, retirados) ---
    "Claude 2": ["claude-2", "claude-2.0", "claude-2.1"],

    # --- Claude 3 ---
    "Claude 3": [
        "claude-3-opus-20240229",
        "claude-3-sonnet-20240229",
        "claude-3-haiku-20240307",
    ],

    # --- Claude 3.5 / 3.7 ---
    "Claude 3.5": [
        "claude-3-5-sonnet-20240620",
        "claude-3-5-sonnet-20241022",
        "claude-3-5-haiku-20241022",
    ],
    "Claude 3.7": ["claude-3-7-sonnet-20250219"],

    # --- Claude 4 / 4.1 ---
    "Claude 4": [
        "claude-opus-4-20250514",
        "claude-sonnet-4-20250514",
    ],
    "Claude 4.1": ["claude-opus-4-1-20250805"],

    # --- Claude 4.5 ---
    "Claude 4.5": [
        "claude-sonnet-4-5-20250929",
        "claude-haiku-4-5-20251001",
        "claude-opus-4-5-20251101",
    ],

    # --- Generaciones más recientes (verificar en la documentación) ---
    "Claude 4.6": ["claude-sonnet-4-6", "claude-opus-4-6"],
    "Claude 5": [
        "claude-sonnet-5",
        "claude-opus-5-5",
        "claude-fable-5-1",   # nivel Mythos con medidas de seguridad adicionales
    ],
}

# Lista plana con todos los identificadores
ALL_MODELS = [m for group in ANTHROPIC_MODELS.values() for m in group]

if __name__ == "__main__":
    print(len(ALL_MODELS), "modelos")
    for m in ALL_MODELS:
        print(m)

# Lista oficial. Para comprobar cuáles siguen activos, 
# usa el endpoint GET /v1/models de la API o la página de deprecaciones de docs.claude.com.