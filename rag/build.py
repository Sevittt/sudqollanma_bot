"""Yagona RAG yig'uvchi (CLI).

Misollar:
  python -m rag.build --dry-run                      # hech narsa yozmaydi, faqat hisobot
  python -m rag.build --dry-run --source dars        # bitta manba
  python -m rag.build                                # embed + rag_chunks_v2 ga yozish

Faqat matni o'zgargan bo'laklar qayta embed qilinadi (hash bo'yicha).
Manbadan yo'qolgan bo'laklar kolleksiyadan o'chiriladi.
"""
from __future__ import annotations

import argparse
import logging
import os
import statistics
import sys
import time
from collections import Counter
from pathlib import Path

from rag import sources as src
from rag.sync import content_hash, dedupe, plan_sync

log = logging.getLogger('rag.build')

DEFAULT_COLLECTION = 'rag_chunks_v2'
EMBED_BATCH = 50
WRITE_BATCH = 400


def _model() -> tuple[str, int]:
    return (os.getenv('EMBEDDING_MODEL', 'gemini-embedding-2'),
            int(os.getenv('EMBEDDING_DIM', '768')))


# ── tashqi ulanishlar (loader.py'ni import qilmaymiz: u BOT_TOKEN talab qiladi) ──

def connect_firestore():
    import firebase_admin
    from firebase_admin import credentials, firestore

    if not firebase_admin._apps:
        key = os.getenv('FIREBASE_CREDENTIALS') or str(src.BOT_ROOT / 'serviceAccountKey.json')
        if Path(key).exists():
            firebase_admin.initialize_app(credentials.Certificate(key))
        else:
            firebase_admin.initialize_app(options={'projectId': 'educationapp-4780a'})
    return firestore.client()


def gemini_client():
    from dotenv import load_dotenv
    from google import genai

    load_dotenv(src.BOT_ROOT / '.env')
    key = os.getenv('GEMINI_API_KEY')
    if not key:
        raise RuntimeError('GEMINI_API_KEY topilmadi (.env)')
    return genai.Client(api_key=key)


def embed_documents(client, texts: list[str], model: str, dim: int, retries: int = 5) -> list[list[float]]:
    from google.genai import types

    config = types.EmbedContentConfig(task_type='RETRIEVAL_DOCUMENT', output_dimensionality=dim)
    for attempt in range(retries):
        try:
            result = client.models.embed_content(model=model, contents=texts, config=config)
            vectors = [e.values for e in result.embeddings]
            if len(vectors) != len(texts):
                raise RuntimeError(f'{len(texts)} ta matnga {len(vectors)} ta vektor qaytdi')
            return vectors
        except Exception as e:  # 429 / 5xx — kutib qayta urinish
            if attempt == retries - 1:
                raise
            wait = 2 ** attempt * 5
            log.warning('Embedding xatosi (%s), %s s dan keyin qayta urinish', e, wait)
            time.sleep(wait)
    return []


def read_existing(db, collection: str) -> dict[str, dict]:
    return {
        doc.id: doc.to_dict() or {}
        for doc in db.collection(collection).select(['hash', 'source']).stream()
    }


# ── hisobot ──────────────────────────────────────────────────────────────────

def report(loaded: dict, kept, dropped, plan) -> str:
    lines = ['Manba        bo\'lak  hujjat  o\'rtacha belgi  maks']
    for name, chunks in loaded.items():
        sizes = [len(c.text) for c in chunks] or [0]
        docs = len({c.doc_id for c in chunks})
        lines.append(f'{name:<12} {len(chunks):>6}  {docs:>6}  {int(statistics.mean(sizes)):>14}  {max(sizes):>4}')
    dup_by_source = Counter(c.source for c in dropped)
    lines += [
        '',
        f'Jami: {sum(len(v) for v in loaded.values())}, takror olib tashlandi: {len(dropped)} {dict(dup_by_source)}',
        f'Qoladi: {len(kept)}',
        f'Reja: embed+yozish {len(plan.upsert)}, o\'zgarmagan {len(plan.unchanged)}, o\'chirish {len(plan.delete)}',
    ]
    return '\n'.join(lines)


# ── asosiy oqim ──────────────────────────────────────────────────────────────

def run(names: list[str], collection: str, dry_run: bool, offline: bool) -> int:
    model, dim = _model()
    needs_db = not offline and (not dry_run or any(n in src.FIRESTORE_SOURCES for n in names))
    db = connect_firestore() if needs_db else None
    if offline:
        names = [n for n in names if n in src.LOCAL_SOURCES]

    loaded = src.load(names, db=db)
    ordered = [c for name in names for c in loaded[name]]
    kept, dropped = dedupe(ordered)
    existing = read_existing(db, collection) if db is not None else {}
    plan = plan_sync(kept, existing, set(names), model, dim)

    print(f'Model: {model} ({dim}), kolleksiya: {collection}, manbalar: {", ".join(names)}')
    print(report(loaded, kept, dropped, plan))
    if dry_run:
        print('\n--dry-run: hech narsa yozilmadi.')
        return 0

    from firebase_admin import firestore
    from google.cloud.firestore_v1.vector import Vector

    client = gemini_client()
    col = db.collection(collection)
    written = 0
    for i in range(0, len(plan.upsert), EMBED_BATCH):
        part = plan.upsert[i:i + EMBED_BATCH]
        vectors = embed_documents(client, [c.embed_input() for c in part], model, dim)
        batch = db.batch()
        for chunk, vector in zip(part, vectors):
            batch.set(col.document(chunk.id), {
                'source': chunk.source,
                'doc_id': chunk.doc_id,
                'doc_title': chunk.doc_title,
                'section': chunk.section,
                'category': chunk.category,
                'text': chunk.text,
                'embedding': Vector(vector),
                'model': model,
                'dim': dim,
                'hash': content_hash(chunk, model, dim),
                'updatedAt': firestore.SERVER_TIMESTAMP,
            })
        batch.commit()
        written += len(part)
        print(f'  yozildi {written}/{len(plan.upsert)}', flush=True)

    for i in range(0, len(plan.delete), WRITE_BATCH):
        batch = db.batch()
        for doc_id in plan.delete[i:i + WRITE_BATCH]:
            batch.delete(col.document(doc_id))
        batch.commit()
    print(f'Tayyor: {written} ta yozildi, {len(plan.delete)} ta o\'chirildi.')
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='Yagona RAG yig\'uvchi')
    parser.add_argument('--source', action='append', choices=src.ALL_SOURCES,
                        help='faqat shu manba(lar); ko\'rsatilmasa — hammasi')
    parser.add_argument('--collection', default=DEFAULT_COLLECTION)
    parser.add_argument('--dry-run', action='store_true', help='yozmaydi, faqat hisobot')
    parser.add_argument('--offline', action='store_true',
                        help='Firestore\'ga ulanmaydi (faqat lokal manbalar, --dry-run bilan)')
    args = parser.parse_args(argv)
    if args.offline and not args.dry_run:
        parser.error('--offline faqat --dry-run bilan ishlaydi')

    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    logging.basicConfig(level=logging.INFO, format='%(levelname)s %(message)s')
    return run(args.source or list(src.ALL_SOURCES), args.collection, args.dry_run, args.offline)


if __name__ == '__main__':
    sys.exit(main())
