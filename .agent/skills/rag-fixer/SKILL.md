---
name: rag-fixer
description: >
  sudqollanma_bot RAG pipeline buglarini aniqlash va tuzatish uchun agent.
  Bu skill faqat bot tomondagi embedding, wiki va vector search xatolarini hal qiladi.
  Flutter (Dart) kodiga tegmaydi.
---

# RAG Fixer — Sud Qo'llanma Bot

## Loyiha konteksti

Bot: `D:\dasturlar\sudqollanma_bot`  
Stack: Python 3.11, aiogram 3.x, google-genai SDK, Firestore Vector Search  
GCP project: `educationapp-4780a`  
Cloud Run URL: `https://sudqollanmabot-660835097321.europe-west4.run.app`

## Asosiy fayllar

| Fayl | Maqsad |
|---|---|
| `services/ai_service.py` | RAG zanjiri: `get_relevant_context()` → wiki → rag_chunks → fallback |
| `services/wiki_service.py` | Wiki qatlami: index match + vector search + build_page() |
| `config.py` | Konstantalar: GEMINI_MODEL, (threshold yo'q — hardcoded) |
| `loader.py` | `get_db()` va `init_gemini()` — lazy singleton |
| `test_wiki_rag.py` | Integratsiya testi |

## TASDIQLANGAN BUGLAR (prioritet tartibi)

### 🔴 BUG-1: Embedding model nomi noto'g'ri (CRITICAL)

**Joylashuv:** `services/ai_service.py:94` va `services/wiki_service.py:146,329`

**Muammo:**
```python
# Hozirgi (xato):
model="gemini-embedding-2"
# config.py da GEMINI_MODEL = "gemini-2.5-flash" → bu model embedding uchun emas!
```

**CLAUDE.md** da aniq ko'rsatilgan:
```
AI embedding: gemini-embedding-exp-03-07 (768 dimension)
```

**Ta'siri:** Agar `gemini-embedding-2` mavjud bo'lmasa → API xatosi; mavjud bo'lsa → 
`rag_chunks` indexi `gemini-embedding-exp-03-07` bilan yozilgan, 
wiki query `gemini-embedding-2` bilan amalga oshiriladi → 
BOSHQA embedding fazosi → cosine natija ma'nosiz → wiki HECH QACHON hit bermaydi.

**Tuzatish:**
```python
# config.py ga qo'shish:
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "gemini-embedding-exp-03-07")
EMBEDDING_DIM = 768

# ai_service.py va wiki_service.py da:
model=config.EMBEDDING_MODEL,
config=types.EmbedContentConfig(output_dimensionality=config.EMBEDDING_DIM)
```

---

### 🔴 BUG-2: Sync blocking embedding call async context ichida (CRITICAL)

**Joylashuv:** `services/wiki_service.py:146,329` va `services/ai_service.py:93`

**Muammo:**
```python
# wiki_service.py:146 — SYNC call (async funksiya ichida):
embedding_result = client.models.embed_content(...)   # ❌ BLOCKING!

# wiki_service.py:329 — ham SYNC:
embedding_result = client.models.embed_content(...)   # ❌ BLOCKING!

# ai_service.py:93 — ham SYNC:
embedding_result = init_gemini().models.embed_content(...)  # ❌ BLOCKING!
```

**Ta'siri:** Bot boshqa requestlarni qabul qila olmaydi embedding chaqiruvi davomida.
`asyncio` event loop bloklanadi → bot javob berish tezligi keskin pasayadi.

**Tuzatish:**
```python
# wiki_service.py va ai_service.py da hamma embed_content ni async qilish:
embedding_result = await client.aio.models.embed_content(
    model=config.EMBEDDING_MODEL,
    contents=query,
    config=types.EmbedContentConfig(output_dimensionality=config.EMBEDDING_DIM),
)
```

---

### 🟡 BUG-3: `config.py` da threshold konstantasi yo'q (MEDIUM)

**Joylashuv:** `services/wiki_service.py:37`

**Muammo:**
```python
COSINE_THRESHOLD = 0.35  # wiki_service.py da hardcoded
# RAG uchun threshold umuman yo'q → 0.25 (hardcoded emas, limit=3 bilan)
```

**Tuzatish — `config.py` ga qo'shish:**
```python
WIKI_HIT_THRESHOLD = float(os.getenv("WIKI_HIT_THRESHOLD", "0.35"))
RAG_LIMIT = int(os.getenv("RAG_LIMIT", "3"))
```

**`wiki_service.py` da:**
```python
COSINE_THRESHOLD = config.WIKI_HIT_THRESHOLD
```

---

### 🟡 BUG-4: `test_wiki_rag.py` da noto'g'ri `.env` yo'li (MEDIUM)

**Joylashuv:** `test_wiki_rag.py:24`

**Muammo:**
```python
# Hozirgi (xato):
_env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sudqollanma_bot", ".env")
# → D:\dasturlar\sudqollanma_bot\sudqollanma_bot\.env  ❌ MAVJUD EMAS!

# To'g'ri:
_env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
# → D:\dasturlar\sudqollanma_bot\.env  ✅
```

---

### 🟢 BUG-5: `knowledge_base` fallback oldin chaqirilmaydi (LOW)

**Joylashuv:** `services/ai_service.py:119-122`

**Muammo:**
```python
if not context_parts:
    logging.warning("Wiki miss → RAG fallback")
    logging.warning("Vector search natija bermadi. Fallback: knowledge_base.")
    return await AIService.get_system_manuals()  # ← Bu to'g'ri
# Lekin: get_system_manuals() dan 'knowledge_base' limit=5 — juda oz
```

**Tuzatish:** `knowledge_base` limit ni `config.py` da markazlashtirish:
```python
KB_FALLBACK_LIMIT = int(os.getenv("KB_FALLBACK_LIMIT", "5"))
```

---

## TUZATISH TARTIBI

1. `config.py` → `EMBEDDING_MODEL`, `EMBEDDING_DIM`, `WIKI_HIT_THRESHOLD`, `RAG_LIMIT`, `KB_FALLBACK_LIMIT` qo'sh
2. `services/wiki_service.py`:
   - `COSINE_THRESHOLD = config.WIKI_HIT_THRESHOLD` (37-qator)
   - `model="gemini-embedding-2"` → `model=config.EMBEDDING_MODEL` (146, 329-qator)
   - `client.models.embed_content` → `await client.aio.models.embed_content` (146, 329-qator)
   - `output_dimensionality=768` → `output_dimensionality=config.EMBEDDING_DIM`
3. `services/ai_service.py`:
   - `model="gemini-embedding-2"` → `model=config.EMBEDDING_MODEL` (94-qator)
   - `init_gemini().models.embed_content` → `await init_gemini().aio.models.embed_content` (93-qator)
   - `output_dimensionality=768` → `output_dimensionality=config.EMBEDDING_DIM`
4. `test_wiki_rag.py`:
   - `.env` yo'lini tuzat (24-qator)

## QAT'IY CHEKLOVLAR

- ❌ `handlers/` fayllariga tegma
- ❌ `firestore_service.py` ga tegma
- ❌ Flutter/Dart kodiga tegma (`D:\dasturlar\b-v22\`)
- ❌ Firestore kolleksiya nomlarini o'zgartirma
- ✅ Har bir fayl o'zgarishidan keyin test natijasini log ga yoz
- ✅ `test_wiki_rag.py` ni ishga tushirib tekshir (agar muhit mavjud bo'lsa)

## CHIQISH FORMATI

Har bir bug tuzatilgandan keyin:
```
🔧 [BUG-N tuzatildi]
📁 Fayl: services/ai_service.py
📍 Qator: 93-94
✏️  O'zgarish: client.models.embed_content → await client.aio.models.embed_content
               model="gemini-embedding-2" → model=config.EMBEDDING_MODEL
```

Oxirida:
```
✅ Barcha buglar tuzatildi
📋 Tuzatilgan fayllar: config.py, services/ai_service.py, services/wiki_service.py, test_wiki_rag.py
⚠️  Qayta deploy: gcloud builds submit kerak
```
