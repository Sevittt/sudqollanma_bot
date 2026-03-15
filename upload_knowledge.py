import os
import json
import logging
from loader import get_db, init_gemini
from google.genai import types

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def chunk_markdown(text, chunk_size=1200, overlap=150):
    """
    Splits a large markdown text into smaller chunks based on size and overlap.
    """
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end]
        chunks.append(chunk)
        start += (chunk_size - overlap)
    return chunks

async def get_embedding(text):
    """Generates a vector embedding for a given text using gemini-embedding-001."""
    try:
        client = init_gemini()
        if not client:
            raise ValueError("Gemini client not initialized. Check GEMINI_API_KEY.")
            
        result = client.models.embed_content(
            model="gemini-embedding-001",
            contents=text,
            config=types.EmbedContentConfig(output_dimensionality=768)
        )
        return result.embeddings[0].values
    except Exception as e:
        logging.error(f"Embedding error: {e}")
        return None

async def upload_knowledge_to_firestore():
    """Uploads chunks with pre-calculated embeddings to Firestore."""
    file_path = 'data/knowledge.md'
    db = get_db()
    
    if not db:
        logging.error("Database connection failed. Check serviceAccountKey.json or ADC.")
        return

    if not os.path.exists(file_path):
        logging.error(f"File not found: {file_path}")
        return

    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    logging.info(f"Reading knowledge base: {len(content)} characters.")
    
    chunks = chunk_markdown(content, chunk_size=1200, overlap=150)
    logging.info(f"Split into {len(chunks)} chunks.")

    collection_ref = db.collection('knowledge_base')
    
    # 1. Clean old data (Recommended for full re-sync)
    logging.info("Cleaning old knowledge base entries...")
    docs = collection_ref.stream()
    deleted = 0
    for doc in docs:
        doc.reference.delete()
        deleted += 1
    logging.info(f"Deleted {deleted} old entries.")

    # 2. Upload new data with embeddings
    logging.info("Generating embeddings and uploading to Firestore...")
    for i, part in enumerate(chunks):
        embedding = await get_embedding(part)
        if not embedding:
            logging.warning(f"Skipping chunk {i} due to embedding failure.")
            continue

        data = {
            'text': part,
            'source': 'knowledge.md',
            'chunk_index': i,
            'embedding': embedding
        }
        
        # Save individually for better error tracking during embedding generation
        collection_ref.add(data)
        
        if (i + 1) % 5 == 0:
            logging.info(f"Processed {i + 1}/{len(chunks)} chunks...")

    logging.info(f"Successfully uploaded {len(chunks)} chunks to Firestore with professional embeddings! ✅")

if __name__ == "__main__":
    import asyncio
    asyncio.run(upload_knowledge_to_firestore())
