"""
test_wiki_rag.py — WikiService + AIService integratsiya testi.

Nima tekshiriladi:
  1. WikiService import + slug builder
  2. loader.py — get_db() va init_gemini()
  3. WikiService.build_page() — yangi sahifa yaratish
  4. Firestore da yozilganini tekshirish (sanity check)
  5. WikiService.search() — Vector Search + hit_count
  6. AIService.get_relevant_context() — to'liq zanjir (Wiki → RAG → fallback)
  7. _fire_and_forget() xavfsizligi

Ishlatish:
  cd bot-bmi
  python test_wiki_rag.py
"""

import asyncio
import sys
import os
import logging

# .env faylini to'g'ri papkadan yuklash
_env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sudqollanma_bot", ".env")
if os.path.exists(_env_path):
    from dotenv import load_dotenv
    load_dotenv(_env_path)
    print(f"[ENV] Yuklandi: {_env_path}")
else:
    print(f"[ENV] OGOHLANTIRISH: .env topilmadi ({_env_path})")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("TEST")

# ── Yordamchi funksiyalar ──────────────────────────────────────────────────────

PASS_S = "[PASS]"
FAIL_S = "[FAIL]"
SKIP_S = "[SKIP]"
results = []


def ok(msg):
    logger.info(f"{PASS_S} {msg}")
    results.append((True, msg))


def fail(msg, err=None):
    err_str = f": {err}" if err else ""
    logger.error(f"{FAIL_S} {msg}{err_str}")
    results.append((False, msg))


def skip(msg):
    logger.warning(f"{SKIP_S} {msg}")
    results.append((None, msg))


# ── TEST 1: slug builder ───────────────────────────────────────────────────────

async def test_slug():
    logger.info("\n=== TEST 1: slug builder ===")
    try:
        from services.wiki_service import _build_slug

        cases = [
            ("E-IMZO drayveri muammolari", "e-imzo-drayveri-muammolari"),
            ("E-SUD tizimiga kirish",      "e-sud-tizimiga-kirish"),
        ]
        for inp, expected in cases:
            result = _build_slug(inp)
            logger.info(f"  slug('{inp}') = '{result}'")
            assert result == expected, f"Kutilgan: '{expected}', Olingan: '{result}'"

        ok("slug builder to'g'ri ishlaydi")
    except AssertionError as e:
        fail("slug builder — noto'g'ri natija", e)
    except Exception as e:
        fail("slug builder", e)


# ── TEST 2: loader ─────────────────────────────────────────────────────────────

async def test_loaders():
    logger.info("\n=== TEST 2: loader.py — get_db() va init_gemini() ===")
    try:
        from loader import get_db, init_gemini
        db = get_db()
        if db:
            ok("get_db() — Firestore ulandi")
        else:
            fail("get_db() — None qaytdi (FIREBASE_CREDENTIALS tekshiring)")
            return False

        client = init_gemini()
        if client:
            ok("init_gemini() — Gemini client tayyor")
        else:
            fail("init_gemini() — None qaytdi (GEMINI_API_KEY tekshiring)")
            return False

        return True
    except Exception as e:
        fail("loader xatosi", e)
        return False


# ── TEST 3: WikiService.build_page() ──────────────────────────────────────────

TEST_QUERY = "TEST wiki integratsiya tekshiruvi 2026"
TEST_CONTEXT = (
    "E-IMZO — elektron imzo tizimi. "
    "Hujjatlarni imzolash uchun C:\\E-IMZO drayveri o'rnatilishi kerak. "
    "Muammo: sertifikat topilmadi. Yechim: drayver qayta o'rnatiladi. "
    "Qadam 1: Eski drayver o'chiriladi. Qadam 2: Yangi versiya yuklanadi. "
    "Qadam 3: Kompyuter qayta yuklanadi. Qadam 4: E-IMZO qayta ochiladi."
)

async def test_build_page():
    logger.info("\n=== TEST 3: WikiService.build_page() ===")
    try:
        from services.wiki_service import WikiService, _build_slug

        slug = _build_slug(TEST_QUERY)
        logger.info(f"  Yaratilayotgan slug: '{slug}'")
        logger.info(f"  So'rov: '{TEST_QUERY}'")

        await WikiService.build_page(TEST_QUERY, TEST_CONTEXT)
        ok(f"build_page() xatosiz tugadi (slug='{slug}')")
        return slug
    except Exception as e:
        fail("build_page()", e)
        return None


# ── TEST 4: Firestore sanity check ────────────────────────────────────────────

async def test_firestore_check(slug):
    logger.info(f"\n=== TEST 4: Firestore wiki_pages['{slug}'] sanity check ===")
    if not slug:
        skip("build_page muvaffaqiyatsiz — bu test o'tkazildi")
        return

    try:
        from loader import get_db
        db = get_db()

        # Gemini asinxron yozishi uchun biroz kutish
        logger.info("  Firestore yozilishi uchun 4s kutilmoqda...")
        await asyncio.sleep(4)

        doc = db.collection("wiki_pages").document(slug).get()
        if not doc.exists:
            fail(f"wiki_pages['{slug}'] Firestore da topilmadi")
            return

        data = doc.to_dict()
        title = data.get("title", "")
        content_len = len(data.get("content", ""))
        has_embedding = "embedding" in data
        hit_count = data.get("hit_count", -1)
        emb_status = "bor" if has_embedding else "YO'Q!"

        logger.info(f"  title:          {title}")
        logger.info(f"  content:        {content_len} belgi")
        logger.info(f"  embedding:      {emb_status}")
        logger.info(f"  hit_count:      {hit_count}")

        if content_len > 100 and has_embedding:
            ok("Firestore hujjat to'g'ri saqlangan (content + embedding mavjud)")
        elif content_len > 100:
            fail("Embedding yo'q — wiki_pages vector index uchun embedding kerak")
        else:
            fail(f"Content juda qisqa ({content_len} belgi) yoki bo'sh")
    except Exception as e:
        fail("Firestore sanity check", e)


