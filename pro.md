# VAZIFA: RAG'ni ikki kod bazasida birlashtirish va tuzatish

## KONTEKST — hozirgi haqiqiy holat (kodni o'qib tasdiqlangan)

Ikkita kod bazasi bitta Firestore'ni (`educationapp-4780a`) baham ko'radi:

### Python bot (`sudqollanma_bot`) — Cloud Run, aiogram 3.x, google-genai
- `services/ai_service.py` — RAG zanjiri, Gemini generatsiya
- `services/wiki_service.py` — LLM Wiki qatlami (Vector Search + Adversarial Review)
- `services/firestore_service.py` — Barcha Firestore CRUD
- `config.py` — `.env` o'zgaruvchilari (threshold va embedding model nomi YO'Q — bu muammo)
- `main.py` — aiohttp server: `/webhook` yo'li bor, lekin `/answer` HTTP endpoint yo'q

### Flutter app (`sud_qollanma`) — alohida repo
- `firebase_ai` + Firebase Extension `ext-firestore-vector-search-queryCallable`
- Extension qaysi embedding modelini ishlatishi noaniq (tasdiqlash kerak)

---

## ANIQLANGAN MUAMMOLAR (koddan aniq topilgan)

### 1. Embedding model nomidagi chalkashlik
`ai_service.py` (97-satr) va `wiki_service.py` (146, 329-satrlar) ikkalasi ham:
```python
model="gemini-embedding-2"
```
ishlatadi. Lekin `CLAUDE.md` da `gemini-embedding-exp-03-07` deb yozilgan.
**Amalda qaysi model ishlatilishi aniq emas** — config.py da `EMBEDDING_MODEL` konstantasi yo'q.

### 2. Threshold faqat wiki_service.py da bor
`wiki_service.py` → `COSINE_THRESHOLD = 0.35` (36-satr).
`ai_service.py` da esa `rag_chunks` vector search natijasida threshold filtri umuman yo'q —
hamma natija qaytariladi, hatto uzoq o'xshashlik bo'lsa ham.

### 3. RAG mantig'i ikkita joyda yozilgan
- `ai_service.py::get_relevant_context()` → wiki → rag_chunks → knowledge_base
- Flutter app → Firebase Extension callable (to'liq boshqa yo'l)

### 4. knowledge_base fallback nosozligi
`ai_service.py` 119-121 satirlarda `context_parts` bo'sh bo'lsa:
```python
logging.warning("Wiki miss → RAG fallback")
logging.warning("Vector search natija bermadi. Fallback: knowledge_base.")
return await AIService.get_system_manuals()
```
Bu log noto'g'ri — bu aslida `rag_chunks` miss, wiki miss allaqachon oldin sodir bo'lgan.

### 5. HTTP /answer endpoint yo'q
`main.py` da faqat `/webhook` yo'li bor. App HTTP orqali chaqira oladigan `/answer` endpoint
hali mavjud emas — bu to'liq yaratilishi kerak bo'lgan yangi komponent.

### 6. config.py da markazlashmagan konstantalar
`EMBEDDING_MODEL`, `WIKI_HIT_THRESHOLD`, `RAG_HIT_THRESHOLD` config.py da yo'q,
modul ichida qattiq yozilgan.

---

## MAQSAD (yagona haqiqat manbai)

Bitta Python "answer core" moduli (`services/answer_core.py`) yaratilib:
- Bot uni **to'g'ridan funksiya chaqiruvi** (in-process) bilan ishlatadi
- App uni **HTTP POST /answer** endpoint orqali chaqiradi
- **Bitta embedding modeli** (config.py dan olinadi) — ham yozish, ham query uchun
- **Bitta wiki-lookup** (vector cosine + index, bitta threshold)
- App'dan Firebase Extension RAG yo'lini olib tashla

---

## QAT'IY SHARTLAR

- Ishlab turgan botni buzma. `helpdesk.py` → `AIService.generate_solution()` xulqi o'zgarmasin.
- Hamma joyda **BITTA embedding modeli**. Hujjat va query bir xil `config.EMBEDDING_MODEL` bilan.
- **Taxmin qilma** — avval konfiguratsiyani o'qib tasdiqla (ayniqsa Firebase Extension modeli).
- Barcha konstantalar (`threshold`, `embedding model nomi`) `config.py` da markazlashsin.
- `CLAUDE.md` ni yangilab tur — har fazadan keyin arxitektura o'zgarishlarini aks ettir.

---

## FAZALAR — har fazadan keyin TO'XTA va hisobot ber, keyingisiga o'tma

