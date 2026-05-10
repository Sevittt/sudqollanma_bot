"""
populate_courses.py — Sud Qo'llanma Telegram Bot
=================================================
Firestore'ga kurs (courses) ma'lumotlarini yuklash skripti.

MUHIM: Bu skript AVVAL populate_videos.py, populate_articles.py,
populate_files.py, populate_quizzes.py ishlatilganidan keyin ishlashi kerak,
chunki u shu kolleksiyalardan haqiqiy doc IDlarini oladi.

Ishlatish:
    python populate_courses.py             # haqiqiy yuklash
    python populate_courses.py --dry-run   # faqat preview, Firestorega yozmaydi

Flutter CourseModel bilan to'liq mos tuzilma:
  courses/{courseId}:
    title, description, thumbnailUrl?, targetRole[], difficulty,
    estimatedMinutes, isPublished, authorId, order, hasCertificate,
    certificateTitle?, createdAt, updatedAt,
    modules[]:
      id, title, description, order,
      lessons[]:
        id, title, order, type (video|article|pdf|quiz),
        refId (haqiqiy Firestore doc ID),
        sourceCollection ('video_tutorials'|'knowledge_base'|'resources'|'quizzes'),
        estimatedMinutes?, isRequired
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

# ─── ID generatsiya ───────────────────────────────────────────────────────────

def new_id() -> str:
    return uuid.uuid4().hex[:20]

# ─── Firestore kontent indekslari ─────────────────────────────────────────────

class ContentIndex:
    """
    Barcha kontent kolleksiyalarini bir marta yuklab, tezkor qidirish uchun
    lug'atga yig'adi. Kurs yaratishda haqiqiy Firestore doc IDlarini ishlatadi.
    """
    def __init__(self):
        log.info("Kontent indekslari yuklanmoqda...")
        self.videos   = self._load("video_tutorials")
        self.articles = self._load("knowledge_base")
        self.files    = self._load("resources")
        self.quizzes  = self._load("quizzes")
        log.info(
            f"  📹 Video: {len(self.videos)} | "
            f"📄 Maqola: {len(self.articles)} | "
            f"📎 Fayl: {len(self.files)} | "
            f"❓ Quiz: {len(self.quizzes)}"
        )

    def _load(self, collection: str) -> list[dict]:
        docs = db.collection(collection).stream()
        result = []
        for d in docs:
            item = d.to_dict()
            item["_id"] = d.id
            result.append(item)
        return result

    def find_video(self, system_id: str = None, order: int = None,
                   title_contains: str = None) -> str | None:
        """systemId + order yoki sarlavha bo'yicha video topadi, doc ID qaytaradi."""
        for v in self.videos:
            if system_id and v.get("systemId", "").upper() != system_id.upper():
                continue
            if order is not None and v.get("order") != order:
                continue
            if title_contains and title_contains.lower() not in v.get("title", "").lower():
                continue
            return v["_id"]
        return None

    def find_article(self, system_id: str = None, category: str = None,
                     title_contains: str = None) -> str | None:
        """systemId yoki sarlavha bo'yicha maqola topadi."""
        for a in self.articles:
            if system_id and a.get("systemId", "").upper() != system_id.upper():
                continue
            if category and a.get("category") != category:
                continue
            if title_contains and title_contains.lower() not in a.get("title", "").lower():
                continue
            return a["_id"]
        return None

    def find_file(self, file_type: str = None, title_contains: str = None) -> str | None:
        """type yoki sarlavha bo'yicha PDF fayl topadi."""
        for f in self.files:
            if file_type and f.get("type") != file_type:
                continue
            if title_contains and title_contains.lower() not in f.get("title", "").lower():
                continue
            return f["_id"]
        return None

    def find_quiz(self, category: str = None, title_contains: str = None) -> str | None:
        """category yoki sarlavha bo'yicha quiz topadi."""
        for q in self.quizzes:
            if category and q.get("category") != category:
                continue
            if title_contains and title_contains.lower() not in q.get("title", "").lower():
                continue
            return q["_id"]
        return None

    def list_videos(self, system_id: str) -> list[dict]:
        """Berilgan systemId uchun barcha videolarni order bo'yicha qaytaradi."""
        vids = [v for v in self.videos
                if v.get("systemId", "").upper() == system_id.upper()]
        return sorted(vids, key=lambda v: v.get("order", 99))


