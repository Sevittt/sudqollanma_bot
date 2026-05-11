"""
populate_faqs.py
================
Gemini 2.5 Flash yordamida O'zbekiston sud tizimi uchun
professional FAQ ma'lumotlarini generatsiya qilib Firestorega yuklaydi.

Firestore schema (faqs/{faqId}):
  - question: str        — savol matni (O'zbek)
  - answer: str          — to'liq javob (O'zbek)
  - category: str        — 'esud' | 'exat' | 'edo' | 'ms' | 'general' | 'security'
  - systemId: str        — bog'liq tizim ID
  - tags: list[str]      — qidirish teglar
  - order: int           — tartiblash
  - isActive: bool
  - createdAt: timestamp
  - viewCount: int       — statistika uchun
"""

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

# ─── Firebase & Gemini Init ───────────────────────────────────────
# Asosiy papka
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)

# .env dan o'qish
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
GEMINI_API_KEY = ENV.get("GEMINI_API_KEY", os.environ.get("GEMINI_API_KEY", ""))
GEMINI_MODEL = "gemini-2.5-flash"

if not firebase_admin._apps:
    cred = credentials.Certificate(os.path.join(BASE_DIR, "serviceAccountKey.json"))
    firebase_admin.initialize_app(cred)

db = firestore.client()
COLLECTION = "faqs"

# Gemini client
client = genai.Client(api_key=GEMINI_API_KEY)

# ─── FAQ Kategoriyalari va Mavzular ──────────────────────────────

FAQ_TOPICS = {
    "esud": {
        "systemId": "ESUD",
        "displayName": "E-SUD tizimi",
        "description": "O'zbekiston sud tizimining elektron hujjat almashinuvi va ish yuritish platformasi",
        "questions": [
            "E-SUD tizimiga qanday kiriladi va kirish jarayoni qanday?",
            "E-SUD da yangi ish (ariza) qanday ro'yxatga olinadi?",
            "E-SUD da hujjat yuborish va qabul qilish qanday amalga oshiriladi?",
            "E-SUD da parolimni unutdim, qanday tiklayman?",
            "E-SUD tizimida elektron imzo (ERI) qanday ishlatiladi?",
            "E-SUD da ishning holati (statusini) qanday kuzataman?",
            "E-SUD da video-konferentsiya orqali majlis o'tkazish qanday?",
            "E-SUD da xatolik: 'Sessiya muddati tugadi' xabari chiqmoqda, nima qilaman?",
            "E-SUD ga kirish uchun qanday texnik talablar bor (brauzer, internet)?",
            "E-SUD da hujjat skanerlash va yuklash qoidalari qanday?",
            "E-SUD da sudya va kotib huquqlari qanday farq qiladi?",
            "E-SUD orqali qaror va ajrim qanday shakllantiriladi?",
            "E-SUD da statistik hisobotlarni qanday ko'raman?",
            "E-SUD tizimida texnik nosozlik bo'lganda kimga murojaat qilish kerak?",
            "E-SUD da eski ishlarni arxivdan qanday topaman?",
        ],
    },
    "exat": {
        "systemId": "EXAT",
        "displayName": "E-XAT tizimi",
        "description": "O'zbekiston sud xodimlari attestatsiyasi va baholash elektron tizimi",
        "questions": [
            "E-XAT tizimiga qanday ro'yxatdan o'tiladi?",
            "E-XAT da attestatsiya jarayoni qanday ketma-ketlikda o'tadi?",
            "E-XAT da test sinoviga kirish uchun qanday tayyorgarlik ko'rish kerak?",
            "E-XAT da baholash natijalari qachon e'lon qilinadi?",
            "E-XAT natijalariga shikoyat qilish tartibi qanday?",
            "E-XAT da profil ma'lumotlarini qanday yangilayman?",
            "E-XAT da DTS (Davlat Tili Sertifikati) natijalarini qanday ko'raman?",
            "E-XAT parolini unutdim, qanday tiklayman?",
            "E-XAT da attestatsiya sertifikati qanday chiqariladi?",
            "E-XAT tizimi qaysi vaqt oralig'ida ishlaydi?",
        ],
    },
    "edo": {
        "systemId": "EDO",
        "displayName": "EDO (Elektron Hujjat Almashinuvi)",
        "description": "Sud idorasidagi ichki elektron hujjat va buyruqlar almashinuv tizimi",
        "questions": [
            "EDO tizimiga qanday kiriladi?",
            "EDO da kiruvchi xat qanday qayta ishlanadi?",
            "EDO da buyruq va ko'rsatma qanday yuboriladi?",
            "EDO da hujjatga viza (kelishuv) qanday qo'yiladi?",
            "EDO da elektron imzo ishlash uchun nima kerak?",
            "EDO da hujjat yo'qolib qoldi, qanday topaman?",
            "EDO da arxivlangan hujjatlarni qanday ko'raman?",
            "EDO va E-SUD o'rtasidagi farq nima?",
            "EDO da xodim profili qanday sozlanadi?",
            "EDO da guruh xabarlarini qanday yuboraman?",
        ],
    },
    "ms": {
        "systemId": "MS",
        "displayName": "my.sud.uz portali",
        "description": "Fuqarolar uchun sud jarayonlarini online kuzatish va murojaat yuborish portali",
        "questions": [
            "my.sud.uz da ish holatini qanday tekshiraman?",
            "my.sud.uz da murojaat (ariza) yuborish tartibi qanday?",
            "my.sud.uz ga ID karta orqali qanday kiriladi?",
            "my.sud.uz da sud majlisi sanasi va vaqtini qanday bilaman?",
            "my.sud.uz da qarorni qanday yuklab olaman?",
            "my.sud.uz da davlat boji miqdori qanday hisoblanadi?",
            "my.sud.uz da xatolik: 'Ruxsat berilmagan' xabari chiqmoqda",
            "my.sud.uz da advokat sifatida qanday ro'yxatdan o'tiladi?",
            "my.sud.uz portali va E-SUD o'rtasidagi farq nima?",
            "my.sud.uz da bildirishnomalar (notification) qanday yoqiladi?",
        ],
    },
    "security": {
        "systemId": "SECURITY",
        "displayName": "Axborot xavfsizligi",
        "description": "Sud tizimida ma'lumotlar himoyasi va kiberxavfsizlik",
        "questions": [
            "Sud tizimi xodimi sifatida kuchli parol qanday yaratiladi?",
            "Fishing (phishing) hujumidan qanday himoyalanaman?",
            "Ish kompyuterida shaxsiy ma'lumotlarni himoya qilish qoidalari",
            "Elektron imzoni (ERI) yo'qotib qo'ysam nima qilaman?",
            "VPN ishlatish sud tizimida ruxsat etilganmi?",
            "Ichki tizimlar parolini necha oyda bir o'zgartirish kerak?",
            "Shubhali elektron xat (spam/fishing) kelsa nima qilish kerak?",
            "Sud ma'lumotlar bazasiga ruxsatsiz kirish urinishlarini qanday aniqlash mumkin?",
        ],
    },
    "general": {
        "systemId": "GENERAL",
        "displayName": "Umumiy savollar",
        "description": "Sud xodimlari uchun umumiy IT va raqamli kompetensiya savollari",
        "questions": [
            "Sud tizimida qo'llaniladigan asosiy dasturliy ta'minotlar ro'yxati",
            "Yangi xodim sifatida birinchi ish kunida qanday tizimlarni o'rganish kerak?",
            "Sud xodimi uchun tavsiya etilgan kompyuter ko'nikmalari darajasi qanday?",
            "Kompyuter muzlab qoldi yoki ishlamay qoldi, nima qilaman?",
            "Printer bilan muammo bo'lsa (bosib chiqarmasa) nima qilaman?",
            "Internet ulanmayapti, qanday tekshiraman?",
            "Microsoft Office hujjatlarni (Word/Excel) saqlash va format haqida",
            "E-pochta (email) xavfsiz ishlatish qoidalari",
            "Sud tizimida qaysi antivirus dasturlardan foydalaniladi?",
            "Texnik yordam (IT xizmati) bilan qanday bog'laniladi?",
        ],
    },
}

