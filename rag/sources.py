"""RAG manbalari. Har bir manba bir xil `Chunk` ro'yxatini qaytaradi.

Manbalar:
  dars      — DARS kurslarining markdown fayllari (lokal papka)
  qollanma  — data/knowledge.md (75 ta rasmiy PDF qo'llanmadan yig'ilgan)
  faq       — Firestore 'faqs'
  kb        — Firestore 'knowledge_base' (DARS'dan ko'chirilgan 'dars' toifasidan tashqari)
"""
from __future__ import annotations

import hashlib
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable

from rag.chunker import chunk_markdown, chunk_plain, clean_heading

BOT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DARS_DIR = Path(os.getenv('RAG_DARS_DIR', r'C:\Users\Arxiv\Documents\DARS'))
DEFAULT_KNOWLEDGE_MD = Path(os.getenv('RAG_KNOWLEDGE_MD', str(BOT_ROOT / 'data' / 'knowledge.md')))

# DARS ichidagi indekslanmaydigan papkalar
DARS_SKIP_DIRS = ('99. Xizmat fayllari va arxiv', 'output')

DARS_MODULES = (
    ('1. Windows', '1-modul: Windows va Ofis'),
    ('2. ERI', '2-modul: ERI va Brauzer'),
    ('3. Axborot', '3-modul: Axborot xavfsizligi'),
    ('4. Oliy sud', '4-modul: Oliy sud axborot tizimlari va EDO'),
    ('5. VKA', '5-modul: VKA va audio-video'),
    ('5_modul', '5-modul: VKA va audio-video'),
)


@dataclass(frozen=True)
class Chunk:
    id: str
    source: str
    doc_id: str
    doc_title: str
    section: str
    text: str
    category: str = ''

    def embed_input(self) -> str:
        """Embedding'ga yuboriladigan matn: sarlavha konteksti + bo'lak."""
        header = self.section or self.doc_title
        return f'{header}\n\n{self.text}' if header else self.text


def doc_slug(title: str) -> str:
    """Barqaror, Firestore id'ga yaroqli qisqa slug (kirill nomlarda ham)."""
    ascii_part = re.sub(r'[^a-z0-9]+', '-', title.lower()).strip('-')[:40].strip('-')
    digest = hashlib.sha1(title.encode('utf-8')).hexdigest()[:8]
    return f'{ascii_part}-{digest}' if ascii_part else digest


def _number(source: str, doc_id: str, doc_title: str, pieces, category: str = '') -> list[Chunk]:
    return [
        Chunk(id=f'{source}:{doc_id}:{n}', source=source, doc_id=doc_id, doc_title=doc_title,
              section=p.section, text=p.text, category=category)
        for n, p in enumerate(pieces)
    ]


# ── dars ─────────────────────────────────────────────────────────────────────

def _dars_module(rel: str) -> str:
    for marker, name in DARS_MODULES:
        if marker in rel:
            return name
    return 'Umumiy'


def load_dars(root: Path = DEFAULT_DARS_DIR) -> list[Chunk]:
    if not root.exists():
        raise FileNotFoundError(f'DARS papkasi topilmadi: {root}')
    chunks: list[Chunk] = []
    for path in sorted(root.rglob('*.md')):
        rel = str(path.relative_to(root))
        if any(skip in rel for skip in DARS_SKIP_DIRS):
            continue
        module = _dars_module(rel)
        title = path.stem.replace('_', ' ')
        pieces = chunk_markdown(path.read_text(encoding='utf-8'), root_title=module)
        chunks += _number('dars', doc_slug(rel), title, pieces, category=module)
    return chunks


# ── qollanma (knowledge.md) ──────────────────────────────────────────────────

_BOOK = re.compile(r'^## 📖\s*(.+)$', re.MULTILINE)


def _book_title(raw: str) -> str:
    title = clean_heading(raw)
    return re.sub(r'\s+PDF$', '', title).strip()


def load_qollanma(path: Path = DEFAULT_KNOWLEDGE_MD) -> list[Chunk]:
    text = path.read_text(encoding='utf-8')
    matches = list(_BOOK.finditer(text))
    chunks: list[Chunk] = []
    for i, match in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[match.end():end]
        body = re.sub(r'^\*\(Manba:.*\)\*\s*$', '', body, flags=re.MULTILINE)
        body = re.sub(r'^-{3,}\s*$', '', body, flags=re.MULTILINE)
        title = _book_title(match.group(1))
        pieces = chunk_markdown(body, root_title=title)
        chunks += _number('qollanma', doc_slug(title), title, pieces, category='qollanma')
    return chunks


# ── Firestore manbalari ──────────────────────────────────────────────────────

def load_faqs(db) -> list[Chunk]:
    chunks: list[Chunk] = []
    for doc in db.collection('faqs').stream():
        data = doc.to_dict() or {}
        question = (data.get('question') or '').strip()
        answer = (data.get('answer') or '').strip()
        if not question or not answer:
            continue
        text = f'Savol: {question}\nJavob: {answer}'
        pieces = chunk_plain(text, section=question) or []
        chunks += _number('faq', doc.id, question, pieces, category=data.get('category', ''))
    return chunks


def load_kb_articles(db) -> list[Chunk]:
    chunks: list[Chunk] = []
    for doc in db.collection('knowledge_base').stream():
        data = doc.to_dict() or {}
        # 'dars' toifasi DARS markdown'idan ko'chirilgan nusxa — 'dars' manbasi bilan takrorlanadi
        if data.get('category') == 'dars':
            continue
        title = (data.get('title') or doc.id).strip()
        content = data.get('content') or data.get('text') or ''
        pieces = chunk_markdown(content, root_title=title)
        chunks += _number('kb', doc.id, title, pieces, category=data.get('category', ''))
    return chunks


LOCAL_SOURCES: dict[str, Callable[[], list[Chunk]]] = {
    'dars': load_dars,
    'qollanma': load_qollanma,
}
FIRESTORE_SOURCES: dict[str, Callable[[object], list[Chunk]]] = {
    'faq': load_faqs,
    'kb': load_kb_articles,
}
ALL_SOURCES = tuple(LOCAL_SOURCES) + tuple(FIRESTORE_SOURCES)


def load(names: Iterable[str], db=None) -> dict[str, list[Chunk]]:
    out: dict[str, list[Chunk]] = {}
    for name in names:
        if name in LOCAL_SOURCES:
            out[name] = LOCAL_SOURCES[name]()
        elif name in FIRESTORE_SOURCES:
            if db is None:
                raise ValueError(f"'{name}' manbasi uchun Firestore ulanishi kerak")
            out[name] = FIRESTORE_SOURCES[name](db)
        else:
            raise ValueError(f"Noma'lum manba: {name}. Mavjudlari: {', '.join(ALL_SOURCES)}")
    return out
