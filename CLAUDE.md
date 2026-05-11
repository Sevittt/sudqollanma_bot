# Sud qo'llanma Bot — CLAUDE.md

O'zbekiston sud tizimi xodimlari uchun AI-powered Telegram boti. Flutter mobil ilovasining ("Sud qo'llanma") Telegram ekotizim qismi.

---

## Loyiha haqida

**Maqsad:** Sud xodimlariga (E-SUD, E-XAT, JIB.SUD.UZ, E-IMZO, VKS) IT muammolarida qadam-baqadam yordam berish va raqamli savodxonligini oshirish.

**Muhim cheklov:** Bot faqat IT/texnik savollarga javob beradi — yuridik maslahat bermaydi.

---

## Tech Stack

| Komponent | Texnologiya |
|---|---|
| Dasturlash tili | Python 3.11+ |
| Bot framework | Aiogram 3.x (async) |
| Ma'lumotlar bazasi | Firebase Firestore (NoSQL) |
| AI generatsiya | Google Gemini (`gemini-3.1-flash-lite-preview`) |
| AI embedding | `gemini-embedding-exp-03-07` (768 dimension) |
| Vektor qidiruv | Firestore Vector Search (Cosine, `rag_chunks` kolleksiyasi) |
| Infratuzilma | Google Cloud Run, region: `europe-west4` |
| GCP project | `educationapp-4780a` |
| Cloud Run URL | `https://sudqollanmabot-660835097321.europe-west4.run.app` |
| Artifact Registry | `europe-west4-docker.pkg.dev/educationapp-4780a/cloud-run-source-deploy/sudqollanmabot` |

---

## Fayl tuzilmasi

```
sudqollanma_bot/
├── main.py                  # Entry point: polling/webhook boshqaruvi
├── loader.py                # Bot, Dispatcher, Firebase, Gemini lazy init
├── config.py                # .env o'zgaruvchilarini yuklash
├── Dockerfile               # Cloud Run uchun konteyner (python:3.11-slim, port 8080)
├── requirements.txt         # aiogram, firebase-admin, google-genai, aiohttp, reportlab, Pillow
├── firestore.indexes.json   # Firestore composite index ta'riflari
├── serviceAccountKey.json   # Firebase service account (local dev va Cloud Run uchun)
│
├── handlers/                # Aiogram routerlar (controllers)
│   ├── __init__.py
│   ├── middleware.py        # ThrottlingMiddleware (1msg/s), ErrorHandlerMiddleware
│   ├── onboarding.py        # /start, rol tanlash, sud tanlash, 3-savollik kompetensiya testi
│   ├── commands.py          # /help, /profile, /about, /reset
│   ├── helpdesk.py          # AI catch-all handler (oxirgi router bo'lishi SHART)
│   ├── quizzes.py           # /quiz, Firestore testlari, XP hisoblash, quiz_attempts saqlash
│   ├── stats.py             # /stats — foydalanuvchi statistikasi
│   ├── resources.py         # /qollanma — Firestore 'resources' kolleksiyasi
│   ├── kb_articles.py       # /maqolalar, /faq — 'knowledge_base' va 'faqs' kolleksiyalari
│   └── courses.py           # 🎓 Kurslar — 'courses' kolleksiyasi, modul/dars navigatsiyasi
│
├── services/
│   ├── ai_service.py        # Gemini API, RAG (vector search), prompt, suhbat tarixi
│   └── firestore_service.py # Barcha Firestore CRUD amallari
│
├── scripts/                 # ETL/baza to'ldirish (production containerga kirmaydi)
│   ├── upload_knowledge.py  # PDF/MD → embedding → rag_chunks kolleksiyasiga yuklash
│   ├── pdf_to_md.py         # PDF fayllarni Markdown ga aylantirish
│   ├── populate_*.py        # Firestore kolleksiyalarini to'ldirish skriptlari
│   └── generate_certificate.py
│
├── data/                    # Lokal bilimlar bazasi (deploy ga KIRMAYDI — .gcloudignore)
│   ├── edo-sud-uz/          # E-DO PDF yo'riqnomalar
│   ├── jib-sud-uz/          # JIB.SUD.UZ PDF + video yo'riqnomalar
│   ├── adolat-sud-uz/       # ADOLAT tizimi PDF yo'riqnomalar
│   ├── e-imzo/              # E-IMZO PDF yo'riqnomalar
│   ├── books/               # Umumiy IT kitoblar (Excel, Windows, Office, printer)
│   └── xatolik-vids/        # Xatolik uchun demo videolar
│
└── .agent/skills/           # Agent ko'rsatmalari (bu fayl ham shu yerda)
    ├── gcloud/SKILL.md      # Cloud Run deploy yo'riqnomasi
    └── ...
```

---

## Muhit sozlamalari (.env)

```env
BOT_TOKEN=<Telegram BotFather tokeni>
GEMINI_API_KEY=<Google AI Studio API kaliti>
GEMINI_MODEL=gemini-3.1-flash-lite-preview
FIREBASE_CREDENTIALS=serviceAccountKey.json
WEBHOOK_URL=https://sudqollanmabot-660835097321.europe-west4.run.app  # bo'sh = polling
ADMIN_IDS=123456789,987654321
```

**Lokal test:** `WEBHOOK_URL=` bo'sh qoldirilsa bot polling rejimida ishlaydi.

---

## Firestore kolleksiyalari