### Faza 0 — Diagnostika (HECH NARSA o'zgartirma, faqat hisobot)

Quyidagilarni aniqlang va hisobot ber:

**A. Firebase Extension sozlamasi:**
- Firebase Console → Extensions → `ext-firestore-vector-search` → Configuration
- Qaysi kolleksiyani qidiradi? (`rag_chunks` yoki `search_index` yoki boshqa?)
- Qaysi embedding model ishlatiladi? (API so'rov parametrlarini ko'r)
- Agar aniqlay olmasang — menga so'rov ber, console skrinshot kerak bo'ladi.

**B. Hozirgi embedding model tasdiqlash:**
- `ai_service.py` va `wiki_service.py` da `"gemini-embedding-2"` ishlatilmoqda
- `CLAUDE.md` da `gemini-embedding-exp-03-07` yozilgan — qaysi biri haqiqiy?
- `rag_chunks` kolleksiyasidagi hujjatlar qaysi model bilan yuklangan?
  (`scripts/upload_knowledge.py` faylini o'qi va model nomini aniqlang)
- Embedding o'lchami: 768 dim — tasdiqlang

**C. Hozirgi threshold holati:**
- `wiki_service.py::COSINE_THRESHOLD = 0.35` ✅ mavjud
- `ai_service.py` → `rag_chunks` search'da threshold YO'Q — tasdiqlang

**D. Topilmalarni yozib, TO'XTA.**

---

### Faza 1 — config.py markazlashtirish + answer_core yaratish

**config.py ga qo'shish:**
```python
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "gemini-embedding-2")
EMBEDDING_DIM   = int(os.getenv("EMBEDDING_DIM", 768))
WIKI_HIT_THRESHOLD = float(os.getenv("WIKI_HIT_THRESHOLD", 0.35))
RAG_HIT_THRESHOLD  = float(os.getenv("RAG_HIT_THRESHOLD", 0.40))
```

**`services/answer_core.py` yaratish:**
```
embed(text) → config.EMBEDDING_MODEL + config.EMBEDDING_DIM
search(query, role, lang, image?) →
  1. wiki_pages Vector Search (WIKI_HIT_THRESHOLD) — wiki qatlami
  2. miss → rag_chunks Vector Search (RAG_HIT_THRESHOLD, limit=3)
  3. miss → knowledge_base fallback
  4. RAG hit bo'lsa → fon rejimida WikiService.build_page()
  5. Gemini generate_content (SYSTEM_INSTRUCTION + user_context)
  → qaytarish: {answer: str, sources: list, wiki_slug: str|None}
```

**HTTP endpoint `main.py` ga qo'shish:**
```
POST /answer
  Body: {query, role?, lang?, telegram_id?}
  Response: {answer, sources, wiki_slug}
  Auth: Bearer token (config.API_SECRET_KEY)
```

Bot `helpdesk.py` → `answer_core.search()` ni to'g'ridan chaqiradi (HTTP emas).

---

### Faza 2 — Botni answer_core ga ulash

- `ai_service.py::generate_solution()` → `answer_core.search()` ni chaqirsin
- `ai_service.py::get_relevant_context()` → `answer_core` ga ko'chirilgan mantiq
- `wiki_service.py` o'zgarishsiz qoladi (answer_core undan foydalanadi)
- Xulq o'zgarmasin: foydalanuvchi uchun bir xil javob formatida

---

### Faza 3 — App'ni ulash, extension yo'lini olib tashlash

- Flutter app: `RagService` / `SearchRemoteDataSource` (extension `queryCallable`) o'rniga
  `/answer` endpointga HTTPS POST chaqiruvi
- Dart `WikiService` slug mantig'ini olib tashla (Python tomon hal qiladi)
- `ext-firestore-vector-search` extensionini RAG yo'lidan chiqar

---

### Faza 4 — Tekshiruv

- Bir xil savol → bot va app **BIR XIL** kontekst/javob qaytarsin
- Slug variantlari (`"E-IMZO drayveri"` / `"E-IMZO drayver xatosi"`) bitta wiki keshga tushsin
- Query va hujjat embedding'i bir xil model bilan ekanini `scripts/` orqali tasdiqlang
- `rag_chunks` va `wiki_pages` da qaysi modellar bilan yozilganini tekshir

---

## CHIQISH FORMATI

Har fazadan keyin:
1. Nima o'zgardi va nega
2. Tegilgan fayllar ro'yxati (fayl nomi + o'zgartirilgan satrlar diapazoni)
3. Xulq o'zgardimi? (ha/yo'q + isboti)
4. Keyin **TO'XTA** va mening tasdiqimni kut