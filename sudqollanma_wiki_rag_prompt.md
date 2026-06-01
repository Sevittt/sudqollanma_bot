# Sud Qo'llanma Bot — LLM Wiki + RAG Integration Prompt

## Kontekst va loyiha holati

Sen `sudqollanma_bot` Telegram botiga LLM Wiki qatlamini qo'shish ustida ishlaysan.
Repo: https://github.com/Sevittt/sudqollanma_bot

Bu bot O'zbekiston sud tizimi xodimlari (kotiblar, hakamlar, IT mutaxassislar) uchun
E-SUD, E-XAT, E-IMZO, MY.SUD.UZ tizimlariga doir IT yordam botdir.

### Stack (o'zgarmaydi)
- **Runtime:** Python, aiogram 3.x, aiohttp (webhook + polling ikkalasi)
- **AI:** google-genai SDK (`init_gemini()` loader.py da)
- **DB:** Firebase Firestore (`get_db()` loader.py da)
- **Embedding model:** `gemini-embedding-exp-03-07`, output_dimensionality=768
- **Generation model:** config.GEMINI_MODEL (Gemini Flash seriyasi)
- **Deploy:** Cloud Run (scale-to-zero), webhook rejimi

### Mavjud Firestore kolleksiyalari
```
rag_chunks/       → {text, embedding, source, ...}
knowledge_base/   → {title, content, category, pdfUrl, ...}
faqs/             → {question, answer, category, difficulty}
users/            → {telegramId, role, courtName, department, ...}
chat_history/     → {telegramId, role, text, timestamp}
```

### Mavjud servislar
```
services/ai_service.py       → AIService: get_relevant_context(), generate_solution(), generate_quiz()
services/firestore_service.py → FirestoreService: get_user(), save_message(), get_recent_messages()
handlers/helpdesk.py         → catch-all text → AIService.generate_solution()
handlers/kb_articles.py      → /maqolalar, /faq — Firestore dan oddiy o'qish
```

---

## Vazifa: LLM Wiki qatlami

### Maqsad
`ai_service.py` dagi `get_relevant_context()` hozir har safar noldan `rag_chunks`
kolleksiyasidan Vector Search qiladi — sintez yo'q, bilim to'planmaydi.

**Qo'shilishi kerak:**
1. `wiki_pages/` kolleksiyasi — LLM yozgan, strukturalangan markdown sahifalar
2. So'rov kelganda avval wikidan qidirish, topilmasa RAG fallback
3. RAG fallback natijasidan fon rejimida wiki sahifa yaratish
4. Wiki sahifalar vaqt o'tishi bilan boyib boradigan bilimlar bazasiga aylanadi

---

## Yaratilishi kerak bo'lgan fayllar

### 1. `services/wiki_service.py` — asosiy wiki mantiq

```python
"""
WikiService — LLM Wiki qatlami.

Firestore kolleksiyasi: wiki_pages
Har bir hujjat:
  - id: slug (masalan: "e-imzo-drayveri-muammolari")
  - title: str
  - content: str (markdown)
  - embedding: Vector(768) — content ning birinchi 2000 belgisidan
  - source_query: str — qaysi savoldan yaratilgan
  - hit_count: int — necha marta ishlatilgan
  - updated_at: SERVER_TIMESTAMP

Mantiq:
  search()     → Vector Search (cosine, limit=1, threshold=0.25)
  build_page() → Gemini bilan markdown yozadi → Firestore ga saqlaydi
  increment_hit() → hit_count ni oshiradi (analytics uchun)
"""
```

**Muhim nuanslar:**
- `build_page()` `asyncio.create_task()` bilan fon rejimida ishlashi shart —
  foydalanuvchi javobni kutmasligi kerak
- Slug: `re.sub(r"[^a-z0-9\u0400-\u04ff\-]", "", text.lower().replace(" ","-"))[:80]`
- Agar slug bo'yicha hujjat allaqachon mavjud bo'lsa — `build_page()` chiqib ketadi
  (duplicate oldini olish)
- `search()` topsa `hit_count` ni `Increment(1)` bilan oshiradi

### 2. `ai_service.py` — `get_relevant_context()` ni yangilash

Hozirgi kod:
```python
# Faqat rag_chunks Vector Search
```

Yangi mantiq:
```python
async def get_relevant_context(user_query, limit=3):
    # 1. WikiService.search(user_query)
    #    → topilsa: qaytaradi
    # 2. Topilmasa: mavjud rag_chunks Vector Search (hozirgi kod)
    # 3. RAG natijasi bor bo'lsa: asyncio.create_task(WikiService.build_page(...))
    # 4. RAG ham bo'sh bo'lsa: get_system_manuals() fallback (mavjud)
```

### 3. `scripts/wiki_builder.py` — bir martalik script

```python
"""
Mavjud knowledge_base kolleksiyasini wiki_pages ga kompilyatsiya qiluvchi script.
Cloud Run da emas, lokal yoki Cloud Shell da ishga tushiriladi.

Jarayon:
  1. knowledge_base dan barcha hujjatlarni oladi
  2. Har biri uchun Gemini bilan wiki sahifa yozadi
  3. Embedding hosil qiladi
  4. wiki_pages ga saqlaydi

Rate limiting: har so'rov orasida 1 soniya kutish (Gemini API limit)
"""
```

### 4. Firestore index (README yoki inline comment sifatida)

```
wiki_pages kolleksiyasida vector index qo'lda yaratilishi kerak:
  Field: embedding
  Dimension: 768
  Google Cloud Console → Firestore → Indexes → Vector indexes
```

