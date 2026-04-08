import os
import requests
from flask import Flask, render_template, request, jsonify

app = Flask(__name__)

# --- Configuration ---
API_KEY = os.environ.get("RAFAY_API_KEY")
API_BASE = "https://models-qwen.genai-apps.fbclouddemo.us:31444/v1"
MODEL = "fb-qwen-7b-instruct-3"
MAX_CONTEXT = 8192  # This matches your vLLM --max-model-len

if not API_KEY:
    exit("ERROR: RAFAY_API_KEY environment variable is not set.")

def estimate_tokens(text):
    # Rough estimate: 4 characters per token is the industry standard heuristic
    return len(text) // 4

@app.route("/", methods=["GET"])
def index():
    return render_template("index.html")

@app.route("/chat", methods=["POST"])
def chat():
    user_data = request.json
    question = user_data.get("question", "")

    if not question:
        return jsonify({"error": "No question provided"}), 400

    # 1. Calculate how much room we have left
    system_prompt = "You are a helpful assistant. Use markdown for all code blocks."
    input_estimate = estimate_tokens(system_prompt + question)
    
    # 2. Safety Buffer: leave 100 tokens for overhead
    available_tokens = MAX_CONTEXT - input_estimate - 100

    # 3. Dynamic max_tokens: Ask for 1024, or whatever is left, whichever is smaller
    # We ensure it's at least 1 so the API doesn't error out on a 0 or negative value
    final_max_tokens = max(1, min(1024, available_tokens))

    # Optional: If the prompt is too long for the model, warn the user
    if available_tokens < 50:
        return jsonify({"error": "Your question is too long for this model's memory limit."}), 400

    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": question}
        ],
        "max_tokens": final_max_tokens,
        "temperature": 0.7
    }

    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }

    try:
        res = requests.post(f"{API_BASE}/chat/completions", json=payload, headers=headers)
        res.raise_for_status()
        ai_response = res.json()["choices"][0]["message"]["content"]
        return jsonify({"answer": ai_response})

    except Exception as e:
        return jsonify({"error": f"API Error: {str(e)}"}), 500

if __name__ == "__main__":
    app.run(debug=True, port=5001)