# ─── Dars va modul yordamchi funksiyalari ─────────────────────────────────────

_SRC = {
    "video":   "video_tutorials",
    "article": "knowledge_base",
    "pdf":     "resources",
    "quiz":    "quizzes",
}

def lesson(title: str, lesson_type: str, ref_id: str | None, order: int,
           estimated_minutes: int = 10, is_required: bool = True) -> dict | None:
    """
    CourseLessonModel ga mos dict qaytaradi.
    ref_id None bo'lsa — dars yaratilmaydi (None qaytaradi), log chiqaradi.
    """
    if ref_id is None:
        log.warning(f"  ⚠️  refId topilmadi: '{title}' darsi o'tkazib yuborildi.")
        return None
    return {
        "id": new_id(),
        "title": title,
        "type": lesson_type,
        "refId": ref_id,
        "sourceCollection": _SRC.get(lesson_type, "resources"),
        "order": order,
        "estimatedMinutes": estimated_minutes,
        "isRequired": is_required,
    }

def module(title: str, description: str, order: int, lessons: list) -> dict:
    """CourseModuleModel ga mos dict qaytaradi. None darslarni filterlaydi."""
    valid_lessons = [l for l in lessons if l is not None]
    return {
        "id": new_id(),
        "title": title,
        "description": description,
        "order": order,
        "lessons": valid_lessons,
    }

def course_doc(title: str, description: str, target_role: list,
               difficulty: str, estimated_minutes: int, order: int,
               modules: list, author_id: str = "system",
               thumbnail_url: str = None, is_published: bool = True,
               has_certificate: bool = True,
               certificate_title: str = None) -> dict:
    now = datetime.datetime.now(tz=datetime.timezone.utc)
    doc = {
        "title": title,
        "description": description,
        "targetRole": target_role,
        "difficulty": difficulty,
        "estimatedMinutes": estimated_minutes,
        "isPublished": is_published,
        "authorId": author_id,
        "order": order,
        "modules": modules,
        "hasCertificate": has_certificate,
        "createdAt": now,
        "updatedAt": now,
    }
    if thumbnail_url:
        doc["thumbnailUrl"] = thumbnail_url
    if certificate_title:
        doc["certificateTitle"] = certificate_title
    return doc


# ─── Kurslarni qurishda ContentIndex ishlatiladi ──────────────────────────────