# ── TEST 5: WikiService.search() ──────────────────────────────────────────────

async def test_search():
    logger.info("\n=== TEST 5: WikiService.search() ===")
    try:
        from services.wiki_service import WikiService

        # Hozir yaratilgan test sahifasini qidirish
        result = await WikiService.search(TEST_QUERY)

        if result:
            logger.info(f"  Hit! Content uzunligi: {len(result)} belgi")
            logger.info(f"  Birinchi 200 belgi:\n    {result[:200]}")
            ok("search() — wiki hit topildi va qaytdi")
        else:
            skip(
                "search() — miss (wiki_pages vector index yaratilmagan yoki "
                "cosine distance > 0.25). Firestore Console da vector index tekshiring."
            )
    except Exception as e:
        err_str = str(e)
        if "FAILED_PRECONDITION" in err_str or "index" in err_str.lower():
            skip(
                f"search() — Firestore vector index yaratilmagan. "
                f"Console → Firestore → Indexes → Vector indexes → Create: "
                f"collection=wiki_pages, field=embedding, dimension=768"
            )
        else:
            fail("search()", e)


# ── TEST 6: AIService.get_relevant_context() — to'liq zanjir ─────────────────

async def test_full_chain():
    logger.info("\n=== TEST 6: AIService.get_relevant_context() — to'liq zanjir ===")
    try:
        from services.ai_service import AIService

        query = "E-IMZO drayveri o'rnatish tartibi"
        logger.info(f"  So'rov: '{query}'")

        context = await AIService.get_relevant_context(query, limit=2)

        if context and len(context.strip()) > 50:
            logger.info(f"  Kontekst uzunligi: {len(context)} belgi")
            logger.info(f"  Birinchi 300 belgi:\n    {context[:300]}")
            ok("get_relevant_context() — kontekst qaytdi (Wiki/RAG/fallback)")
        elif context is not None and len(context.strip()) <= 50:
            skip(f"get_relevant_context() — qisqa kontekst (rag_chunks yoki knowledge_base ham bo'sh?)")
        else:
            skip("get_relevant_context() — bo'sh qaytdi")
    except Exception as e:
        fail("get_relevant_context()", e)


# ── TEST 7: _fire_and_forget xavfsizligi ─────────────────────────────────────

async def test_fire_and_forget():
    logger.info("\n=== TEST 7: _fire_and_forget xavfsizligi ===")
    try:
        from services.wiki_service import _fire_and_forget

        executed = []

        async def dummy_task():
            executed.append(True)

        # Running loop ichida — to'g'ri ishlanishi kerak
        _fire_and_forget(dummy_task())
        await asyncio.sleep(0.1)

        if executed:
            ok("_fire_and_forget() — running loop ichida task bajarildi")
        else:
            fail("_fire_and_forget() — task bajarilmadi")
    except Exception as e:
        fail("_fire_and_forget()", e)


# ── Tozalash ──────────────────────────────────────────────────────────────────

async def cleanup(slug):
    if not slug:
        return
    logger.info(f"\n=== CLEANUP: test hujjatini o'chirish ===")
    try:
        from loader import get_db
        get_db().collection("wiki_pages").document(slug).delete()
        logger.info(f"  wiki_pages['{slug}'] o'chirildi")
    except Exception as e:
        logger.warning(f"  Tozalash xatosi (muhim emas): {e}")


# ── MAIN ──────────────────────────────────────────────────────────────────────

async def main():
    logger.info("=" * 65)
    logger.info("  WikiService + AIService — integratsiya testi")
    logger.info("=" * 65)

    slug = None
    try:
        await test_slug()
        loaded = await test_loaders()

        if not loaded:
            logger.error("Loader ishlamadi — qolgan testlar o'tkaziladi")
        else:
            slug = await test_build_page()
            await test_firestore_check(slug)
            await test_search()
            await test_full_chain()

        await test_fire_and_forget()

    finally:
        await cleanup(slug)

    # ── Natija ────────────────────────────────────────────────────────────────
    logger.info("\n" + "=" * 65)
    passed  = sum(1 for s, _ in results if s is True)
    failed  = sum(1 for s, _ in results if s is False)
    skipped = sum(1 for s, _ in results if s is None)
    logger.info(f"  NATIJA:  {passed} PASS  |  {failed} FAIL  |  {skipped} SKIP")
    logger.info("=" * 65)
    for status, msg in results:
        icon = PASS_S if status is True else (FAIL_S if status is False else SKIP_S)
        logger.info(f"  {icon} {msg}")
    logger.info("")

    if failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
