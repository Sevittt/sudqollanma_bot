"""Toza (I/O'siz) mantiq: takrorlarni olib tashlash, hash va sinxronlash rejasi."""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field

from rag.sources import Chunk


def content_hash(chunk: Chunk, model: str, dim: int) -> str:
    payload = f'{model}|{dim}|{chunk.embed_input()}'
    return hashlib.sha256(payload.encode('utf-8')).hexdigest()


def _norm(text: str) -> str:
    return re.sub(r'\s+', ' ', text).strip().lower()


def dedupe(chunks: list[Chunk]) -> tuple[list[Chunk], list[Chunk]]:
    """Bir xil matnli bo'laklardan faqat birinchisini qoldiradi (manbalar tartibi muhim)."""
    seen: set[str] = set()
    ids: set[str] = set()
    kept: list[Chunk] = []
    dropped: list[Chunk] = []
    for chunk in chunks:
        key = _norm(chunk.text)
        if key in seen or chunk.id in ids:
            dropped.append(chunk)
            continue
        seen.add(key)
        ids.add(chunk.id)
        kept.append(chunk)
    return kept, dropped


@dataclass
class SyncPlan:
    upsert: list[Chunk] = field(default_factory=list)
    unchanged: list[Chunk] = field(default_factory=list)
    delete: list[str] = field(default_factory=list)


def plan_sync(
    chunks: list[Chunk],
    existing: dict[str, dict],
    sources: set[str],
    model: str,
    dim: int,
) -> SyncPlan:
    """Qaysi bo'lakni qayta embed qilish, qaysini o'chirish kerakligini aniqlaydi.

    existing: {doc_id: {'hash': ..., 'source': ...}} — kolleksiyadagi joriy holat.
    Faqat shu safar yig'ilgan manbalarga tegishli eski hujjatlar o'chiriladi.
    """
    plan = SyncPlan()
    new_ids = set()
    for chunk in chunks:
        new_ids.add(chunk.id)
        old = existing.get(chunk.id)
        if old and old.get('hash') == content_hash(chunk, model, dim):
            plan.unchanged.append(chunk)
        else:
            plan.upsert.append(chunk)
    plan.delete = sorted(
        doc_id for doc_id, meta in existing.items()
        if doc_id not in new_ids and meta.get('source') in sources
    )
    return plan
