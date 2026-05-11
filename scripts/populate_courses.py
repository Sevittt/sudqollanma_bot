"""
populate_courses.py — Sud Qo'llanma Telegram Bot
=================================================
Firestore'ga kurs (courses) ma'lumotlarini yuklash skripti.
final_course_plan.md hujjatiga asoslangan tayyor va aniq kurslar tuzilmasi.

Ishlatish:
    python populate_courses.py             # haqiqiy yuklash
    python populate_courses.py --dry-run   # faqat preview, Firestorega yozmaydi
"""

import sys
import uuid
import datetime
import logging
import argparse
from loader import get_db
from firebase_admin import firestore

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger(__name__)

db = get_db()

def new_id() -> str:
    return uuid.uuid4().hex[:20]

def lesson(title: str, lesson_type: str, ref_id: str, order: int,
           xp_reward: int, is_required: bool, min_pass_score: int | None = None,
           time_codes: list | None = None) -> dict:
    
    source_collection = "video_tutorials"
    if lesson_type == "article":
        source_collection = "knowledge_base"
    elif lesson_type == "quiz":
        source_collection = "quizzes"
        
    doc = {
        "id": new_id(),
        "title": title,
        "type": lesson_type,
        "refId": ref_id,
        "sourceCollection": source_collection,
        "order": order,
        "xpReward": xp_reward,
        "isRequired": is_required,
        "estimatedMinutes": 10 if lesson_type == "video" else 5
    }
    if min_pass_score is not None:
        doc["minPassScore"] = min_pass_score
    if time_codes:
        doc["timeCodes"] = time_codes
    return doc

def module(module_id: str, title: str, description: str, order: int, lessons: list) -> dict:
    return {
        "id": module_id,
        "title": title,
        "description": description,
        "order": order,
        "lessons": lessons,
    }