# ─── Gemini FAQ generatsiya funksiyasi ────────────────────────────

def generate_faq_answer(category: str, question: str, system_info: dict) -> dict | None:
    """Gemini orqali savol uchun professional javob generatsiya qilish."""

    prompt = f"""Sen O'zbekiston Sud Tizimining tajribali IT mutaxassisisan.
Quyidagi savol sud xodimlaridan (sudya, kotib, yordamchi xodimlar) kelib tushmoqda.

Tizim: {system_info['displayName']}
Tizim haqida: {system_info['description']}

SAVOL: {question}

Quyidagi formatda JSON qaytargin (faqat JSON, boshqa narsa emas):
{{
  "answer": "To'liq va aniq javob. 3-6 jumladan iborat. Amaliy, qadamba-qadam ko'rsatmalar bo'lsin. O'zbek tilida (lotin yozuv). Texnik atamalar Uzbek ekvivalenti bilan izohlansin.",
  "short_answer": "1 jumlali qisqa javob",
  "tags": ["teg1", "teg2", "teg3", "teg4"],
  "difficulty": "boshlang'ich|o'rta|murakkab",
  "related_steps": ["qadam 1", "qadam 2", "qadam 3"]
}}

MUHIM qoidalar:
- Javob FAQAT O'zbekiston sud tizimi kontekstida bo'lsin
- Aniq, amaliy va tushunarli til ishlatilsin
- Texnik atamalar (ERI, API, VPN) izohlansin
- Javob 150-300 so'z oralig'ida bo'lsin
- tags: kichik harflar, probel bo'lmasin (tire ishlatilsin)"""

    try:
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.3,
                max_output_tokens=4096,
            ),
        )

        text = response.text.strip()

        # Robust JSON extraction: { dan } gacha bracket-counting
        import re as _re

        def extract_json(s: str) -> str:
            """Nested {} ni hisoblab to'g'ri JSON blokni topadi."""
            start = s.find('{')
            if start == -1:
                return s
            depth = 0
            in_string = False
            escape = False
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
                    if ch == '{':
                        depth += 1
                    elif ch == '}':
                        depth -= 1
                        if depth == 0:
                            return s[start:i+1]
            # Agar tugamagan bo'lsa — boshidan oxirigacha
            return s[start:]

        text = extract_json(text)
        data = json.loads(text)
        return data

    except json.JSONDecodeError as e:
        logging.warning(f"JSON parse xatoligi: {e}. Javob: {text[:200]}")
        return None
    except Exception as e:
        logging.error(f"Gemini xatoligi: {e}")
        return None


