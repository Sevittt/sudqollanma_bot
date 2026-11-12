"""
wiki_linter.py — Davriy wiki linting operatsiyasi skripti.

Vazifasi:
  1. wiki_pages kolleksiyasidagi barcha sahifalarni o'qiydi.
  2. Har bir sahifaning review_score ballini va eskirganligini (30 kundan oshganligini) tekshiradi.
  3. Talabga javob bermaydigan (eskirgan yoki past balli) sahifalarni yangi RAG kontekstlari yordamida qayta yaratadi.
  4. Natijalarni wiki_log kolleksiyasiga yozadi.

Tizimda foydalanish:
  Lokal yoki Cloud Shell:
    python scripts/wiki_linter.py
"""

import asyncio
import sys
import os
import logging
from datetime import datetime, timedelta, timezone

# Root papkani path ga qo'shish
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("WIKI_LINTER")


async def run_lint() -> dict:
    """Wiki sahifalarini to'liq linting tekshiruvidan o'tkazadi va yangilaydi."""
    # ── Muhit o'zgaruvchilarini tekshirish (Sokin nosozliklarni oldini olish) ───
    import config
    missing_envs = []
    if not config.BOT_TOKEN:
        missing_envs.append("BOT_TOKEN")
    if not config.GEMINI_API_KEY:
        missing_envs.append("GEMINI_API_KEY")
    if not config.FIREBASE_CREDENTIALS and not os.getenv("GOOGLE_APPLICATION_CREDENTIALS"):
        if not os.path.exists("serviceAccountKey.json"):
            missing_envs.append("FIREBASE_CREDENTIALS / serviceAccountKey.json")

    if missing_envs:
        error_msg = f"LINT KATTA XATO: Quyidagi muhit sozlamalari (env) etishmayapti: {', '.join(missing_envs)}. Linter ishga tushmadi!"
        logger.error(error_msg)
        raise RuntimeError(error_msg)

    from loader import get_db
    from services.wiki_service import WikiService, WIKI_COLLECTION, WIKI_LOG_COLLECTION
    from services.ai_service import AIService
    # pyrefly: ignore [missing-import]
    from google.cloud.firestore_v1 import SERVER_TIMESTAMP

    db = get_db()
    if not db:
        logger.error("Firestore ulanmadi.")
        raise RuntimeError("Firestore disconnected")

    logger.info("Wiki Linter ishga tushdi...")
    pages = list(db.collection(WIKI_COLLECTION).stream())
    logger.info(f"Tekshirilayotgan sahifalar soni: {len(pages)}")

    results = {
        "checked": len(pages),
        "refreshed": 0,
        "errors": 0,
        "details": []
    }

    now = datetime.now(timezone.utc)
    expiry_limit = now - timedelta(days=30)

    for i, doc in enumerate(pages, start=1):
        data = doc.to_dict()
        slug = doc.id
        title = data.get("title", slug)
        source_query = data.get("source_query", title)
        review_score = data.get("review_score", 0.0)
        updated_at = data.get("updated_at")

        # 30 kunlik muddatni tekshirish
        is_expired = False
        if updated_at:
            # Firestore timestamp ni datetime ga o'tkazish
            if hasattr(updated_at, "to_datetime"):
                updated_dt = updated_at.to_datetime()
            else:
                updated_dt = updated_at
                
            # Timezone awareness ta'minlash
            if updated_dt.tzinfo is None:
                updated_dt = updated_dt.replace(tzinfo=timezone.utc)
                
            if updated_dt < expiry_limit:
                is_expired = True

        # Refresh kerakligini aniqlash
        needs_refresh = False
        reason = ""
        
        if review_score < 0.8:
            needs_refresh = True
            reason = f"Past review balli: {review_score:.2f} < 0.80"
        elif is_expired:
            needs_refresh = True
            reason = "Sahifa eskirgan (30 kundan oshgan)"

        if needs_refresh:
            logger.info(f"[{i}/{len(pages)}] Refreshing: '{slug}' - Sabab: {reason}")
            try:
                # 1. Yangi RAG kontekstini olish (rag_chunks Vector Search fallback)
                rag_context = await AIService.get_relevant_context(source_query, limit=3)
                
                # 2. Sahifani qayta yaratish (Creator + Reviewer zanjiri)
                await WikiService.build_page(source_query, rag_context)
                
                results["refreshed"] += 1
                results["details"].append({
                    "slug": slug,
                    "status": "refreshed",
                    "reason": reason
                })
            except Exception as e:
                logger.error(f"Sahifani yangilashda xatolik ({slug}): {e}")
                results["errors"] += 1
                results["details"].append({
                    "slug": slug,
                    "status": "error",
                    "error": str(e)
                })
        else:
            logger.info(f"[{i}/{len(pages)}] OK: '{slug}' (Score: {review_score:.2f})")

    # Lint natijalarini zurnalga yozish
    try:
        log_ref = db.collection(WIKI_LOG_COLLECTION).document()
        log_ref.set({
            "timestamp": SERVER_TIMESTAMP,
            "action": "LINT_REFRESH",
            "reviewer_feedback": f"Linter finished. Checked: {results['checked']}, Refreshed: {results['refreshed']}, Errors: {results['errors']}",
            "approved": True
        })
    except Exception as log_err:
        logger.warning(f"Linter log yozishda xatolik: {log_err}")

    logger.info(f"Linter yakunlandi. Jami: {results['checked']} tekshirildi, {results['refreshed']} yangilandi.")
    return results


if __name__ == "__main__":
    try:
        results = asyncio.run(run_lint())
        if results.get("errors", 0) > 0:
            logger.error(f"Linter ba'zi sahifalar yangilanishida xatolikka uchradi (errors: {results['errors']}). Exit 1.")
            sys.exit(1)
        sys.exit(0)
    except Exception as e:
        logger.critical(f"Linter halokatli xato tufayli to'xtadi: {e}")
        sys.exit(1)
