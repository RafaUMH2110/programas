# Ejemplo 1 de suso de API de Anthropic
# https://www.anthropic.com/index/claude-api    

import anthropic

client = anthropic.Anthropic()

respuesta = client.messages.create(
    model="claude-haiku-4-5-20251001",
    max_tokens=512,
    system="""Eres un programador experto en python que quiere aprender a utilizar la API de Anthropic.
            Responde a la pregunta de forma clara y concisa.
            Si no sabes la respuesta, di que no lo sabes.""",
    messages=[
        {"role": "user", "content": "Explicamé este código de Python:\n\n```python\nimport anthropic\n\nclient = anthropic.Anthropic()\n\nrespuesta = client.messages.create(\n    model=\"claude-haiku-4-5-20251001\",\n    max_tokens=512,\n    system=\"\"\"Eres un programador experto en python que quiere aprender a utilizar la API de Anthropic.\n            Responde a la pregunta de forma clara y concisa.\n            Si no sabes la respuesta, di que no lo sabes.\"\"\",\n    messages=[\n        {\"role\": \"user\", \"content\": \"Explicamé este código de Python:\"}\n    ]\n)"""},
    ]
)

print(respuesta.content[0].text) # type: ignore

# Opcional: guardar resultados en un archivo
print("\n\n📄 Resumen guardado en resultados_haiku.txt")
with open("resultados.txt", "w", encoding="utf-8") as f:
    for r in respuesta.content: # type: ignore
        f.write(f"{r.text}\n") # type: ignore   
        f.write("-" * 60 + "\n")
    f.close()