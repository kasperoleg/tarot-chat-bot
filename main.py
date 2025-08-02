from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
import os
import time
import sys
import logging
from datetime import datetime

app = Flask(__name__)
CORS(app, origins=["*"])

# Ключ и эндпоинт
MISTRAL_API_KEY = os.environ.get('MISTRAL_API_KEY')
MISTRAL_ENDPOINT = "https://api.mistral.ai/v1/chat/completions"
start_time = time.time()
request_count = 0
error_count = 0

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def process_tarot_answer(raw_answer):
    try:
        sentences = raw_answer.split('.')
        final_answer = ". ".join(s.strip() for s in sentences if s.strip()) + "."
        final_answer = ' '.join(final_answer.split())
        return final_answer if len(final_answer.split()) < 400 else " ".join(final_answer.split()[:380]) + "..."
    except Exception as e:
        logger.error(f"Ошибка обработки ответа: {e}")
        return raw_answer[:400] + "."

def call_mistral_api(payload, max_retries=3):
    headers = {
        "Authorization": f"Bearer {MISTRAL_API_KEY}",
        "Content-Type": "application/json"
    }
    for attempt in range(max_retries):
        try:
            response = requests.post(MISTRAL_ENDPOINT, headers=headers, json=payload, timeout=30)
            if response.status_code == 200:
                return response
            elif response.status_code == 429:
                time.sleep(2 ** attempt)
            else:
                raise Exception(f"API error: {response.status_code}")
        except Exception as e:
            logger.error(f"Mistral API ошибка: {e}")
            if attempt == max_retries - 1:
                raise
            time.sleep(1)
    raise Exception("Mistral API все попытки неудачны")

@app.route('/')
def home():
    uptime = int(time.time() - start_time)
    return jsonify({
        "status": "🔮 Tarot Chat API работает!",
        "uptime_seconds": uptime,
        "requests_total": request_count,
        "version": "Fly.io Minimal"
    })

@app.route('/ping')
def ping():
    return jsonify({
        "status": "alive",
        "uptime_seconds": int(time.time() - start_time),
        "requests_total": request_count,
        "errors_total": error_count,
        "python_version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    })

@app.route('/tarot-chat', methods=['POST', 'OPTIONS'])
def tarot_chat():
    global request_count, error_count
    request_count += 1
    try:
        if not request.is_json:
            error_count += 1
            return jsonify({"error": "Требуется JSON"}), 400
        data = request.get_json()
        if not data or 'question' not in data:
            error_count += 1
            return jsonify({"error": "Отсутствует вопрос"}), 400
        user_question = data['question'].strip()
        tarot_prompt = f"""Ты опытный мастер Таро. Дай краткую трактовку (до 400 слов). Вопрос: {user_question}"""
        payload = {
            "model": "mistral-small-latest",
            "messages": [{"role": "user", "content": tarot_prompt}],
            "temperature": 0.7,
            "max_tokens": 500,
            "top_p": 0.9,
            "stop": ["\n\n\n", "###", "---"]
        }
        response = call_mistral_api(payload)
        result = response.json()
        if 'choices' in result and len(result['choices']) > 0:
            answer = process_tarot_answer(result['choices'][0]['message']['content'])
            return jsonify({"answer": answer})
        else:
            error_count += 1
            return jsonify({"error": "Пустой ответ от AI"}), 502
    except Exception as e:
        error_count += 1
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=False)
