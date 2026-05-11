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

# ─── Firebase & Gemini Init ───────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def load_env():
    env_path = os.path.join(BASE_DIR, ".env")
    env = {}
    if os.path.exists(env_path):
        with open(env_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and "=" in line and not line.startswith("#"):
                    key, _, val = line.partition("=")
                    env[key.strip()] = val.strip()
    return env

ENV = load_env()
GEMINI_API_KEY = ENV.get("GEMINI_API_KEY", "")
GEMINI_MODEL = "gemini-2.5-flash"

if not firebase_admin._apps:
    cred = credentials.Certificate(os.path.join(BASE_DIR, "serviceAccountKey.json"))
    firebase_admin.initialize_app(cred)

db = firestore.client()
COLLECTION = "quizzes"
client = genai.Client(api_key=GEMINI_API_KEY)

QUIZ_CATEGORIES = {
    "esud": {
        "title": "E-SUD asosiy tushunchalari",
        "description": "E-SUD dasturida ishlash bo'yicha bazaviy bilimlarni sinovchi test.",
        "quiz_count": 2,
        "questions_per_quiz": 10
    },
    "exat": {
        "title": "E-XAT tizimi va xavfsiz xat almashinuvi",
        "description": "Elektron xat almashinuv tizimi qoidalari, himoyalangan aloqa shartlari.",
        "quiz_count": 2,
        "questions_per_quiz": 10
    },
    "edo": {
        "title": "EDO Tizimi ishlash mexanizmlari",
        "description": "Buyruqlar, ma'lumotnomalar va idoralararo hujjat almashish.",
        "quiz_count": 2,
        "questions_per_quiz": 10
    },
    "security": {
        "title": "Axborot xavfsizligi qoidalari",
        "description": "Sud xodimlarining raqamli xavfsizlik va ERI kalitlari bo'yicha majburiyatlari.",
        "quiz_count": 2,
        "questions_per_quiz": 10
    },
    "general": {
        "title": "IT savodxonlik",
        "description": "Kompyuter va maxsus davlat dasturlaridan umumiy foydalanish testi.",
        "quiz_count": 2,
        "questions_per_quiz": 10
    }
}

def generate_quiz_questions(category: str, title: str, desc: str, amount: int) -> list:
    prompt = f"""Sen O'zbekiston Oliy Sudi qoshidagi o'quv markazi IT ekspertisan.
Sud xodimlari tayyorgarligini tekshiruvchi TEST bazasini yozishing kerak.
Mavzu: {title}
Tavsif: {desc}
Kerakli savollar soni: {amount} ta

Quyidagi JSON ro'yxatini (array) qaytargin (faqat JSON array, markdown formatisiz!):
[
  {{
    "questionText": "Savol matni (O'zbek tilida)",
    "questionType": "multipleChoice",
    "options": [
      "A xato",
      "B xato",
      "C xato",
      "D to'g'ri (Variant matnlari uzilgan harflarsiz, ya'ni aniq faktlar bo'lsin)"
    ],
    "correctAnswer": "D to'g'ri"
  }}
]

MUHIM:
- "correctAnswer" maydoni to'liq "options" dagi kabi bir xil matn bo'lishi shart! Indeks EMAS.
- options da harf qo'ymasdan faqat ma'lumotni o'zini yozgin (masalan: "Faqat rahbar qila oladi", "Hamma qila oladi", ...)
"""

    try:
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.3,
                max_output_tokens=8192,
            ),
        )

        text = response.text.strip()
        def extract_json_array(s: str) -> str:
            start = s.find('[')
            depth = 0
            in_string = False
            escape = False
            if start == -1: return s
            for i, ch in enumerate(s[start:], start):
                if escape:
                    escape = False
                    continue
                if ch == '\\' and in_string:
                    escape = True
                    continue
                if ch == '"' and not escape:
                    in_string = not in_string
                    continue
                if not in_string:
                    if ch == '[': depth += 1
                    elif ch == ']':
                        depth -= 1
                        if depth == 0: return s[start:i+1]
            return s[start:]

        extr_str = extract_json_array(text)
        if not extr_str.startswith('['): return []
        data = json.loads(extr_str)
        return data if isinstance(data, list) else []

    except Exception as e:
        logging.error(f"Gemini API xatoligi: {e}")
        return []