| Kolleksiya | Maqsad |
|---|---|
| `users` | Foydalanuvchilar (telegram_id, phoneNumber, xp, level, role, courtName, ...) |
| `conversations` | Suhbat tarixi (RAG uchun context) |
| `rag_chunks` | Vektorlashtirilgan bilimlar bazasi (text + embedding[768]) |
| `knowledge_base` | Maqolalar (title, content, category, systemId) |
| `faqs` | Ko'p so'raladigan savollar (question, answer, category, difficulty) |
| `quizzes` | Test topiklari → subcollection: `questions` |
| `quiz_attempts` | Test natijalari (Flutter ilova bilan sinxron) |
| `resources` | PDF/fayl havolalari (title, url, type) |
| `courses` | Kurslar (modules → lessons nested array) |
| `courts` | Sudlar ro'yxati (courtName, courtType, region) |

---

## Handlers tartibi (muhim!)

`main.py` da router registratsiyasi tartibi qat'iy:

```python
dp.include_router(onboarding.router)   # 1. /start, contact
dp.include_router(commands.router)     # 2. /help, /profile, /about, /reset
dp.include_router(stats.router)        # 3. /stats
dp.include_router(quizzes.router)      # 4. /quiz
dp.include_router(resources.router)    # 5. /qollanma
dp.include_router(kb_articles.router)  # 6. /maqolalar, /faq
dp.include_router(courses.router)      # 7. 🎓 Kurslar
dp.include_router(helpdesk.router)     # 8. OXIRGI — catch-all text handler
```

`helpdesk.router` **har doim oxirgi** bo'lishi shart, aks holda barcha matnni AI ga yuboradi.

---

## AI va RAG arxitekturasi

1. Foydalanuvchi savol yozadi
2. `ai_service.py → get_relevant_context()` → savol `gemini-embedding-exp-03-07` orqali vektorizatsiya qilinadi (768 dim)
3. `rag_chunks` kolleksiyasida Firestore Vector Search (Cosine) → Top-3 chunk topiladi
4. Chunk + foydalanuvchi konteksti (ism, lavozim, sud) + suhbat tarixi → Gemini ga yuboriladi
5. `SYSTEM_INSTRUCTION` — "Raqamli Mentor" roli, o'zbekona empatiya, faqat IT savollarga javob

**Fallback:** Vector search natija bermasa → `knowledge_base` kolleksiyasidan oddiy o'qish.

---

## Bilimlar bazasini yangilash

```powershell
# 1. PDF → MD
cd sudqollanma_bot
python scripts/pdf_to_md.py

# 2. MD → Firestore rag_chunks (embedding bilan)
python scripts/upload_knowledge.py
```

Firestore Vector Search index (bir marta yaratiladi):
```powershell
cmd /c "gcloud alpha firestore indexes composite create --project=educationapp-4780a --collection-group=knowledge_base --query-scope=COLLECTION --field-config=field-path=embedding,vector-config='{\"dimension\":\"768\",\"flat\":\"{}\"}'"
```

---

## Cloud Run Deploy

### 1-bosqich: Container build

```powershell
cmd /c "gcloud builds submit --tag europe-west4-docker.pkg.dev/educationapp-4780a/cloud-run-source-deploy/sudqollanmabot:stable"
```

> `.gcloudignore` da `data/`, `*.pdf`, `*.xlsx`, `populate_*.py` bo'lishi SHART — aks holda 1.3 GB fayl yuboriladi.

### 2-bosqich: Deploy (tokenlarni .env dan olish)

```powershell
cmd /c "gcloud run deploy sudqollanmabot --image europe-west4-docker.pkg.dev/educationapp-4780a/cloud-run-source-deploy/sudqollanmabot:stable --region europe-west4 --memory 1Gi --timeout 600 --concurrency 80 --service-account 660835097321-compute@developer.gserviceaccount.com --set-env-vars BOT_TOKEN=<BOT_TOKEN>,GEMINI_API_KEY=<GEMINI_API_KEY>,GEMINI_MODEL=gemini-3.1-flash-lite-preview,WEBHOOK_URL=https://sudqollanmabot-660835097321.europe-west4.run.app,FIREBASE_CREDENTIALS=serviceAccountKey.json"
```

**Muhim parametrlar:**
- `--memory 1Gi` — Firebase + Gemini uchun minimum
- `--timeout 600` — startup uchun etarli vaqt
- `--region europe-west4` — barqaror region

### Loglarni ko'rish

```powershell
cmd /c "gcloud run services logs read sudqollanmabot --region europe-west4 --limit 20"
```

### IAM xatoligi (`Container import failed`) bo'lsa

```powershell
cmd /c "gcloud projects add-iam-policy-binding educationapp-4780a --member=serviceAccount:660835097321-compute@developer.gserviceaccount.com --role=roles/artifactregistry.reader --condition=None"
cmd /c "gcloud projects add-iam-policy-binding educationapp-4780a --member=serviceAccount:service-660835097321@serverless-robot-prod.iam.gserviceaccount.com --role=roles/artifactregistry.reader --condition=None"
```

---

## Xavfsizlik

- **Identity spoofing:** `message.contact.user_id == message.from_user.id` tekshiruvi (`onboarding.py`)
- **API kalitlar:** Hech qachon kod ichiga yozilmaydi — faqat `.env` va Cloud Run env vars
- **Foydalanuvchi ma'lumotlari:** Faqat Firestore da, lokal faylda yo'q

---

## Kelajak rejalari (Roadmap)

1. **Ticketing System** — AI javob topa olmasa, IT bo'limiga ariza yuborish
2. **Video Preview** — Qidirilgan tizim bo'yicha video preview + ilovaga yo'naltirish
3. **Big Data Analytics** — Qaysi sudlarda qanday muammolar ko'p — dashboard
4. **Flutter bilan birlashtirish** — Bot funksiyalarini ilovaga ko'chirish
