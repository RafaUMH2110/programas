
clave_api = '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'

import openai
import pprint

system_prompt="""
Copie con precisión todas las direcciones de correo electrónico del siguiente texto y escríbalas,
una por línea. Escriba una dirección de correo electrónico solo si está escrita con precisión en el
texto de entrada. Si no hay direcciones de correo electrónico en el texto, escriba “N/A”. No
diga nada más.
"""

#configurador IA
model="gpt-4o-mini"
temperatura=0.5 # Especifica la 'creatividad' de la respuesta

def contestar_pregunta(model, system_prompt,temperatura,content):
    openai.api_key = clave_api
    context = {"role": "system","content":system_prompt}
    messages = [context]
    messages.append({"role": "user", "content": content})
    response = openai.chat.completions.create(
    model=model, messages=messages, temperature=temperatura)
    response_content = response.choices[0].message.content
    return response_content

lista_ideas = ["hablame de París un viaje de 3 días", "háblame de Aspe en Alicante (España) un viaje de una semana"]

system_prompt="""
Eres un especiaalista en viajes culturales y ocio
"""
for idea in lista_ideas:
    respuesta= contestar_pregunta(model, system_prompt,temperatura,idea)
    print(pprint.pformat(respuesta, indent=1, width=70))
    print("\n")