def build_courses() -> list[dict]:
    now = datetime.datetime.now(tz=datetime.timezone.utc)
    courses = []

    # 1. E-SUD Asosiy Kurs
    courses.append({
        "_doc_id": "course_esud_basics",
        "title": "E-SUD (E-XSUD) Tizimi — Asosiy Kurs",
        "description": "Sud xodimlarini E-XSUD tizimida bosqichma-bosqich ishlashga o'rgatuvchi to'liq kurs",
        "difficulty": "beginner",
        "estimatedHours": 3,
        "hasCertificate": True,
        "targetRole": ["clerk", "secretary", "judge"],
        "tags": ["esud", "e-xsud", "sud", "jinoat"],
        "imageUrl": "assets/images/courses/esud_main.png",
        "isPublished": True,
        "authorId": "system",
        "order": 1,
        "createdAt": now,
        "updatedAt": now,
        "modules": [
            module("esud_m1", "Tizimga Kirish va Sozlamalar", "E-XSUD tizimiga birinchi marta kirish, asosiy interfeys va foydalanuvchi sozlamalari", 1, [
                lesson("Avtomatik taqsimot", "video", "HEESLnZQ7Vo5IDkV0dI4", 1, 10, True),
                lesson("E-XSUD kirish va ishlarni ro'yxatga olish", "video", "AVbWWb1V5exMMMsiCVSY", 2, 10, True),
                lesson("Tizim foydalanuvchilarini ro'yxatdan o'tkazish", "video", "rmVudZ5RBb5IpJjwO0E2", 3, 10, True)
            ]),
            module("esud_m2", "Ishlarni Ro'yxatdan O'tkazish", "Jinoat materiallari, ashyoviy dalillar va murojaatlarni tizimga kiritish", 2, [
                lesson("Ashyoviy dalillar", "video", "tn6mhxEkDH9ZJLRTGX2s", 1, 10, True),
                lesson("Jinoat materiallari", "video", "92ByoRycUrdz45iZkWGn", 2, 10, True),
                lesson("Sudga kelgan murojaatlar ro'yxatdan", "video", "CIvlU7wh9xyZWlPFq9lz", 3, 10, True),
                lesson("Apellyatsiya va kassatsiya shikoyat", "video", "0rSCLAJYwtA1OFXDUI7s", 4, 10, True),
                lesson("Tergov organlari orqali elektron ishlar", "video", "3OTJtDipycEL40tOwAok", 5, 10, False)
            ]),
            module("esud_m3", "Hujjatlar va Ijro", "Sud hujjatlarini sanksiya qilish, publikatsiya va ijro jarayoni", 3, [
                lesson("Sanksiya", "video", "BjdZxeEGgYF512qBsKAE", 1, 10, True),
                lesson("Sud hujjatlarini publikatsiya", "video", "5Kv9yr3G6myNQ6FY8fpP", 2, 10, True),
                lesson("Ijro hujjatlarini yuborish", "video", "IADhqCh7ZBF5li0AZaJh", 3, 10, True),
                lesson("Jinoat ishlarini birlashtirish va ajratish", "video", "5dhoty2ubd9Gh4jyY591", 4, 10, False),
                lesson("Majburiy ijro byurosi — qaytarilgan hujjatlar", "video", "xlV4mo4ET1mWOqZ35hnb", 5, 10, False)
            ]),
            module("esud_m4", "Oliy Sud Bo'limlari", "Oliy sud devonxonasi, nazorat hay'ati va Raёsatda murojaatlar bilan ishlash", 4, [
                lesson("Oliy sud devonxonasi murojaatlar", "video", "0okPzl9b3jfte3k5WN2e", 1, 10, True),
                lesson("Oliy sud murojaatlar boshqarmasi", "video", "Aqy9Cj58vlagsSOmDlEf", 2, 10, True),
                lesson("Nazorat sudlov hay'atiga protestlar", "video", "oF7W8KLqQhQIqGcmdr1k", 3, 10, True),
                lesson("Oliy sud Raёsatiga protestlar", "video", "WzeAnA0CiLxISF8cCECa", 4, 10, False),
                lesson("Ro'yxatlar va hisobotlar avtomatik", "video", "5ynF29eHWdBmxvNYOSGQ", 5, 10, False)
            ]),
            module("esud_m5", "Qo'shimcha Mavzular va Yakuniy Baholash", "Qo'shimcha ish turlari va kurs bo'yicha yakuniy test", 5, [
                lesson("Fuqarolar shaxsiy qabuli", "video", "lU3mIwfoVGu02eYPjcTn", 1, 10, False),
                lesson("Huquqiy targ'ibotlarni ro'yxatdan", "video", "ZaAMawEElTLLNIstULLa", 2, 10, False),
                lesson("Sud amaliyotini umumlashtirish", "video", "q9Pgfy1rFulvxTH55307", 3, 10, False),
                lesson("Qonun hujjatlariga berilgan taklif", "video", "NkmDXnq5ltJHyMZGYxjG", 4, 10, False),
                lesson("Yakuniy Test", "quiz", "quiz_esud_02", 5, 30, True, 70)
            ])
        ]
    })

    # 2. E-SUD Xatoliklarni Bartaraf Etish
    courses.append({
        "_doc_id": "course_esud_troubleshoot",
        "title": "E-SUD — Xatoliklarni Bartaraf Etish",
        "description": "E-XSUD tizimida eng ko'p uchraydigan texnik muammolar va ularni hal qilish yo'llari",
        "difficulty": "intermediate",
        "estimatedHours": 1,
        "hasCertificate": False,
        "targetRole": ["clerk", "it_admin"],
        "tags": ["esud", "xatolik", "troubleshooting", "kesh", "tiket"],
        "imageUrl": "assets/images/courses/esud_troubleshoot.png",
        "isPublished": True,
        "authorId": "system",
        "order": 2,
        "createdAt": now,
        "updatedAt": now,
        "modules": [
            module("trouble_m1", "Kesh va Ulanish Muammolari", "Brauzer keshini tozalash usullarini o'rganish", 1, [
                lesson("Kesh tozalash IP", "video", "kNqhOjlWHjqcNWQLGVVR", 1, 10, True, time_codes=[
                    {"time": 0, "label": "Kirish"},
                    {"time": 90, "label": "Kesh tozalash"},
                    {"time": 300, "label": "IP sozlash"}
                ]),
                lesson("Keshni tozalash (to'liq)", "video", "pzEDlv4OgTwhu3muedYR", 2, 10, True),
                lesson("Exsud xato xabari", "video", "QUVKQK7UOwseQ8Z5kbgW", 3, 10, True)
            ]),
            module("trouble_m2", "Avtomatik Qaytarish Muammolari", "24-soatlik avtomatik qaytarish muammosini hal qilish", 2, [
                lesson("24 avtomatik qaytarish", "video", "MeyqLIqJ6LEsvgtmtTaH", 1, 10, True),
                lesson("24 avtomatik qaytarish (qo'shimcha)", "video", "zTCd5nD2MbhXEnS91B0T", 2, 10, False),
                lesson("Elektron xatoligi ijro hujjatlari", "video", "4mU2LAbJkWpkklNWqdG9", 3, 10, True)
            ]),
            module("trouble_m3", "Tiket Tizimi Orqali Murojaat", "Tiket tizimiga kirish va to'g'ri murojaat yo'llash", 3, [
                lesson("Tiket (qisqa)", "video", "U8fHWC5FDEl18nl4F1Yp", 1, 10, False),
                lesson("Tiket tizimi", "video", "m8tVm60hNC7bIb8pE49r", 2, 10, True),
                lesson("Tiketni ishlatish bo'yicha", "video", "n2Hnnu6AbYoclLv40oIV", 3, 10, True)
            ])
        ]
    })

    # 3. E-XAT va Axborot Xavfsizligi
    courses.append({
        "_doc_id": "course_exat_security",
        "title": "E-XAT va Axborot Xavfsizligi",
        "description": "Elektron xat almashish tizimi, attestatsiyaga tayyorgarlik va raqamli xavfsizlik asoslari",
        "difficulty": "intermediate",
        "estimatedHours": 1.5,
        "hasCertificate": True,
        "targetRole": ["all"],
        "tags": ["exat", "xavfsizlik", "attestatsiya", "security"],
        "imageUrl": "assets/images/courses/exat_security.png",
        "isPublished": True,
        "authorId": "system",
        "order": 3,
        "createdAt": now,
        "updatedAt": now,
        "modules": [
            module("exat_m1", "E-XAT Tizimi va Attestatsiya", "E-XAT tizimi orqali xavfsiz xat almashish va attestatsiyaga tayyorgarlik", 1, [
                lesson("E-XAT orqali attestatsiyaga tayyorgarlik", "article", "art_exat_1", 1, 8, True),
                lesson("E-XAT — Test (Qism 1)", "quiz", "quiz_exat_01", 2, 20, True, 60),
                lesson("E-XAT — Test (Qism 2)", "quiz", "quiz_exat_02", 3, 25, True, 70)
            ]),
            module("exat_m2", "Axborot Xavfsizligi Qoidalari", "Axborot xavfsizligining asosiy tamoyillarini bilish", 2, [
                lesson("Axborot xavfsizligi — Test (Qism 1)", "quiz", "quiz_security_01", 1, 20, True, 60),
                lesson("Axborot xavfsizligi — Test (Qism 2)", "quiz", "quiz_security_02", 2, 20, True, 70)
            ])
        ]
    })

    # 4. IT Ko'nikmalar va EDO
    courses.append({
        "_doc_id": "course_it_edo",
        "title": "IT Ko'nikmalar va EDO Tizimi",
        "description": "MS Office asoslari, umumiy IT savodxonlik va elektron hujjat aylanishi (EDO)",
        "difficulty": "beginner",
        "estimatedHours": 1,
        "hasCertificate": False,
        "targetRole": ["all"],
        "tags": ["it", "edo", "office", "ms-word", "ms-excel"],
        "imageUrl": "assets/images/courses/it_edo.png",
        "isPublished": True,
        "authorId": "system",
        "order": 4,
        "createdAt": now,
        "updatedAt": now,
        "modules": [
            module("it_m1", "MS Office va Umumiy IT Asoslari", "MS Word va Excel asosiy funksiyalarini o'rganish", 1, [
                lesson("MS Word va Excel Masterclass", "article", "art_it_4", 1, 8, True),
                lesson("IT savodxonlik — Test (Qism 1)", "quiz", "quiz_general_01", 2, 20, True, 50),
                lesson("IT savodxonlik — Test (Qism 2)", "quiz", "quiz_general_02", 3, 20, True, 50)
            ]),
            module("it_m2", "EDO va Billing Tizimi", "Elektron to'lov va billing tizimini o'rganish", 2, [
                lesson("Billing elektron to'lov tizimi", "video", "tmIGWqbK5Gtid5vKJZaA", 1, 10, False),
                lesson("EDO mexanizmlari — Test (Qism 1)", "quiz", "quiz_edo_01", 2, 15, True, 60),
                lesson("EDO mexanizmlari — Test (Qism 2)", "quiz", "quiz_edo_02", 3, 15, True, 60)
            ])
        ]
    })
    
    # Fix estimatedHours to estimatedMinutes as expected by Dart
    for c in courses:
        if "estimatedHours" in c:
            c["estimatedMinutes"] = int(float(c.pop("estimatedHours")) * 60)

    return courses