def safe_doc_id(prefix: str, idx: int) -> str:
    return f"quiz_{prefix}_{idx:02d}"

def populate_quizzes():
    logging.info("🚀 QUIZ populatsiyasi boshlandi (Subcollection orqali)...")
    
    # Eskilarni tozalash (jumladan subcollectionlarni) uchun avvalgi hujjatlarni o'chirish.
    # Firestore admin SDK da collection ichidagi hamma narsani tez o'chirish yo'q, 
    # Shuning uchun root docs ni o'chiramiz. Katta scale dagi app emas bu.
    existing = list(db.collection(COLLECTION).stream())
    if existing:
        logging.info(f"⚠ Mavjud {len(existing)} ta eski quiz hujjatlari o'chirilmoqda...")
        for doc in existing:
            # Delete questions subcollection first
            sub_docs = list(doc.reference.collection('questions').stream())
            if sub_docs:
                batch = db.batch()
                for sd in sub_docs:
                    batch.delete(sd.reference)
                batch.commit()
            doc.reference.delete()
        logging.info("✅ Tozalash tugadi.\n")

    grand_total = 0
    total_questions = 0
    
    for cat_key, cat_data in QUIZ_CATEGORIES.items():
        logging.info(f"📂 Kategoriya: {cat_data['title']}")
        q_count = cat_data["quiz_count"]
        amt = cat_data["questions_per_quiz"]
        
        for q_idx in range(1, q_count + 1):
            logging.info(f"  → Quiz #{q_idx} uchun {amt} ta savol generatsiya qilinmoqda...")
            questions_data = generate_quiz_questions(cat_key, cat_data["title"], cat_data["description"], amt)
            
            if not questions_data or len(questions_data) < 5:
                logging.warning("    ❌ Sifatli format topilmadi. O'tkazib yuborilmoqda...")
                continue
                
            quiz_doc_id = safe_doc_id(cat_key, q_idx)
            quiz_doc = {
                "id": quiz_doc_id,
                "title": f"[{cat_key.upper()}] {cat_data['title']} (Qism {q_idx})",
                "description": cat_data['description'],
                "resourceId": f"res_{cat_key}",
                "category": cat_key,
                "createdAt": firestore.SERVER_TIMESTAMP
            }
            
            # 1) Avval Quiz parent doc yaratamiz
            db.collection(COLLECTION).document(quiz_doc_id).set(quiz_doc)
            
            # 2) Keyin questions subcollection ga xar bir savolni alohida DOC sifatida qoshamiz
            batch = db.batch()
            for i, q in enumerate(questions_data):
                q_id = f"q_{i+1:04d}" # Lexicographical sorting uchun id format
                question_ref = db.collection(COLLECTION).document(quiz_doc_id).collection('questions').document(q_id)
                q_data = {
                    "questionText": q.get("questionText", f"Savol {i+1}"),
                    "questionType": "multipleChoice",
                    "options": q.get("options", []),
                    "correctAnswer": q.get("correctAnswer", "")
                }
                batch.set(question_ref, q_data)
                
            batch.commit()
            
            grand_total += 1
            total_questions += len(questions_data)
            logging.info(f"    ✅ Quiz yuklandi: {quiz_doc_id} va uning Ichki 'questions' subcollectionida {len(questions_data)} ta savol.")
            time.sleep(3)
            
    logging.info(f"\n🎉 JAMI: {grand_total} ta QUIZ va umumiy {total_questions} ta SAVOL Firestorega yuklandi!")

if __name__ == "__main__":
    populate_quizzes()