def build_courses(idx: ContentIndex) -> list[dict]:
    """
    Barcha kurslarni Firestore'dagi haqiqiy doc IDlari bilan quradi.
    Yangi kurs qo'shmoqchi bo'lsangiz — shu funksiyaga qo'shing.
    """
    courses = []

    # ─────────────────────────────────────────────────────────────────────────
    # 1. E-SUD KURSI
    # ESUD tizimidagi videolarni order bo'yicha avtomatik yuklash
    # ─────────────────────────────────────────────────────────────────────────
    esud_videos = idx.list_videos("ESUD")
    log.info(f"ESUD uchun {len(esud_videos)} ta video topildi.")

    esud_kirish_lessons = []
    for i, v in enumerate(esud_videos[:5], start=1):      # Dastlabki 5 video
        esud_kirish_lessons.append(
            lesson(v["title"], "video", v["_id"], order=i,
                   estimated_minutes=max(5, (v.get("duration") or 300) // 60))
        )

    esud_article_id = idx.find_article(system_id="ESUD", title_contains="raqamli hujjat")
    esud_quiz_id    = idx.find_quiz(category="esud")

    if esud_kirish_lessons or esud_article_id:
        courses.append(course_doc(
            title="E-SUD tizimiga kirish va asosiy amallar",
            description=(
                "Sudyalar va kotiblar uchun E-SUD elektron ish yuritish tizimining "
                "interfeysini o'rganish, hujjatlar bilan ishlash, asosiy amallar."
            ),
            target_role=["judge", "clerk", "ict_specialist"],
            difficulty="beginner",
            estimated_minutes=90,
            order=1,
            has_certificate=True,
            certificate_title="E-SUD tizimini o'zlashtirish",
            modules=[
                module(
                    title="Video darslar: E-SUD",
                    description="Tizimga kirish, navigatsiya va asosiy funksiyalar",
                    order=1,
                    lessons=esud_kirish_lessons,
                ),
                module(
                    title="O'qish materiali",
                    description="E-SUD bo'yicha qo'shimcha nazariy bilimlar",
                    order=2,
                    lessons=[
                        lesson("E-SUD: Raqamli hujjatlar asoslari", "article",
                               esud_article_id, order=1, estimated_minutes=8),
                    ],
                ),
                module(
                    title="Bilimni tekshirish",
                    description="E-SUD bo'yicha test",
                    order=3,
                    lessons=[
                        lesson("E-SUD test", "quiz", esud_quiz_id, order=1,
                               estimated_minutes=10),
                    ],
                ),
            ],
        ))

    # ─────────────────────────────────────────────────────────────────────────
    # 2. AXBOROT XAVFSIZLIGI KURSI
    # ─────────────────────────────────────────────────────────────────────────
    security_article_id = idx.find_article(
        system_id="SECURITY", title_contains="axborot xavfsizligi"
    )
    security_quiz_id    = idx.find_quiz(category="security")
    eimzo_file_id       = idx.find_file(title_contains="e-imzo")

    courses.append(course_doc(
        title="Axborot xavfsizligi asoslari",
        description=(
            "Sud xodimlari uchun shaxsiy ma'lumotlarni himoya qilish, "
            "ERI kalitlari, kiberxavfsizlik asoslari."
        ),
        target_role=["judge", "clerk", "ict_specialist", "admin"],
        difficulty="beginner",
        estimated_minutes=60,
        order=2,
        has_certificate=True,
        certificate_title="Axborot xavfsizligi asoslari",
        modules=[
            module(
                title="Nazariy asos",
                description="Xavfsizlik qoidalari va ERI kalitlari",
                order=1,
                lessons=[
                    lesson("Axborot xavfsizligi: asosiy tushunchalar", "article",
                           security_article_id, order=1, estimated_minutes=10),
                    lesson("E-IMZO qo'llanmasi (PDF)", "pdf",
                           eimzo_file_id, order=2, estimated_minutes=15),
                ],
            ),
            module(
                title="Bilimni tekshirish",
                description="Xavfsizlik bo'yicha test",
                order=2,
                lessons=[
                    lesson("Axborot xavfsizligi testi", "quiz",
                           security_quiz_id, order=1, estimated_minutes=10),
                ],
            ),
        ],
    ))

    # ─────────────────────────────────────────────────────────────────────────
    # 3. E-XAT KURSI
    # ─────────────────────────────────────────────────────────────────────────
    exat_article_id = idx.find_article(
        system_id="EXAT", title_contains="attestatsiya"
    )
    exat_quiz_id    = idx.find_quiz(category="exat")

    courses.append(course_doc(
        title="E-XAT: Attestatsiya va elektron xat",
        description=(
            "E-XAT tizimi: attestatsiyaga tayyorgarlik, kiruvchi va "
            "chiquvchi xatlar bilan ishlash yo'riqnomasi."
        ),
        target_role=["clerk", "admin", "judge"],
        difficulty="intermediate",
        estimated_minutes=80,
        order=3,
        has_certificate=True,
        certificate_title="E-XAT tizimini o'zlashtirish",
        modules=[
            module(
                title="E-XAT asoslari",
                description="Attestatsiya va xat almashinuv tizimiga kirish",
                order=1,
                lessons=[
                    lesson("E-XAT: Attestatsiyaga tayyorgarlik", "article",
                           exat_article_id, order=1, estimated_minutes=8),
                ],
            ),
            module(
                title="Bilimni tekshirish",
                description="E-XAT bo'yicha test",
                order=2,
                lessons=[
                    lesson("E-XAT testi", "quiz", exat_quiz_id, order=1,
                           estimated_minutes=10),
                ],
            ),
        ],
    ))

    # ─────────────────────────────────────────────────────────────────────────
    # 4. EDO KURSI
    # ─────────────────────────────────────────────────────────────────────────
    edo_article_id = idx.find_article(
        system_id="EDO", title_contains="elektron hujjat aylanishi"
    )
    edo_quiz_id    = idx.find_quiz(category="edo")
    edo_file_id    = idx.find_file(title_contains="imzolangan hujjat")

    courses.append(course_doc(
        title="EDO: Elektron hujjat aylanishi",
        description=(
            "Buyruqlar, ma'lumotnomalar, hujjatlarni imzolash va "
            "idoralararo yuborish — EDO tizimida ishlash to'liq kursi."
        ),
        target_role=["clerk", "admin"],
        difficulty="intermediate",
        estimated_minutes=100,
        order=4,
        has_certificate=True,
        certificate_title="EDO tizimini o'zlashtirish",
        modules=[
            module(
                title="EDO asoslari",
                description="Hujjat aylanishi va imzolash jarayoni",
                order=1,
                lessons=[
                    lesson("EDO: Hujjat aylanishi asoslari", "article",
                           edo_article_id, order=1, estimated_minutes=10),
                    lesson("Imzolangan hujjatlarni yuborish (PDF)", "pdf",
                           edo_file_id, order=2, estimated_minutes=10),
                ],
            ),
            module(
                title="Bilimni tekshirish",
                description="EDO bo'yicha test",
                order=2,
                lessons=[
                    lesson("EDO testi", "quiz", edo_quiz_id, order=1,
                           estimated_minutes=10),
                ],
            ),
        ],
    ))

    # ─────────────────────────────────────────────────────────────────────────
    # My.sud video kursi — MS tizimidagi barcha videolar
    # ─────────────────────────────────────────────────────────────────────────
    ms_videos = idx.list_videos("MS")
    log.info(f"MS (My.sud) uchun {len(ms_videos)} ta video topildi.")

    ms_lessons = []
    for i, v in enumerate(ms_videos, start=1):
        ms_lessons.append(
            lesson(v["title"], "video", v["_id"], order=i,
                   estimated_minutes=max(5, (v.get("duration") or 300) // 60))
        )

    if ms_lessons:
        courses.append(course_doc(
            title="My.sud tizimi: to'liq video kurs",
            description=(
                "My.sud axborot tizimida ishlash bo'yicha barcha video darslar: "
                "ro'yxatdan o'tish, ishni yuritish, hisobotlar."
            ),
            target_role=["judge", "clerk"],
            difficulty="beginner",
            estimated_minutes=len(ms_lessons) * 8,
            order=5,
            has_certificate=True,
            certificate_title="My.sud tizimini o'zlashtirish",
            modules=[
                module(
                    title="My.sud video darslar",
                    description="Barcha video yo'riqnomalar ketma-ket",
                    order=1,
                    lessons=ms_lessons,
                ),
            ],
        ))

    log.info(f"Jami {len(courses)} ta kurs qurildi.")
    return courses


# ─── Firestore ga yuklash ─────────────────────────────────────────────────────

def upload_courses(courses: list, dry_run: bool = False):
    if not courses:
        log.warning("Yuklash uchun kurs yo'q.")
        return

    # Eskisini o'chirish
    log.info("Eski kurslar o'chirilmoqda...")
    for doc in db.collection("courses").stream():
        doc.reference.delete()

    log.info(f"{len(courses)} ta kurs yuklanmoqda...")
    for course_data in courses:
        title = course_data.get("title", "?")
        total_lessons = sum(
            len(m.get("lessons", []))
            for m in course_data.get("modules", [])
        )
        if dry_run:
            log.info(f"  [DRY-RUN] {title}  ({total_lessons} dars)")
            for m in course_data.get("modules", []):
                log.info(f"    Modul: {m['title']}")
                for l in m.get("lessons", []):
                    log.info(f"      [{l['type']:7s}] {l['title'][:55]} → {l['refId'][:16]}...")
            continue

        try:
            _, ref = db.collection("courses").add(course_data)
            log.info(f"  ✅ {title}  (ID: {ref.id}, {total_lessons} dars)")
        except Exception as e:
            log.error(f"  ❌ {title}: {e}")


# ─── CLI ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Firestore'ga kurslar yuklash")
    parser.add_argument("--dry-run", action="store_true",
                        help="Firestorega yozmasdan preview ko'rsat")
    args = parser.parse_args()

    idx = ContentIndex()
    courses = build_courses(idx)

    if not courses:
        log.error("Hech qanday kurs qurilmadi. Avval kontent skriptlarini ishlatib ko'ring.")
        sys.exit(1)

    upload_courses(courses, dry_run=args.dry_run)
    log.info("✅ Tayyor!")
