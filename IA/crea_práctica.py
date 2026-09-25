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
                    Eres un experto en automatización industrial y en la creación de GRAFCETs.
                    Tu tarea es analizar las ideas proporcionadas y generar un GRAFCET detallado para cada una de ellas,
                    incluyendo los pasos, transiciones y acciones necesarias para implementar el proceso descrito. 
                    Asegúrate de que cada GRAFCET sea claro, preciso y fácil de entender, utilizando la notación estándar de GRAFCET. 
                    Además, proporciona una breve explicación de cada paso y transición, así como cualquier recomendación 
                    adicional para optimizar el proceso.  
                    """
    
    user_prompt = f"""
                        You are a highly experienced expert in industrial automation, control systems, and fashion manufacturing processes. You specialize in creating high-quality educational materials, particularly hands-on laboratory practices and technical exercises for engineering students.

Create a complete **teaching practice (lab assignment)** focused on industrial automation applied to the fashion/apparel production industry.

### Core Requirements:

1. **Scenario**: Design a realistic and engaging automation problem based on a fashion production process (e.g., automated cutting, sewing, dyeing, packaging, or material handling line). The problem must be technically rich and educationally valuable.

2. **Documentation**:
   - Provide a full description of the current manual or semi-automated process and the plant layout.
   - Generate **ALL necessary diagrams** using Mermaid syntax to clearly illustrate:
     - Plant layout / floor plan
     - Process flow diagram (PFD)
     - Detailed sequence of operations
     - Sensor and actuator locations
     - Any other relevant schematics

3. **GRAFCET Solution**:
   - Students must solve the automation problem using **GRAFCET** (Graphe de Commande Étape-Transition).
   - Include a **detailed, step-by-step guide** on how to design GRAFCET diagrams (methodology, rules, best practices, translation from process description to GRAFCET, etc.).
   - Provide a complete correct GRAFCET solution as a reference (for the teacher), plus a partial or blank version for students.

4. **Educational Design**:
   - The practice should take a student approximately **2 hours** to complete.
   - Include clear learning objectives, required prior knowledge, materials needed, and evaluation criteria.
   - Structure the document with sections: Introduction, Objectives, Problem Statement, Process Description, Diagrams, Tasks for the Student, GRAFCET Design Methodology, Deliverables, and References.

5. **Output Format**:
   - Generate the entire practice as a **single, well-structured Markdown file**.
   - Use Mermaid diagrams extensively for all graphics (flowcharts, plant layouts, GRAFCET diagrams, etc.).
   - The Markdown must be **optimized for conversion to .docx** (proper headings, page breaks via HTML comments if needed, clean tables, numbered sections, image sizing considerations, etc.).
   - The full document should be **substantial** — equivalent to at least 10 pages when converted to Word (rich content, detailed explanations, multiple diagrams, and comprehensive instructions).
   - All text content (instructions, explanations, methodology, etc.) must be written in **professional Spanish (es-ES)**.
   - Mermaid code blocks must be correctly formatted and functional.

### Additional Guidelines:
- Make the practice challenging but solvable within the time frame.
- Use realistic fashion industry terminology and constraints (fabric handling, quality control, safety, flexibility for different models, etc.).
- Ensure all Mermaid diagrams are high quality and easy to understand.
- Maintain excellent pedagogical quality: progressive difficulty, clear instructions, and helpful hints where appropriate.

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
        # Opcional: guardar resultados en un archivo
        # yaml_pandoc = f"""
        #                 ---
        #                 title: "Práctica_generada"
        #                 author: Rafael Puerto
        #                 date: July 04, 2026
        #                 output:
        #                 word_document:
        #                     path: "./practicas_generadas/output_doc.docx"
        #                 resource-path: "./practicas/practicas_generadas/assets/"
        #                 --- 
        #                 """

        name_file = "/Users/rafa/Programas/tmp/resultados_" + resultado['modelo'] + ".md"
        print("\n\n📄 Resumen guardado en " + name_file)
        with open(name_file, "w", encoding="utf-8") as f:
            #f.write(f"IDEA: {practica_docente}\n")
            #f.write("-" * 60 + "\n")
            #f.write(yaml_pandoc + "\n")
            f.write(f"{resultado['texto']}\n")
            #f.write("-" * 60 + "\n")
            f.close()