import os
import json
import logging
from loader import db

logging.basicConfig(level=logging.INFO, format='%(message)s')

def chunk_markdown(text, chunk_size=1000, overlap=100):
    """
    Splits a large markdown text into smaller chunks based on size and overlap.
    A more sophisticated chunker could split by headings (e.g., '###').
    """
    chunks = []
    # Simple character-based chunking with overlap
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end]
        chunks.append(chunk)
        start += (chunk_size - overlap)
    return chunks

async def upload_knowledge_to_firestore():
    """Uploads the parsed knowledge markdown to Firestore for vector search."""
    file_path = 'data/knowledge.md'
    
    if not os.path.exists(file_path):
        logging.error(f"Fayl topilmadi: {file_path}")
        return

    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    logging.info(f"Yalpi bilim bazasi o'qildi: {len(content)} ta belgi.")
    
    # Chunking strategy
    chunks = chunk_markdown(content, chunk_size=1500, overlap=150)
    logging.info(f"{len(chunks)} ta bo'lakka (chunk) ajratildi.")

    collection_ref = db.collection('knowledge_base')
    
    # Tizimni yangilash uchun avvalgi eskilarni o'chirib tashlaymiz
    docs = collection_ref.stream()
    deleted_count = 0
    for doc in docs:
        doc.reference.delete()
        deleted_count += 1
    logging.info(f"{deleted_count} ta eski ma'lumotlar o'chirildi.")

    # Yangi chunk'larni yuklaymiz
    batch = db.batch()
    for i, part in enumerate(chunks):
        doc_ref = collection_ref.document() # Avtomatik ID
        data = {
            'text': part, # Extension shu maydonni (text) o'qiydi
            'source': 'knowledge.md',
            'chunk_index': i
        }
        batch.set(doc_ref, data)
        
        # Firestore batch limiti 500 ta operatsiya
        if (i + 1) % 400 == 0:
            batch.commit()
            logging.info(f"{i + 1} ta qism muvaffaqiyatli saqlandi...")
            batch = db.batch()
    
    # Qolganlarini ham saqlaymiz
    batch.commit()
    logging.info(f"Barcha {len(chunks)} ta qism muvaffaqiyatli Firestore'ga joylandi! \n💡 Vector Search Extension endi har biriga 'embedding' maydonini qo'shib chiqadi.")

if __name__ == "__main__":
    import asyncio
    asyncio.run(upload_knowledge_to_firestore())
