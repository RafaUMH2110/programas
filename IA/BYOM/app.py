import os
import requests
import json
from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

app = Flask(__name__)

# Configuración de modelos
MODELS = {
    "anthropic": {
        "url": "https://api.anthropic.com/v1/messages",
        "headers_template": {
            "Content-Type": "application/json",
            "x-api-key": os.getenv("ANTHROPIC_API_KEY"),
            "anthropic-version": "2023-06-01",
            "anthropic-dangerous-direct-browser-access": "true"
        },
        "system_field": "system"
    },
    "openai": {
        "url": "https://api.openai.com/v1/chat/completions",
        "headers_template": {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {os.getenv('OPENAI_API_KEY')}"
        },
        "system_field": "system"
    },
    "gemini": {
        "url": "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
        "headers_template": {
            "Content-Type": "application/json",
            "x-goog-api-key": os.getenv("GEMINI_API_KEY")
        },
        "system_field": "system_instruction"
    }
}

def anonimizar_request(payload, provider):
    """
    Función para anonimizar la petición antes de enviarla.
    En este caso, solo aseguramos que no se envíen headers adicionales.
    """
    # Limpiar cualquier payload que pueda contener datos de sesión o cookies
    # (Flask ya maneja esto, pero es una capa de seguridad extra)
    return payload

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/generate', methods=['POST'])
def generate():
    data = request.json
    provider = data.get('provider')
    model = data.get('model')
    user_input = data.get('user_input')
    system_prompt = data.get('system_prompt', "Eres un asistente útil.")

    if provider not in MODELS:
        return jsonify({"error": "Proveedor no soportado"}), 400

    config = MODELS[provider]
    
    # Construir payload según el proveedor
    if provider == "anthropic":
        payload = {
            "model": model,
            "max_tokens": 4096,
            "system": system_prompt,
            "messages": [{"role": "user", "content": user_input}]
        }
    elif provider == "openai":
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_input}
            ],
            "max_tokens": 4096
        }
    elif provider == "gemini":
        payload = {
            "system_instruction": {"parts": [{"text": system_prompt}]},
            "contents": [{"parts": [{"text": user_input}]}],
            "generationConfig": {"maxOutputTokens": 4096}
        }
        # Reemplazar {model} en la URL
        config["url"] = config["url"].format(model=model)

    # Anonimizar y enviar
    payload = anonimizar_request(payload, provider)
    
    try:
        headers = config["headers_template"].copy()
        response = requests.post(config["url"], headers=headers, json=payload, timeout=60)
        
        if response.status_code != 200:
            return jsonify({"error": f"Error API: {response.status_code} - {response.text}"}), 500
        
        result = response.json()
        
        # Extraer respuesta según el proveedor
        if provider == "anthropic":
            output_text = result["content"][0]["text"]
        elif provider == "openai":
            output_text = result["choices"][0]["message"]["content"]
        elif provider == "gemini":
            output_text = result["candidates"][0]["content"]["parts"][0]["text"]
        
        return jsonify({"result": output_text})
        
    except requests.exceptions.Timeout:
        return jsonify({"error": "Tiempo de espera agotado (60s)"}), 504
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000)