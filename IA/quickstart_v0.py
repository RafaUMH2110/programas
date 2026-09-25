import anthropic
# import pprint


client = anthropic.Anthropic()


message = client.messages.create(
    model="claude-opus-4-7",
    max_tokens=1000,
    messages=[
        {
            "role": "user",
            "content": "Qué se puede comer en Aspe. Alicante, España?",
        }
    ],
)
print(message.content)



# def contestar_pregunta(model, system_prompt,temperatura,content):
#     message = client.messages.create(
#         context = {"role": "system","content":system_prompt}
#         messages = [
#             {
#                 "role": system_prompt,
#                 "content": content,
#             }
#         ],
#     )



# system_prompt = """
#     Eres un especialista en gastronomía
# """

# respuesta= contestar_pregunta(model, system_prompt,temperatura,content)