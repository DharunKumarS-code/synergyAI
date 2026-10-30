import os

from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    raise ValueError(
        "GEMINI_API_KEY was not found. Check your .env file."
    )

client = genai.Client(
    api_key=api_key,
    http_options=types.HttpOptions(timeout=60000),
)

try:
    print("Testing Gemini with a minimal request...")

    response = client.models.generate_content(
        model="gemini-3.5-flash-lite",
        contents="Reply with OK.",
        config=types.GenerateContentConfig(
            max_output_tokens=20,
        ),
    )

    print("\nGemini connection successful!")
    print("Response:", response.text)

except Exception as error:
    print("\nGemini request failed.")
    print("Error type:", type(error).__name__)
    print("Error details:", str(error)[:2000])

finally:
    client.close()

