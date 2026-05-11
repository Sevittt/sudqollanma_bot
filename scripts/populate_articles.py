import os
import sys
import time
import logging
import json
import firebase_admin
from firebase_admin import credentials, firestore
from google import genai
from google.genai import types

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
sys.stdout.reconfigure(encoding='utf-8')

# ROOT papka: sudqollanma_bot/ (scripts/ dan bir daraja yuqori)
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# .env faylini ROOT dan yuklash
from dotenv import load_dotenv
load_dotenv(os.path.join(ROOT_DIR, ".env"))

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL   = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
FIREBASE_CRED  = os.path.join(ROOT_DIR, "serviceAccountKey.json")
STORAGE_BUCKET = "educationapp-4780a.firebasestorage.app"

# Firebase init
if not firebase_admin._apps:
    cred = credentials.Certificate(FIREBASE_CRED)
    firebase_admin.initialize_app(cred, {'storageBucket': STORAGE_BUCKET})

db         = firestore.client()
client     = genai.Client(api_key=GEMINI_API_KEY)
COLLECTION = "knowledge_base"


# Article categories: 'beginner', 'akt', 'system', 'auth', 'general'
ARTICLE_TOPICS = [
    {
        "category": "system",
        "systemId": "ESUD",
        "title": "E-SUD tizimida raqamli hujjatlar bilan ishlash asoslari",
        "tags": ["esud", "hujjatlar", "asosiy"]
    },
    {
        "category": "system",
        "systemId": "EXAT",
        "title": "E-XAT orqali attestatsiyaga tayyorgarlik va baholash mexanizmlari",
        "tags": ["exat", "attestatsiya", "sinov"]
    },
    {
        "category": "system",
        "systemId": "EDO",
        "title": "Elektron hujjat aylanishi (EDO): viza qo'yish va jo'natish",
        "tags": ["edo", "hujjat_aylanishi"]
    },
    {
        "category": "akt",
        "systemId": "SECURITY",
        "title": "Axborot xavfsizligi va ERI-dan to'g'ri foydalanish qoidalari",
        "tags": ["xavfsizlik", "eri", "parollar"]
    },
    {
        "category": "general",
        "systemId": "IT",
        "title": "Sud xodimlari uchun MS Word va MS Excel darsligi (Masterclass)",
        "tags": ["word", "excel", "qollanma"]
    }
]

def generate_article_content(topic: dict) -> dict:
    prompt = f"""Sen O'zbekiston Sud tizimi malaka oshirish agentligining katta ekspertisan.
Mavzu: {topic['title']}
Ushbu mavzuda professional tarmoq o'quv qo'llanmasini (Knowledge Base Article) yozib ber. 

Quyidagi formatda JSON qaytargin:
{{
  "description": "2-3 jumlalik qisqacha tavsif (anotatsiya)",
  "content": "Juda batafsil, sarlavhalar (#, ##), ro'yxatlar (- ) bilan yozilgan katta MARKDOWN formatidagi matn (kamida 500 so'z). Amaliy maslahatlar va yo'riqnomalar ber."
}}

Faqat JSON formatida qaytar. Boshqa matn qo'shma.
"""
    try:
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.7,
                max_output_tokens=8192,
            ),
        )
        
        text = response.text.strip()
        start = text.find('{')
        end = text.rfind('}')
        if start != -1 and end != -1:
            data = json.loads(text[start:end+1])
            return data
    except Exception as e:
        logging.error(f"Xatolik: {e}")
    return {}

def populate_articles():
    logging.info("🚀 ARTICLES (Knowledge Base) populatsiyasi boshlandi...")
    
    # Faqat art_ prefikslı maqolalarni o'chirish — RAG chunk'lariga tegmaslik uchun
    existing = [d for d in db.collection(COLLECTION).stream() if d.id.startswith('art_')]
    if existing:
        logging.info(f"⚠ Mavjud {len(existing)} ta eski maqolalar o'chirilmoqda...")
        for i in range(0, len(existing), 100):
            chunk = existing[i:i+100]
            batch = db.batch()
            for doc in chunk:
                batch.delete(doc.reference)
            batch.commit()
    
    grand_total = 0
    for idx, topic in enumerate(ARTICLE_TOPICS):
        logging.info(f"  → Maqola generatsiya qilinmoqda: {topic['title']}")
        result = generate_article_content(topic)
        if result and "content" in result:
            doc_id = f"art_{topic['systemId'].lower()}_{idx}"
            doc = {
                "title": topic['title'],
                "description": result.get("description", ""),
                "content": result.get("content", ""),
                "pdfUrl": None,
                "category": topic["category"],
                "systemId": topic["systemId"],
                "tags": topic["tags"],
                "authorId": "admin_bot",
                "authorName": "Sud Qo'llanma Bot",
                "views": 0,
                "helpful": 0,
                "createdAt": firestore.SERVER_TIMESTAMP,
                "updatedAt": firestore.SERVER_TIMESTAMP,
                "isPinned": idx == 0
            }
            db.collection(COLLECTION).document(doc_id).set(doc)
            grand_total += 1
            logging.info(f"    ✅ Maqola saqlandi: {doc_id}")
            time.sleep(3)
        else:
            logging.warning("    ❌ Nimadir xato ketdi, oziqlantirilmadi.")

    logging.info(f"\n🎉 JAMI {grand_total} TA MAQOLA Firestorega yuklandi!")

if __name__ == "__main__":
    populate_articles()
