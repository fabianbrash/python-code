import openai
import os
from yaspin import yaspin

client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY", "sk-your-api-key-here"))

def ask_chatgpt(prompt: str, model="gpt-4o"):
    with yaspin(text="Talking to ChatGPT...", color="cyan") as spinner:
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": "You are a helpful assistant."},
                    {"role": "user", "content": prompt}
                ]
            )
            spinner.ok("✅ ")
            return response.choices[0].message.content.strip()
        except Exception as e:
            spinner.fail("💥 ")
            return f"Error: {str(e)}"

if __name__ == "__main__":
    fixed_prompt = "Tell me a story about a robot who learns to dream."
    reply = ask_chatgpt(fixed_prompt)
    print("\nChatGPT says:\n", reply)
