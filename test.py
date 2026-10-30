import os
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

# Use the same OpenRouter key as the OCR router.
load_dotenv(Path(__file__).resolve().parent / "ocr-router" / ".env", override=True)

api_key = os.getenv("OPENROUTER_API_KEY")

print(f"API key found: {'yes' if api_key else 'NO'}")

if not api_key or not api_key.startswith("sk-or-"):
    print("ERROR: Can OpenRouter key trong D:/finmind/ocr-router/.env")
    print("OPENROUTER_API_KEY=sk-or-v1-xxx...")
    exit(1)

client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=api_key,
)

print("Dang goi qwen/qwen3-vl-235b-a22b-thinking:free ...")
try:
    res = client.chat.completions.create(
        model="recursive/flint-v1.0:free",
        messages=[{"role": "user", "content": "Hello, gioi thieu ngan gon ban la ai?"}],
    )
    print("=== SUCCESS ===")
    print(res.choices[0].message.content)
    if res.usage:
        print(f"\nUsage: {res.usage}")
except Exception as e:
    print(f"ERROR: {e}")
    if getattr(e, "status_code", None) == 404:
        print("Model free nay hien khong co provider tren OpenRouter.")