def safe_doc_id(text: str, prefix: str = "") -> str:
    """Firestore document ID uchun xavfsiz string."""
    import re
    text = text.lower().strip()
    text = re.sub(r"['\u2018\u2019`\u201a\u201b]", "", text)
    text = re.sub(r"[^a-z0-9\u0400-\u04ff\s_-]", "", text, flags=re.UNICODE)
    text = re.sub(r'\s+', '_', text)
    doc_id = f"{prefix}_{text}" if prefix else text
    return doc_id[:80]


# ─── Asosiy funksiya ─────────────────────────────────────────────

def populate_faqs():
    logging.info("🚀 FAQ populatsiyasi boshlandi...")
    logging.info(f"   Model: {GEMINI_MODEL}")
    logging.info(f"   Kategoriyalar: {len(FAQ_TOPICS)}")
    total_questions = sum(len(v['questions']) for v in FAQ_TOPICS.values())
    logging.info(f"   Jami savollar: {total_questions}\n")

    # Mavjud FAQlarni tozalash
    existing = list(db.collection(COLLECTION).stream())
    if existing:
        logging.info(f"⚠ Mavjud {len(existing)} ta FAQ o'chirilmoqda...")
        batch = db.batch()
        for doc in existing:
            batch.delete(doc.reference)
        batch.commit()
        logging.info("✅ Tozalash tugadi.\n")

    grand_total = 0
    global_order = 1

    for cat_key, cat_data in FAQ_TOPICS.items():
        logging.info(f"\n{'─'*50}")
        logging.info(f"📂 Kategoriya: {cat_data['displayName']} ({len(cat_data['questions'])} savol)")
        logging.info(f"{'─'*50}")

        batch = db.batch()
        batch_count = 0
        cat_total = 0

        for q_idx, question in enumerate(cat_data['questions']):
            logging.info(f"  [{q_idx+1}/{len(cat_data['questions'])}] Generatsiya: {question[:60]}...")

            # Gemini dan javob olish (3 marta urinish)
            faq_data = None
            for attempt in range(3):
                faq_data = generate_faq_answer(cat_key, question, cat_data)
                if faq_data:
                    break
                logging.warning(f"    Urinish {attempt+1}/3 muvaffaqiyatsiz, qayta urinilmoqda...")
                time.sleep(2 ** attempt)  # exponential backoff

            if not faq_data:
                logging.error(f"    ❌ Javob olinmadi, o'tkazib yuborildi: {question}")
                continue

            # Firestore hujjat
            doc_id = safe_doc_id(question, prefix=cat_key)
            doc = {
                "question": question,
                "answer": faq_data.get("answer", ""),
                "shortAnswer": faq_data.get("short_answer", ""),
                "category": cat_key,
                "systemId": cat_data["systemId"],
                "tags": faq_data.get("tags", [cat_key]),
                "difficulty": faq_data.get("difficulty", "o'rta"),
                "relatedSteps": faq_data.get("related_steps", []),
                "order": global_order,
                "isActive": True,
                "viewCount": 0,
                "createdAt": firestore.SERVER_TIMESTAMP,
            }

            ref = db.collection(COLLECTION).document(doc_id)
            batch.set(ref, doc)
            batch_count += 1
            cat_total += 1
            grand_total += 1
            global_order += 1

            logging.info(f"    ✅ OK | {faq_data.get('difficulty', '?')} | tegs: {faq_data.get('tags', [])[:3]}")

            # Rate limiting: Gemini bepul kvotada ehtiyotkorlik
            time.sleep(1.2)  # ~50 so'rov/minut chegarasidan pastda

            # Batch commit

            if batch_count >= 20:
                batch.commit()
                logging.info(f"  → Batch commit: {grand_total} ta FAQ yozildi")
                batch = db.batch()
                batch_count = 0

        # Kategoriya tugagan batch
        if batch_count > 0:
            batch.commit()

        logging.info(f"  📊 {cat_data['displayName']}: {cat_total} ta FAQ yuklandi")

    logging.info(f"\n{'='*50}")
    logging.info(f"🎉 JAMI: {grand_total} ta FAQ muvaffaqiyatli Firestorega yuklandi!")
    logging.info(f"{'='*50}")


if __name__ == "__main__":
    populate_faqs()
