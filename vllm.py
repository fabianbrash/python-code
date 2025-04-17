import requests
import urllib3

# Disable SSL certificate warnings (since we're using self-signed certs)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Configuration
API_URL = "https://your-vllm-server.local:8000/v1/chat/completions"
API_KEY = "your-api-key"  # Optional for vLLM; remove header if not needed
MODEL_NAME = "your-model-name"

# Headers (remove Authorization header if your vLLM doesn't require it)
headers = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {API_KEY}"
}

# User question
user_question = "What's the difference between CPU and GPU?"

# API payload
data = {
    "model": MODEL_NAME,
    "messages": [
        {"role": "user", "content": user_question}
    ],
    "temperature": 0.7
}

try:
    response = requests.post(API_URL, headers=headers, json=data, verify=False)
    response.raise_for_status()
    reply = response.json()["choices"][0]["message"]["content"]
    print("Assistant:", reply)
except requests.exceptions.RequestException as e:
    print("Error communicating with vLLM server:", e)