def upload_courses(courses: list, dry_run: bool = False):
    if not courses:
        log.warning("Yuklash uchun kurs yo'q.")
        return

    log.info("Eski kurslar o'chirilmoqda...")
    for doc in db.collection("courses").stream():
        doc.reference.delete()

    log.info(f"{len(courses)} ta kurs yuklanmoqda...")
    for course_data in courses:
        title = course_data.get("title", "?")
        doc_id = course_data.pop("_doc_id")
        
        total_lessons = sum(
            len(m.get("lessons", []))
            for m in course_data.get("modules", [])
        )
        if dry_run:
            log.info(f"  [DRY-RUN] {doc_id} -> {title}  ({total_lessons} dars)")
            for m in course_data.get("modules", []):
                log.info(f"    Modul: {m['title']}")
                for l in m.get("lessons", []):
                    log.info(f"      [{l['type']:7s}] {l['title'][:55]} -> {l['refId']}")
            continue

        try:
            db.collection("courses").document(doc_id).set(course_data)
            log.info(f"  ✅ {title}  (ID: {doc_id}, {total_lessons} dars)")
        except Exception as e:
            log.error(f"  ❌ {title}: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    courses = build_courses()
    upload_courses(courses, dry_run=args.dry_run)
    log.info("✅ Tayyor!")
