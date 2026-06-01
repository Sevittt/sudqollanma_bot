"""
WikiService — LLM Wiki qatlami.

Firestore kolleksiyasi: wiki_pages
Har bir hujjat:
  - slug:         str  — hujjat ID (masalan: "e-imzo-drayveri-muammolari")
  - title:        str
  - content:      str (markdown)
  - embedding:    Vector(768) — content ning birinchi 2000 belgisidan
  - source_query: str  — qaysi savoldan yaratilgan
  - hit_count:    int  — necha marta ishlatilgan (analytics)
  - updated_at:   SERVER_TIMESTAMP

Mantiq:
  search()          → Vector Search (cosine, limit=1, threshold=0.25)
  build_page()      → Gemini bilan markdown yozadi → Firestore ga saqlaydi
  _increment_hit()  → hit_count ni oshiradi (analytics uchun)

⚠️  MUHIM — Firestore Vector Index:
  wiki_pages kolleksiyasida vector index qo'lda yaratilishi kerak:
    Field:     embedding
    Dimension: 768
    Yo'l:      Google Cloud Console → Firestore → Indexes → Vector indexes
               → Create vector index → Collection: wiki_pages
  Index bo'lmasa search() xato beradi (lekin try/except tufayli bot ishlashda davom etadi).
"""

import asyncio
import re
import logging
from typing import Optional

# pyrefly: ignore [missing-import]
from google.cloud.firestore_v1.vector import Vector
# pyrefly: ignore [missing-import]
from google.cloud.firestore_v1.base_vector_query import DistanceMeasure
# pyrefly: ignore [missing-import]
from google.cloud.firestore_v1 import SERVER_TIMESTAMP, Increment
from loader import get_db, init_gemini

logger = logging.getLogger(__name__)

WIKI_COLLECTION = "wiki_pages"

# Cosine distance threshold: 0 = identical, 2 = opposite.
# distance <= 0.35  →  cosine similarity >= 0.65  →  Wiki hit
# Eslatma: query embedding vs content embedding solishtirish tufayli
# bir xil mavzuda ~0.25 atrofida bo'ladi. 0.35 amaliy foydalanish uchun optimal.
# (Prompt bo'yicha: bosqich 3 da haqiqiy savollarga qarab sozlanadi)
COSINE_THRESHOLD = 0.35


def _fire_and_forget(coro) -> None:
    """Coroutine ni mavjud event loop da xavfsiz fon rejimida ishga tushiradi.

    asyncio.create_task() faqat running loop ichida ishlaydi.
    Bu helper loop mavjudligini tekshiradi va munosib usulni tanlaydi.
    """
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(coro)
    except RuntimeError:
        # Running loop yo'q (masalan, test muhitida) — coroutine e'tiborsiz qoldiriladi
        logger.debug("_fire_and_forget: running loop topilmadi, coroutine bekor qilindi")
        # Coroutine ni yopish (ResourceWarning oldini olish)
        coro.close()


def _build_slug(text: str) -> str:
    """So'rovdan slug hosil qiladi (hujjat ID sifatida ishlatiladi).

    Misol: "E-IMZO drayveri muammolari" → "e-imzo-drayveri-muammolari"
    """
    slug = re.sub(
        r"[^a-z0-9\u0400-\u04ff\-]",
        "",
        text.lower().replace(" ", "-"),
    )
    # Ketma-ket tireni birlashtirish va chekkalarini tozalash
    slug = re.sub(r"-{2,}", "-", slug).strip("-")
    return slug[:80]


def _build_prompt(topic: str, rag_context: str) -> str:
    """Wiki sahifa uchun Gemini promptini tuzadi."""
    ctx = rag_context[:4000]
    return (
        f"Quyidagi sud tizimi IT qo'llanmasi matnlaridan '{topic}' mavzusida\n"
        "wiki sahifa yoz. FAQAT berilgan manbada bor narsani yoz, o'ylab topma.\n\n"
        "Tuzilma:\n"
        f"## {topic}\n"
        "### Asosiy tushuntirish\n"
        "### Qadamlar (agar amaliy jarayon bo'lsa)\n"
        "### Tez-tez uchraydigan muammolar va yechimlari\n"
        "### Bog'liq mavzular\n\n"
        "Til: O'zbek (lotin)\n"
        "Uslub: Qisqa, aniq, sud xodimlariga tushunarli\n"
        "Hajm: 300-600 so'z\n\n"
        f"Manbalar:\n{ctx}"
    )


