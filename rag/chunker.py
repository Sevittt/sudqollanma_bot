"""Barcha manbalar uchun bitta bo'laklash qoidasi (tashqi kutubxonalarsiz)."""
from __future__ import annotations

import re
from dataclasses import dataclass

MAX_CHARS = 1200
OVERLAP_CHARS = 150
MIN_CHARS = 50

_HEADER = re.compile(r'^(#{1,3})\s+(.*)$')


@dataclass(frozen=True)
class Piece:
    section: str  # sarlavha zanjiri: "A › B › C"
    text: str


def clean_text(text: str) -> str:
    text = text.replace('\r\n', '\n').replace('\r', '\n')
    text = re.sub(r'[ \t]+', ' ', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def clean_heading(line: str) -> str:
    title = re.sub(r'[*_`]', '', line).strip()
    return title.strip('# ').strip()


def split_long(text: str, max_chars: int = MAX_CHARS, overlap: int = OVERLAP_CHARS) -> list[str]:
    """Matnni paragraf chegaralarida ≤ max_chars bo'laklarga bo'ladi.

    Keyingi bo'lak oldingisining oxirgi ~overlap belgisidan boshlanadi, shunda
    chegarada qolgan fikr ikkala bo'lakda ham ko'rinadi. Bitta paragraf
    max_chars dan uzun bo'lsa, u so'z chegarasida kesiladi.
    """
    text = clean_text(text)
    if len(text) <= max_chars:
        return [text] if text else []

    units: list[str] = []
    for para in text.split('\n\n'):
        para = para.strip()
        while len(para) > max_chars:
            cut = para.rfind(' ', 0, max_chars)
            cut = cut if cut > max_chars // 2 else max_chars
            units.append(para[:cut].strip())
            para = para[cut:].strip()
        if para:
            units.append(para)

    pieces: list[str] = []
    current = ''
    for unit in units:
        candidate = f'{current}\n\n{unit}' if current else unit
        if len(candidate) <= max_chars:
            current = candidate
            continue
        if current:
            pieces.append(current)
            tail = current[-overlap:] if overlap else ''
            space = tail.find(' ')
            tail = tail[space + 1:] if 0 <= space < len(tail) - 1 else tail
            current = f'{tail}\n\n{unit}' if tail and len(tail) + len(unit) + 2 <= max_chars else unit
        else:
            current = unit
    if current:
        pieces.append(current)
    return pieces


def chunk_markdown(text: str, root_title: str = '') -> list[Piece]:
    """Markdown'ni #–### sarlavhalar bo'yicha bo'ladi, sarlavha zanjirini saqlaydi."""
    stack: list[tuple[int, str]] = []
    sections: list[tuple[str, list[str]]] = []
    lines: list[str] = []

    def path() -> str:
        names = [root_title] if root_title else []
        names += [name for _, name in stack if name]
        return ' › '.join(names)

    def flush():
        if lines:
            sections.append((path(), lines.copy()))
            lines.clear()

    in_code = False
    for line in clean_text(text).split('\n'):
        if line.strip().startswith('```'):
            in_code = not in_code
        match = None if in_code else _HEADER.match(line)
        if match:
            flush()
            level, name = len(match.group(1)), clean_heading(match.group(2))
            while stack and stack[-1][0] >= level:
                stack.pop()
            stack.append((level, name))
            continue
        lines.append(line)
    flush()

    pieces: list[Piece] = []
    for section, body in sections:
        for part in split_long('\n'.join(body)):
            if len(part) >= MIN_CHARS:
                pieces.append(Piece(section=section, text=part))
    return pieces


def chunk_plain(text: str, section: str = '') -> list[Piece]:
    return [Piece(section=section, text=p) for p in split_long(text) if len(p) >= MIN_CHARS]
