"""
migrate_to_courses.py — Sud Qo'llanma Telegram Bot
Mavjud resources, knowledge_base va faqs ma'lumotlarini kurslar (courses) tarkibiga o'tkazish skripti.
"""

import uuid
import datetime
import logging
from loader import get_db
from firebase_admin import firestore

# Setup logging
logging.basicConfig(level=logging.INFO)
db = get_db()

# Kategoriya va kurs nomlari mappingi
MAPPING = {
    "esud": {
        "title": "E-SUD tizimiga kirish va asosiy amallar",
        "category_name": "🖥 E-SUD tizimi"
    },
    "exat": {
        "title": "E-XAT: Elektron hujjat muomalasi",
        "category_name": "📧 E-XAT tizimi"
    },
    "axborot_xavfsizligi": {
        "title": "Axborot xavfsizligi asoslari",
        "category_name": "🛡 Axborot xavfsizligi"
    },
    "edo": {
        "title": "EDO — Elektron hujjat almashish",
        "category_name": "📤 EDO tizimi"
    },
    "mysud": {
        "title": "MY.SUD.UZ portali bilan ishlash",
        "category_name": "🌐 MY.SUD.UZ"
    }
}

def new_id() -> str:
    return uuid.uuid4().hex[:20]

async def migrate():
    if not db:
        logging.error("Firestore initialization failed.")
        return

    logging.info("Starting migration to unified courses...")

    # 1. Kurslarni olish yoki yaratish uchun tayyorlash
    courses_ref = db.collection('courses')
    existing_courses_stream = courses_ref.stream()
    courses_map = {} # title -> doc_data (with id)

    for doc in existing_courses_stream:
        data = doc.to_dict()
        data['id'] = doc.id
        courses_map[data['title']] = data

    # 2. Mavjud ma'lumotlarni yig'ish
    resources = list(db.collection('resources').stream())
    articles = list(db.collection('knowledge_base').stream())
    faqs = list(db.collection('faqs').stream())

    logging.info(f"Found {len(resources)} resources, {len(articles)} articles, {len(faqs)} FAQs.")

    # 3. Kurslarni to'ldirish
    for type_key, info in MAPPING.items():
        course_title = info['title']
        
        # Kursni topish yoki yangi yaratish
        if course_title in courses_map:
            course_data = courses_map[course_title]
            logging.info(f"Updating existing course: {course_title}")
        else:
            logging.info(f"Creating new course: {course_title}")
            course_data = {
                "title": course_title,
                "description": f"{info['category_name']} bo'yicha barcha materiallar to'plami.",
                "targetRole": ["judge", "clerk", "ict_specialist"],
                "difficulty": "beginner",
                "estimatedMinutes": 60,
                "isPublished": True,
                "authorId": "system",
                "order": 1,
                "modules": [],
                "createdAt": firestore.SERVER_TIMESTAMP,
                "updatedAt": firestore.SERVER_TIMESTAMP,
            }
        
        # Modullarni tayyorlash
        modules = {m['title']: m for m in course_data.get('modules', [])}
        
        def get_or_create_module(title):
            if title not in modules:
                modules[title] = {
                    "id": new_id(),
                    "title": title,
                    "description": f"{course_title} bo'yicha {title.lower()}.",
                    "order": len(modules) + 1,
                    "lessons": []
                }
            return modules[title]

        # A. Resurslar (PDFlar)
        relevant_resources = [r for r in resources if r.to_dict().get('type') == type_key]
        if relevant_resources:
            mod = get_or_create_module("📚 Qo'llanmalar va fayllar")
            existing_ref_ids = [l.get('refId') for l in mod['lessons']]
            for res_doc in relevant_resources:
                res_data = res_doc.to_dict()
                if res_doc.id not in existing_ref_ids:
                    mod['lessons'].append({
                        "id": new_id(),
                        "title": res_data.get('title', 'Nomsiz resurs'),
                        "type": "pdf",
                        "refId": res_doc.id,
                        "order": len(mod['lessons']) + 1,
                        "estimatedMinutes": 5,
                        "isRequired": True
                    })

        # B. Maqolalar
        relevant_articles = [a for a in articles if a.to_dict().get('category') == type_key]
        if relevant_articles:
            mod = get_or_create_module("📖 Bilimlar bazasi (Maqolalar)")
            existing_ref_ids = [l.get('refId') for l in mod['lessons']]
            for art_doc in relevant_articles:
                art_data = art_doc.to_dict()
                if art_doc.id not in existing_ref_ids:
                    mod['lessons'].append({
                        "id": new_id(),
                        "title": art_data.get('title', 'Nomsiz maqola'),
                        "type": "article",
                        "refId": art_doc.id,
                        "order": len(mod['lessons']) + 1,
                        "estimatedMinutes": 10,
                        "isRequired": True
                    })

        # C. FAQs
        relevant_faqs = [f for f in faqs if f.to_dict().get('category') == type_key]
        if relevant_faqs:
            mod = get_or_create_module("❓ FAQ (Savol-javoblar)")
            existing_ref_ids = [l.get('refId') for l in mod['lessons']]
            for faq_doc in relevant_faqs:
                faq_data = faq_doc.to_dict()
                if faq_doc.id not in existing_ref_ids:
                    mod['lessons'].append({
                        "id": new_id(),
                        "title": faq_data.get('question', 'Nomsiz savol'),
                        "type": "article", # FAQlar ham article kabi ko'rsatiladi
                        "refId": faq_doc.id,
                        "order": len(mod['lessons']) + 1,
                        "estimatedMinutes": 3,
                        "isRequired": False
                    })

        # Kurs ma'lumotlarini yangilash
        course_data['modules'] = list(modules.values())
        course_data['updatedAt'] = firestore.SERVER_TIMESTAMP
        
        # Firestore'ga saqlash
        if 'id' in course_data:
            course_id = course_data.pop('id')
            courses_ref.document(course_id).set(course_data)
            logging.info(f"✅ Updated course: {course_title}")
        else:
            _, doc_ref = courses_ref.add(course_data)
            logging.info(f"✅ Created course: {course_title} (ID: {doc_ref.id})")

    logging.info("Migration completed successfully!")

if __name__ == "__main__":
    import asyncio
    asyncio.run(migrate())