---

## Kod sifatiga talablar

### Xatoliklarni boshqarish
- Har bir `WikiService` metodi `try/except` bilan o'ralgan bo'lishi kerak
- Wiki qatlami xato bersaham, asosiy RAG ishlashda davom etishi shart
- Barcha xatolar `logging.error()` bilan yoziladi, exception ko'tarilmaydi
- Cloud Run muhitida `asyncio.create_task()` mavjud loop da ishlashini tekshir

### GCP/Firebase integratsiyasi
- Barcha Firestore operatsiyalar mavjud `get_db()` orqali — yangi connection ochilmaydi
- Barcha Gemini chaqiruvlar mavjud `init_gemini()` orqali — yangi client yaratilmaydi
- `Vector` import: `from google.cloud.firestore_v1.vector import Vector`
- `DistanceMeasure` import: `from google.cloud.firestore_v1.base_vector_query import DistanceMeasure`
- `SERVER_TIMESTAMP` import: `from google.cloud.firestore_v1 import SERVER_TIMESTAMP`
- `Increment` import: `from google.cloud.firestore_v1 import Increment`

### aiogram bilan uyg'unlik
- `build_page()` `asyncio.create_task()` bilan chaqirilganda aiogram event loop bilan
  to'qnashuv bo'lmasligi kerak
- `helpdesk.py` da hech qanday o'zgarish talab qilinmaydi —
  barcha mantiq `ai_service.py` ichida
- Webhook va polling rejimlarining ikkalasida ham ishlashi shart

### Cloud Run spetsifikligi
- Scale-to-zero bo'lganda `asyncio.create_task()` to'liq bajarilmasligi mumkin —
  bu ma'lum risk, acceptable
- Cold start vaqtida wiki index yuklanmaydi — faqat so'rov kelganda ishga tushadi
- Memory: wiki sahifalar Firestore da saqlanadi, xotirada keshlanmaydi (soddalik uchun)

---

## Wiki sahifa formati (Gemini uchun prompt shabloni)

```
Quyidagi sud tizimi IT qo'llanmasi matnlaridan '{topic}' mavzusida
wiki sahifa yoz. FAQAT berilgan manbada bor narsani yoz, o'ylab topma.

Tuzilma:
## {topic}
### Asosiy tushuntirish
### Qadamlar (agar amaliy jarayon bo'lsa)
### Tez-tez uchraydigan muammolar va yechimlari
### Bog'liq mavzular

Til: O'zbek (lotin)
Uslub: Qisqa, aniq, sud xodimlariga tushunarli
Hajm: 300-600 so'z

Manbalar:
{rag_context[:4000]}
```

---

## Bosqichma-bosqich amalga oshirish tartibi

### Bosqich 1 — Infratuzilma (xavfsiz)
1. Firestore da `wiki_pages` kolleksiyasi uchun vector index yaratish
   (Console → Firestore → Indexes → Create vector index)
2. `services/wiki_service.py` yaratish — hali hech yerga ulanmaydi
3. Unit test: bitta `build_page()` chaqirib, Firestore da yozilganini tekshirish

### Bosqich 2 — Integratsiya
4. `ai_service.py` dagi `get_relevant_context()` ni yangilash
5. Lokal polling rejimida sinash: bir necha savol berish, wiki_pages da yozilganini tekshirish
6. `scripts/wiki_builder.py` bilan mavjud `knowledge_base` dan wiki yaratish

### Bosqich 3 — Deploy va kuzatish
7. Cloud Run ga deploy
8. Bir hafta davomida `wiki_pages` kolleksiyasidagi `hit_count` larni kuzatish
9. Threshold (0.25) ni haqiqiy savollarga qarab sozlash

---

## Muvaffaqiyat mezonlari

- Birinchi haftadan keyin `wiki_pages` da kamida 20 ta sahifa yaratilgan
- Takroriy savollar (masalan "E-IMZO ishlamayapti") wikidan javob oladi (hit_count > 1)
- Hech qanday regression yo'q: mavjud `/quiz`, `/maqolalar`, `/faq` buyruqlari
  oldingiday ishlaydi
- `ai_service.py` dagi `generate_quiz()` o'zgarmaydi
- Cloud Run loglarda `Wiki hit ✅` va `Wiki miss → RAG fallback` ko'rinadi

---

## Nima o'zgarmaydi (muhim chegara)

- `handlers/` — hech qaysi handler o'zgarmaydi
- `services/firestore_service.py` — o'zgarmaydi
- `loader.py`, `config.py` — o'zgarmaydi
- `requirements.txt` — yangi paket kerak emas (barcha importlar allaqachon bor)
- Mavjud Firestore kolleksiyalar (`rag_chunks`, `knowledge_base`, `faqs`,
  `users`, `chat_history`) — o'zgarmaydi, faqat o'qiladi

---

## Qo'shimcha: Kelajakdagi kengaytmalar (hozir amalga oshirilmaydi)

Bu prompt doirasiga kirmaydi, lekin keyingi bosqich uchun eslatma:
- `wiki_pages` da `related: [slug1, slug2]` maydoni — o'zaro havolalar
- `/wiki` buyrug'i — foydalanuvchi to'g'ridan-to'g'ri wiki qidirishi uchun
- Wiki sahifalarni admin tomonidan tahrirlash imkoniyati
- `hit_count` asosida "eng mashhur maqolalar" ro'yxati
