"""
wiki_builder.py — Bir martalik seed script.

Mavjud knowledge_base kolleksiyasini wiki_pages ga kompilyatsiya qiladi.

Jarayon:
  1. knowledge_base dan barcha hujjatlarni oladi
  2. Har biri uchun WikiService.build_page(title, content) chaqiradi
  3. Embedding hosil qiladi va wiki_pages ga saqlaydi

Rate limiting: har so'rov orasida 1 soniya kutish (Gemini API limit).

Ishlatish (lokal yoki Cloud Shell):
  cd bot-bmi
  python scripts/wiki_builder.py

DIQQAT: Bu script Cloud Run da emas, faqat lokal yoki Cloud Shell da ishga tushiriladi.
"""

import asyncio
import sys
import os
import logging

# Proyekt root papkasini path ga qo'shish
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


async def main():
    from loader import get_db
    from services.wiki_service import WikiService

    db = get_db()
    if not db:
        logger.error("Firestore ulanmadi. FIREBASE_CREDENTIALS ni tekshiring.")
        sys.exit(1)

    logger.info("knowledge_base dan hujjatlar o'qilmoqda...")
    docs = list(db.collection("knowledge_base").stream())
    logger.info(f"Topildi: {len(docs)} ta hujjat")

    if not docs:
        logger.warning("knowledge_base bo'sh. Hech narsa yaratilmadi.")
        return

    success = 0
    skipped = 0
    errors = 0

    for i, doc in enumerate(docs, start=1):
        data = doc.to_dict()
        title = data.get("title", "").strip()
        content = data.get("content", data.get("text", "")).strip()

        if not title or not content:
            logger.warning(f"[{i}/{len(docs)}] Hujjat '{doc.id}': title yoki content yo'q — o'tkazildi")
            skipped += 1
            continue

        logger.info(f"[{i}/{len(docs)}] Sahifa yaratilmoqda: \"{title}\"")
        try:
            await WikiService.build_page(title, content)
            success += 1
        except Exception as e:
            logger.error(f"  ✗ Xato: {e}")
            errors += 1

        # Rate limiting — Gemini API limitini hisobga olish
        if i < len(docs):
            await asyncio.sleep(1.0)

    logger.info("=" * 50)
    logger.info(f"Natija: {success} yaratildi | {skipped} o'tkazildi | {errors} xato")
    logger.info("wiki_pages kolleksiyasini Firebase Console da tekshiring.")


if __name__ == "__main__":
    asyncio.run(main())
