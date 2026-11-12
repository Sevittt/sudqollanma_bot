"""
WikiService — LLM Wiki qatlami.

Firestore kolleksiyalari:
  1. wiki_pages: LLM yozgan, strukturalangan markdown sahifalar.
  2. wiki_meta/wiki_index: Tezkor kalit so'z va alias qidiruv xaritasi.
  3. wiki_log: Har bir o'zgarish va adversarial review natijalari audit jurnali.

Mantiq:
  search()          → 1. wiki_index direct match, 2. wiki_pages Vector Search.
  build_page()      → Gemini Creator + Adversarial Reviewer hamkorligida yaratadi/birlashtiradi.
"""

import asyncio
import re
import logging
import json
from typing import Optional, Dict, Any

# pyrefly: ignore [missing-import]
from google.cloud.firestore_v1.vector import Vector
# pyrefly: ignore [missing-import]
from google.cloud.firestore_v1.base_vector_query import DistanceMeasure
# pyrefly: ignore [missing-import]
from google.cloud.firestore_v1 import SERVER_TIMESTAMP, Increment
from loader import get_db, init_gemini
import config

logger = logging.getLogger(__name__)

WIKI_COLLECTION = "wiki_pages"
WIKI_META_COLLECTION = "wiki_meta"
WIKI_LOG_COLLECTION = "wiki_log"
WIKI_INDEX_DOCUMENT = "wiki_index"

# Cosine distance threshold config.py dan olinadi (markazlashtirilgan)
COSINE_THRESHOLD = config.WIKI_HIT_THRESHOLD


def _fire_and_forget(coro) -> None:
    """Coroutine ni mavjud event loop da xavfsiz fon rejimida ishga tushiradi."""
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(coro)
    except RuntimeError:
        logger.debug("_fire_and_forget: running loop topilmadi, coroutine bekor qilindi")
        coro.close()


def _build_slug(text: str) -> str:
    """So'rovdan yoki sarlavhadan slug hosil qiladi."""
    slug = re.sub(
        r"[^a-z0-9\u0400-\u04ff\-]",
        "",
        text.lower().replace(" ", "-"),
    )
    slug = re.sub(r"-{2,}", "-", slug).strip("-")
    return slug[:80]


def _parse_json(text: str) -> Optional[dict]:
    """Gemini qaytargan matndan JSON ni xavfsiz ajratib oladi."""
    if not text:
        return None
    try:
        cleaned = text.strip()
        if cleaned.startswith("```"):
            lines = cleaned.splitlines()
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines[-1].startswith("```"):
                lines = lines[:-1]
            cleaned = "\n".join(lines).strip()
        return json.loads(cleaned)
    except Exception as e:
        logger.error(f"JSON parsing xatosi: {e}\nOriginal text: {text}")
        try:
            start = text.find('{')
            end = text.rfind('}') + 1
            if start != -1 and end > start:
                return json.loads(text[start:end])
        except Exception as e2:
            logger.error(f"Fallback JSON parsing xatosi: {e2}")
    return None


def _match_index(query: str, index_data: dict) -> Optional[str]:
    """Qidiruv so'rovi bo'yicha wiki_index'dan eng yaqin mos slug'ni qaytaradi."""
    if not query or not index_data or "topics" not in index_data:
        return None
    
    q = query.lower().strip()
    topics = index_data["topics"]
    
    # 1. To'g'ridan-to'g'ri slug mosligi
    if q in topics:
        return q
        
    # 2. Sarlavha yoki alias mosligi
    for slug, meta in topics.items():
        title = meta.get("title", "").lower()
        if q == title or q in title or title in q:
            return slug
            
        aliases = [a.lower() for a in meta.get("aliases", [])]
        for alias in aliases:
            if q == alias or alias in q or q in alias:
                return slug
            
    return None


