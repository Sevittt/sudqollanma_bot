import os
import sys
import logging
import json
import firebase_admin
from firebase_admin import credentials, firestore
from google import genai
from google.genai import types

# Asosiy papkani pathga qo'shish
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)

from loader import get_db, init_gemini

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# RAG chunk'lari maqolalardan ALOHIDA kolleksiyada saqlanadi.
# knowledge_base  → Library UI maqolalari (populate_articles.py yozadi)
# rag_chunks      → Vector search uchun chunk'lar (bu skript yozadi)
RAG_COLLECTION = 'rag_chunks'


def chunk_by_section(text: str, max_size: int = 1200, overlap: int = 150) -> list[dict]:
    """
    Markdown sarlavhalar (## yoki ###) bo'yicha bo'ladi.
    Agar bo'lim max_size dan katta bo'lsa, sliding window bilan maydalaydi.
    Har bir chunk { title, text } formatida qaytaradi.
    """
    import re
    sections = re.split(r'\n(?=#{1,3} )', text)
    chunks = []

    for section in sections:
        lines = section.strip().splitlines()
        if not lines:
            continue

        # Birinchi qator sarlavha bo'lishi mumkin
        title = lines[0].lstrip('#').strip() if lines[0].startswith('#') else ''
        body = section.strip()

        if len(body) <= max_size:
            chunks.append({'title': title, 'text': body})
        else:
            # Sliding window
            start = 0
            while start < len(body):
                end = start + max_size
                chunk_text = body[start:end]
                chunks.append({'title': title, 'text': chunk_text})
                start += (max_size - overlap)

    return chunks


async def get_embedding(
    text: str,
    model: str = 'gemini-embedding-2',
    max_retries: int = 5,
) -> list[float] | None:
    """
    Gemini Embedding 2 orqali vektor generatsiya qiladi.
    Rate limit (429) bo'lsa exponential backoff bilan qayta urinadi.
    """
    import asyncio

    client = init_gemini()
    if not client:
        logging.error("Gemini client ishga tushmadi.")
        return None

    for attempt in range(max_retries):
        try:
            result = client.models.embed_content(
                model=model,
                contents=text,
                config=types.EmbedContentConfig(output_dimensionality=768)
            )
            return result.embeddings[0].values
        except Exception as e:
            msg = str(e)
            if '429' in msg or 'RESOURCE_EXHAUSTED' in msg:
                wait = 2 ** attempt * 10  # 10s, 20s, 40s, 80s, 160s
                logging.warning(f"Rate limit. {wait}s kutilmoqda... (urinish {attempt + 1}/{max_retries})")
                await asyncio.sleep(wait)
            else:
                logging.error(f"Embedding xatosi: {e}")
                return None

    logging.error("Maksimal urinishlar tugadi, chunk o'tkazib yuborildi.")
    return None


async def upload_knowledge_to_firestore(file_path: str = None):
    """
    knowledge.md ni bo'limlarga ajratib, embedding generatsiya qilib,
    rag_chunks kolleksiyasiga yuklaydi.
    """
    if file_path is None:
        # Default path relative to root
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        file_path = os.path.join(base_dir, 'data', 'knowledge.md')
    db = get_db()
    if not db:
        logging.error("Firestore ulanmadi.")
        return

    if not os.path.exists(file_path):
        logging.error(f"Fayl topilmadi: {file_path}")
        return

    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    logging.info(f"knowledge.md o'qildi: {len(content)} belgi.")

    chunks = chunk_by_section(content, max_size=1200, overlap=150)
    logging.info(f"{len(chunks)} ta chunk ajratildi.")

    collection_ref = db.collection(RAG_COLLECTION)

    # Faqat knowledge.md manbaidan kelgan eski chunk'larni o'chirish
    logging.info("Eski knowledge.md chunk'lari o'chirilmoqda...")
    old_docs = collection_ref.where('source', '==', 'knowledge.md').stream()
    deleted = 0
    for doc in old_docs:
        doc.reference.delete()
        deleted += 1
    logging.info(f"{deleted} ta eski chunk o'chirildi.")

    # Allaqachon yuklangan chunk'larni aniqlash (qayta ishlatganda skip qilish uchun)
    existing_ids = {
        doc.id for doc in collection_ref.where('source', '==', 'knowledge.md').stream()
    }
    logging.info(f"Allaqachon mavjud: {len(existing_ids)} ta chunk.")

    # Yangi chunk'larni embedding bilan yuklash
    logging.info("Embedding generatsiya va yuklash boshlandi...")
    import asyncio
    success = 0
    skipped = 0
    for i, chunk in enumerate(chunks):
        doc_id = f"km_{i:04d}"  # deterministic ID: km_0000, km_0001, ...

        if doc_id in existing_ids:
            skipped += 1
            continue

        embedding = await get_embedding(chunk['text'])
        if not embedding:
            logging.warning(f"Chunk {i} uchun embedding olinmadi, o'tkazib yuborildi.")
            continue

        data = {
            'title': chunk['title'],
            'text': chunk['text'],
            'embedding': embedding,
            'source': 'knowledge.md',
            'chunk_index': i,
        }
        collection_ref.document(doc_id).set(data)
        success += 1

        # Rate limit: har 5 so'rovdan keyin 2s dam olish
        if success % 5 == 0:
            await asyncio.sleep(2)
            logging.info(f"  {i + 1}/{len(chunks)} chunk yuklandi (skip: {skipped})...")

    logging.info(f"✅ knowledge.md: {success} yangi, {skipped} mavjud (jami: {len(chunks)} chunk).")


async def upload_faqs_to_rag():
    """faqs kolleksiyasini RAG uchun rag_chunks ga ko'chiradi."""
    db = get_db()
    if not db:
        return

    collection_ref = db.collection(RAG_COLLECTION)

    # Eski FAQ chunk'larini o'chirish
    old = collection_ref.where('source', '==', 'faqs').stream()
    for doc in old:
        doc.reference.delete()

    import asyncio
    faq_docs = list(db.collection('faqs').stream())
    existing_faq_ids = {
        doc.to_dict().get('faq_id')
        for doc in collection_ref.where('source', '==', 'faqs').stream()
    }

    success = 0
    for i, doc in enumerate(faq_docs):
        if doc.id in existing_faq_ids:
            continue

        faq = doc.to_dict()
        q = faq.get('question', '')
        a = faq.get('answer', '')
        t = ', '.join(faq.get('tags', []))
        text = f"Savol: {q}\nJavob: {a}\nTeglar: {t}"

        embedding = await get_embedding(text)
        if not embedding:
            continue

        collection_ref.document(f"faq_{doc.id}").set({
            'title': q,
            'text': text,
            'embedding': embedding,
            'source': 'faqs',
            'faq_id': doc.id,
        })
        success += 1

        if success % 5 == 0:
            await asyncio.sleep(2)

    logging.info(f"✅ FAQs: {success} ta chunk yuklandi.")


if __name__ == "__main__":
    import asyncio

    async def main():
        await upload_knowledge_to_firestore()
        await upload_faqs_to_rag()

    asyncio.run(main())