class WikiService:
    """LLM Wiki qatlami servisi."""

    @staticmethod
    async def search(query: str) -> Optional[str]:
        """wiki_pages dan Vector Search orqali mos sahifani qidiradi.

        Args:
            query: Foydalanuvchi so'rovi.

        Returns:
            Topilsa — markdown content satri.
            Topilmasa — None (RAG fallback uchun signal).
        """
        if not query or not query.strip():
            return None

        db = get_db()
        client = init_gemini()
        if not db or not client:
            return None

        try:
            from google.genai import types

            # So'rov uchun embedding hosil qilish
            embedding_result = client.models.embed_content(
                model="gemini-embedding-2",
                contents=query,
                config=types.EmbedContentConfig(output_dimensionality=768),
            )
            query_vector = embedding_result.embeddings[0].values

            # wiki_pages da Vector Search (limit=1)
            results = (
                db.collection(WIKI_COLLECTION)
                .find_nearest(
                    vector_field="embedding",
                    query_vector=Vector(query_vector),
                    distance_measure=DistanceMeasure.COSINE,
                    limit=1,
                    distance_result_field="vector_distance",
                )
                .get()
            )

            for doc in results:
                data = doc.to_dict()
                distance = data.get("vector_distance", 1.0)

                if distance <= COSINE_THRESHOLD:
                    content = data.get("content", "")
                    if content:
                        slug = data.get("slug", doc.id)
                        logger.info(
                            f"Wiki hit ✅ → \"{slug}\" (distance={distance:.3f})"
                        )
                        # hit_count ni fon rejimida oshirish (xavfsiz)
                        _fire_and_forget(WikiService._increment_hit(doc.id))
                        return content
                else:
                    logger.info(
                        f"Wiki miss (distance={distance:.3f} > threshold={COSINE_THRESHOLD})"
                    )

        except Exception as e:
            logger.error(f"WikiService.search() xatosi: {e}")

        logger.info(f"Wiki miss → RAG fallback for \"{query}\"")
        return None

    @staticmethod
    async def build_page(query: str, rag_context: str) -> None:
        """RAG kontekstidan fon rejimida wiki sahifa yaratadi.

        Duplicate oldini olish: slug bo'yicha hujjat allaqachon mavjud bo'lsa chiqadi.
        Bu metod asyncio.create_task() bilan chaqirilishi kerak —
        foydalanuvchi javobni kutmasin.

        Args:
            query:       Foydalanuvchi so'rovi (sahifa mavzusi sifatida ishlatiladi).
            rag_context: RAG Vector Search dan kelgan matn (manba).
        """
        if not query or not query.strip():
            return
        if not rag_context or not rag_context.strip():
            return

        slug = _build_slug(query)
        db = get_db()
        client = init_gemini()
        if not db or not client:
            return

        try:
            # Duplicate tekshirish
            existing = db.collection(WIKI_COLLECTION).document(slug).get()
            if existing.exists:
                logger.info(
                    f"WikiService: \"{slug}\" allaqachon mavjud, o'tkazib yuborildi"
                )
                return

            # Gemini bilan wiki sahifa yozish
            import config

            prompt = _build_prompt(query, rag_context)
            response = await client.aio.models.generate_content(
                model=config.GEMINI_MODEL,
                contents=prompt,
            )
            content = response.text
            if not content or not content.strip():
                logger.warning(f"WikiService: \"{slug}\" uchun Gemini bo'sh javob qaytardi")
                return

            # Content ning birinchi 2000 belgisidan embedding hosil qilish
            from google.genai import types

            embedding_result = client.models.embed_content(
                model="gemini-embedding-2",
                contents=content[:2000],
                config=types.EmbedContentConfig(output_dimensionality=768),
            )
            embedding_values = embedding_result.embeddings[0].values

            # Firestore ga saqlash
            db.collection(WIKI_COLLECTION).document(slug).set(
                {
                    "slug": slug,
                    "title": query,
                    "content": content.strip(),
                    "embedding": Vector(embedding_values),
                    "source_query": query,
                    "hit_count": 0,
                    "updated_at": SERVER_TIMESTAMP,
                }
            )

            logger.info(f"WikiService: yangi sahifa yaratildi → \"{slug}\"")

        except Exception as e:
            logger.error(f"WikiService.build_page() xatosi (slug={slug}): {e}")

    @staticmethod
    async def _increment_hit(doc_id: str) -> None:
        """hit_count ni atomik ravishda oshiradi (analytics)."""
        try:
            get_db().collection(WIKI_COLLECTION).document(doc_id).update(
                {"hit_count": Increment(1)}
            )
        except Exception as e:
            logger.error(f"WikiService._increment_hit() xatosi: {e}")
