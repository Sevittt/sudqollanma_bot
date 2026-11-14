"""rag_chunks_v2 bo'yicha vektor qidiruv (rag/build.py yig'adigan kolleksiya).

Hujjatlar gemini-embedding-2 + RETRIEVAL_DOCUMENT bilan indekslangan,
shuning uchun savol ham aynan shu model va RETRIEVAL_QUERY bilan embed qilinadi.
"""
from __future__ import annotations

import logging

import config
from loader import get_db, init_gemini

log = logging.getLogger(__name__)


def format_context(hits: list[dict], max_chars: int = 3000) -> str:
    """Topilgan bo'laklarni manbasi ko'rsatilgan kontekst matniga aylantiradi."""
    parts = []
    for hit in hits:
        header = hit.get('section') or hit.get('doc_title') or ''
        text = (hit.get('text') or '')[:max_chars]
        if text:
            parts.append(f'[Manba: {header}]\n{text}' if header else text)
    return '\n\n---\n\n'.join(parts)


def filter_hits(hits: list[dict], max_distance: float) -> list[dict]:
    """Juda uzoq (mavzuga aloqasiz) natijalarni tashlaydi."""
    return [h for h in hits if h.get('distance', 0.0) <= max_distance]


async def search(query: str, limit: int | None = None) -> list[dict]:
    query = (query or '').strip()
    if not query:
        return []
    limit = limit or config.RAG_LIMIT

    from google.cloud.firestore_v1.base_vector_query import DistanceMeasure
    from google.cloud.firestore_v1.vector import Vector
    from google.genai import types

    result = await init_gemini().aio.models.embed_content(
        model=config.EMBEDDING_MODEL,
        contents=query,
        config=types.EmbedContentConfig(
            task_type='RETRIEVAL_QUERY',
            output_dimensionality=config.EMBEDDING_DIM,
        ),
    )
    vector = result.embeddings[0].values

    docs = get_db().collection(config.RAG_COLLECTION).find_nearest(
        vector_field='embedding',
        query_vector=Vector(vector),
        distance_measure=DistanceMeasure.COSINE,
        limit=limit,
        distance_result_field='distance',
    ).get()

    hits = []
    for doc in docs:
        data = doc.to_dict() or {}
        data.pop('embedding', None)
        hits.append(data)
    kept = filter_hits(hits, config.RAG_MAX_DISTANCE)
    log.info('RAG: %d ta natija, %d tasi chegaradan o\'tdi', len(hits), len(kept))
    return kept
