"""Gemini FAQ generatsiyasini bitta savol bilan test."""
import sys, json, re
sys.stdout.reconfigure(encoding='utf-8')

def load_env():
    env = {}
    with open('.env', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line and '=' in line and not line.startswith('#'):
                k, _, v = line.partition('=')
                env[k.strip()] = v.strip()
    return env

ENV = load_env()
from google import genai
from google.genai import types

client = genai.Client(api_key=ENV['GEMINI_API_KEY'])

prompt = """Sen O'zbekiston Sud Tizimining tajribali IT mutaxassisisan.
Tizim: E-SUD tizimi

SAVOL: E-SUD tizimiga qanday kiriladi va kirish jarayoni qanday?

Faqat JSON qaytargin:
{
  "answer": "To'liq javob 3-5 jumlada O'zbek tilida",
  "short_answer": "1 jumlali qisqa javob",
  "tags": ["teg1", "teg2", "teg3"],
  "difficulty": "boshlang'ich"
}"""

resp = client.models.generate_content(
    model='gemini-2.5-flash',
    contents=prompt,
    config=types.GenerateContentConfig(
        temperature=0.3,
        max_output_tokens=4096,
    ),
)

text = resp.text.strip()
print("RAW (500 char):", text[:500])
print("---")

# Parse
json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', text, re.DOTALL)
if json_match:
    text = json_match.group(1).strip()
else:
    start = text.find('{')
    end = text.rfind('}')
    if start != -1 and end != -1:
        text = text[start:end+1]

try:
    data = json.loads(text)
    print("JSON parse - OK!")
    print("Answer:", data.get('answer', '')[:150])
    print("Tags:", data.get('tags', []))
    print("Difficulty:", data.get('difficulty'))
except Exception as e:
    print(f"JSON xatoligi: {e}")
    print("Text:", text[:300])