class WikiService:
    """LLM Wiki qatlami servisi."""

    @staticmethod
    async def search(query: str) -> Optional[str]:
        """wiki_pages dan tezkor index yoki Vector Search orqali sahifa qidiradi."""
        if not query or not query.strip():
            return None

        db = get_db()
        client = init_gemini()
        if not db or not client:
            return None

        try:
            # ── 1. Gibrid Qidiruv: wiki_index direct match ────────────────────────
            index_doc = db.collection(WIKI_META_COLLECTION).document(WIKI_INDEX_DOCUMENT).get()
            if index_doc.exists:
                index_data = index_doc.to_dict()
                matched_slug = _match_index(query, index_data)
                if matched_slug:
                    doc = db.collection(WIKI_COLLECTION).document(matched_slug).get()
                    if doc.exists:
                        data = doc.to_dict()
                        content = data.get("content", "")
                        if content:
                            logger.info(f"Wiki Index Hit ✅ → \"{matched_slug}\" (Tezkor kalit so'z mosligi)")
                            _fire_and_forget(WikiService._increment_hit(matched_slug))
                            return content

            # ── 2. Vector Search ────────────────────────────────────────────
            from google.genai import types

            embedding_result = await client.aio.models.embed_content(
                model=config.EMBEDDING_MODEL,
                contents=query,
                config=types.EmbedContentConfig(output_dimensionality=config.EMBEDDING_DIM),
            )
            query_vector = embedding_result.embeddings[0].values

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
                        logger.info(f"Wiki Vector Hit ✅ → \"{slug}\" (distance={distance:.3f})")
                        _fire_and_forget(WikiService._increment_hit(doc.id))
                        return content
                else:
                    logger.info(f"Wiki miss (distance={distance:.3f} > threshold={COSINE_THRESHOLD})")

        except Exception as e:
            logger.error(f"WikiService.search() xatosi: {e}")

        logger.info(f"Wiki miss → RAG fallback for \"{query}\"")
        return None

    @staticmethod
    async def build_page(query: str, rag_context: str) -> None:
        """RAG kontekstidan fon rejimida wiki sahifa yaratadi (Adversarial Review bilan)."""
        if not query or not query.strip() or not rag_context or not rag_context.strip():
            return

        db = get_db()
        client = init_gemini()
        if not db or not client:
            return

        try:
            # ── 1. Creator Zanjiri: Wiki sahifa qoralamasini yozish ──────────────────
            creator_prompt = (
                f"Sen O'zbekiston sud tizimi IT mutaxassislarining Wiki sahifalarini tuzuvchi 'Creator' AIsan.\n"
                f"Foydalanuvchi muammosi / so'rovi: '{query}'\n\n"
                f"--- ORIGINAL MANBALAR (RAG KONTEKSTI) ---\n"
                f"{rag_context[:6000]}\n"
                f"-----------------------------------------\n\n"
                f"Ushbu manbalar asosida, sud xodimlari uchun qisqa, tushunarli va yuqori darajada strukturalangan o'zbekcha wiki sahifasini tuzib ber.\n"
                f"DIQQAT: Sening yozgan kontenting FAQAT va FAQAT original manbalarda keltirilgan faktlarga asoslanishi SHART. "
                f"Manbada ko'rsatilmagan har qanday tashqi texnik qadamlar (masalan, 'Boshqaruv paneli orqali o'chirish' kabi amallar), "
                f"muammoning sabablari haqidagi taxminlar, qo'shimcha maslahatlar yoki o'zingizdan qo'shilgan buyruqlarni yozish QAT'IYAN MAN ETILADI. "
                f"Manbada yo'q narsalarni qo'shsangiz, adversarial reviewer sahifani rad etadi. "
                f"Agar manba juda qisqa bo'lsa, kontent matni ham juda qisqa va qat'iy bo'lishi kerak. Hech qanday kengaytirish va 'puflash'ga yo'l qo'yilmaydi.\n\n"
                f"Javobni quyidagi JSON formatida qaytar. Boshqa hech qanday so'z yoki tushuntirish qo'shma:\n"
                f"{{\n"
                f'  "standardized_title": "Standartlashtirilgan o\'zbekcha qisqa sarlavha (masalan: \'E-IMZO drayverini o\'rnatish\')",\n'
                f'  "aliases": ["qidiruv kalit so\'zlari, sinonimlar ro\'yxati (kamida 3-4 ta)"],\n'
                f'  "content": "Professional markdown formatida wiki sahifasi matni. FAQAT manbadagi faktlarni yozing, o\'zingizdan hech qanday texnik qadamlar yoki taxminlar qo\'shmang. Har bir da\'vo oxirida manba provensiyasini ^[Manba: fayl_nomi] formatida aniq ko\'rsating. Matn hajmi original manba hajmiga mutanosib bo\'lishi shart, qisqa manbalar uchun juda qisqa va aniq yozing.",\n'
                f'  "systemId": "ESUD | EXAT | EIMZO | EDO | GENERAL",\n'
                f'  "relations": [\n'
                f'    {{"target": "standart-bog\'liq-sahifa-slugi", "type": "requires | supersedes | related"}}\n'
                f'  ],\n'
                f'  "provenance": [\n'
                f'    {{"claim": "muhim da\'vo yoki qadam matni", "source": "manba fayl yoki qo\'llanma nomi"}}\n'
                f'  ]\n'
                f"}}\n"
            )

            response = await client.aio.models.generate_content(
                model=config.GEMINI_MODEL,
                contents=creator_prompt,
            )
            
            data = _parse_json(response.text)
            if not data or "content" not in data or "standardized_title" not in data:
                logger.warning("WikiService: Creator noto'g'ri loyiha qaytardi.")
                return

            standardized_title = data["standardized_title"]
            slug = _build_slug(standardized_title)

            # ── 2. Identity & Merge: Dublikat oldini olish va mavjudini yangilash ─────
            existing_doc = db.collection(WIKI_COLLECTION).document(slug).get()
            if existing_doc.exists:
                logger.info(f"WikiService: \"{slug}\" mavjud. Yangi ma'lumotlar bilan birlashtirilmoqda...")
                existing_data = existing_doc.to_dict()
                existing_content = existing_data.get("content", "")

                merge_prompt = (
                    f"Sen O'zbekiston sud tizimi IT Wiki sahifalarini birlashtiruvchi AIsan.\n"
                    f"Mavjud Wiki sahifasi matni:\n{existing_content}\n\n"
                    f"Yangi kelgan qo'shimcha ma'lumotlar:\n{data.get('content', '')}\n\n"
                    f"Ushbu ikki ma'lumotni birlashtirib, bitta mukammal, takrorlanishlarsiz va to'liq Wiki sahifasini yoz. Qolgan JSON maydonlarni ham o'zaro birlashtirib yangilang.\n"
                    f"Javobni quyidagi JSON formatida qaytar, boshqa hech narsa qo'shma:\n"
                    f"{{\n"
                    f'  "standardized_title": "{standardized_title}",\n'
                    f'  "aliases": ["birlashtirilgan barcha aliases ro\'yxati (takrorlanishlarsiz)"],\n'
                    f'  "content": "Birlashtirilgan professional markdown matni",\n'
                    f'  "systemId": "{data.get("systemId", "GENERAL")}",\n'
                    f'  "relations": [birlashtirilgan relations],\n'
                    f'  "provenance": [birlashtirilgan provenance]\n'
                    f"}}\n"
                )
                
                merge_response = await client.aio.models.generate_content(
                    model=config.GEMINI_MODEL,
                    contents=merge_prompt,
                )
                merged_data = _parse_json(merge_response.text)
                if merged_data and "content" in merged_data:
                    data = merged_data

            # ── 3. Adversarial Review: Ikki bosqichli tekshiruv ─────────────────────
            draft_json_str = json.dumps(data, ensure_ascii=False, indent=2)
            reviewer_prompt = (
                f"Sen O'zbekiston sud tizimi IT Wiki sahifalarini audit qiluvchi, o'ta talabchan va shafqatsiz 'Reviewer' AIsan.\n"
                f"Sening vazifang — quyida taqdim etilgan Wiki sahifasi loyihasini (draft) berilgan original RAG manbalari bilan solishtirib tekshirish.\n\n"
                f"--- ORIGINAL MANBALAR (RAG KONTEKSTI) ---\n"
                f"{rag_context[:6000]}\n"
                f"-----------------------------------------\n\n"
                f"--- WIKI DRAFT LOYIHASI ---\n"
                f"{draft_json_str}\n"
                f"---------------------------\n\n"
                f"Tekshirish mezonlari:\n"
                f"1. Gallyutsinatsiya (Hallucination): Loyihada original manbalarda mutlaqo tilga olinmagan ma'lumotlar, asossiz da'volar yoki o'ylab topilgan buyruq/qadamlar bormi?\n"
                f"2. Qarama-qarshilik (Contradiction): Loyihadagi ma'lumotlar original manbalarga yoki bir-biriga zidmi?\n"
                f"3. Havolalar aniqligi (Provenance): Loyihada keltirilgan manba havolalari to'g'ri va asolidmi?\n\n"
                f"Javobni quyidagi JSON formatida qaytar. Boshqa hech qanday so'z yoki tushuntirish qo'shma:\n"
                f"{{\n"
                f'  "approved": true | false,\n'
                f'  "review_score": 0.0 dan 1.0 gacha bo\'lgan ball (agar ma\'lumot to\'liq to\'g\'ri bo\'lsa 0.8 dan yuqori ball bering),\n'
                f'  "feedback": "Batafsil tahliliy fikringiz va agar approved=false bo\'lsa uning sababi"\n'
                f"}}\n"
            )

            reviewer_response = await client.aio.models.generate_content(
                model=config.GEMINI_MODEL,
                contents=reviewer_prompt,
            )
            
            reviewer_data = _parse_json(reviewer_response.text)
            approved = False
            review_score = 0.0
            feedback = "Tahlil xatosi"

            if reviewer_data:
                approved = reviewer_data.get("approved", False)
                review_score = float(reviewer_data.get("review_score", 0.0))
                feedback = reviewer_data.get("feedback", "")

            # ── 4. Audit Log Yozish ────────────────────────────────────────────────
            action_type = "UPDATE" if existing_doc.exists else "CREATE"
            log_ref = db.collection(WIKI_LOG_COLLECTION).document()
            log_ref.set({
                "timestamp": SERVER_TIMESTAMP,
                "action": action_type,
                "slug": slug,
                "trigger_query": query,
                "review_score": review_score,
                "reviewer_feedback": feedback,
                "approved": approved
            })

            if not approved or review_score < 0.8:
                logger.warning(f"WikiService: Sahifa rad etildi (slug={slug}, score={review_score}). Sabab: {feedback}")
                return

            # ── 5. Saqlash va Index Yangilash ──────────────────────────────────────
            # Content ning birinchi 2000 belgisidan embedding hosil qilish
            from google.genai import types

            content_text = data["content"]
            embedding_result = await client.aio.models.embed_content(
                model=config.EMBEDDING_MODEL,
                contents=content_text[:2000],
                config=types.EmbedContentConfig(output_dimensionality=config.EMBEDDING_DIM),
            )
            embedding_values = embedding_result.embeddings[0].values

            # Firestore wiki_pages sahifasini yozish
            db.collection(WIKI_COLLECTION).document(slug).set({
                "slug": slug,
                "title": standardized_title,
                "content": content_text.strip(),
                "embedding": Vector(embedding_values),
                "source_query": query,
                "systemId": data.get("systemId", "GENERAL"),
                "aliases": data.get("aliases", []),
                "relations": data.get("relations", []),
                "provenance": data.get("provenance", []),
                "hit_count": existing_data.get("hit_count", 0) if existing_doc.exists else 0,
                "updated_at": SERVER_TIMESTAMP,
                "review_score": review_score
            })

            # Firestore wiki_index xaritasini tranzaksiyasiz, atomik yangilash (xavfsiz merge)
            index_ref = db.collection(WIKI_META_COLLECTION).document(WIKI_INDEX_DOCUMENT)
            index_ref.set({
                "last_updated": SERVER_TIMESTAMP,
                "topics": {
                    slug: {
                        "title": standardized_title,
                        "systemId": data.get("systemId", "GENERAL"),
                        "aliases": data.get("aliases", [])
                    }
                }
            }, merge=True)

            logger.info(f"WikiService: Wiki sahifasi muvaffaqiyatli saqlandi va index yangilandi! → \"{slug}\"")

        except Exception as e:
            logger.error(f"WikiService.build_page() xatosi (query={query}): {e}")

    @staticmethod
    async def _increment_hit(doc_id: str) -> None:
        """hit_count ni atomik ravishda oshiradi (analytics)."""
        try:
            get_db().collection(WIKI_COLLECTION).document(doc_id).update(
                {"hit_count": Increment(1)}
            )
        except Exception as e:
            logger.error(f"WikiService._increment_hit() xatosi: {e}")
