import google.generativeai as genai
import os
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    print("API Key topilmadi!")
else:
    print(f"API Key: {api_key[:5]}... (mavjud)")
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-flash-latest')
        response = model.generate_content("Hello, world!")
        print("Success! Response:", response.text)
    except Exception as e:
        print("Error:", e)
