# 🛂 Sud Qo'llanma Bot - Loyiha Pasporti (Project Passport)

## 📌 1. Umumiy Ma'lumot
- **Loyiha nomi:** Sud Qo'llanma Bot ("SUD IT MENTOR")
- **Missiyasi:** O'zbekiston sud tizimi xodimlariga (tuman, shahar, viloyat va Oliy sud) IT va raqamli tizimlardan (E-SUD, E-XAT, JIB.SUD.UZ, E-IMZO, VKS) foydalanishda texnik va operatsion yordam berish hamda ularning raqamli savodxonligini oshirish.
- **Tizimdagi roli:** Yuridik maslahatchi emas, balki **"Raqamli Murabbiy va Texnik Ko'makchi"**. Asosiy "Sud Qo'llanma" mobil ilovasining ekotizim qismi hisoblanadi.

---

## 🏗 2. Arxitektura va Texnologik Stek (Tech Stack)
- **Dasturlash tili:** Python 3.11+
- **Bot Framework:** Aiogram 3.x (Asinxron Telegram bot)
- **Ma'lumotlar Bazasi:** Firebase Firestore (NoSQL) — Mobil ilova (Flutter) bilan to'liq sinxronlashgan yagona baza.
- **Sun'iy Intelekt (AI) & RAG:** Google Gemini (Generative AI) 
  - Generatsiya uchun: `gemini-3.0-flash` yoki `gemini-2.5-flash`
  - Vektor (Embedding) uchun: `gemini-embedding-001`
- **Infratuzilma (Deployment):** Google Cloud Run (Docker-konteyner orqali, Webhook usulida ishlaydi, Port: 8080)
- **Izlash tizimi (Search Index):** Firestore Vector Search (Cosine distance yordamida `knowledge_base` kolleksiyasidan aqlli qidiruv amalga oshiriladi).

---

## ⚙️ 3. Asosiy Modullar va Imkoniyatlar (Key Features)
1. **Identifikatsiya va Sinxronizatsiya (`handlers/onboarding.py`):**
   - Telefon raqam orqali verifikatsiya. Telegram profilini Firestore bazasidagi ilova profili (UID) bilan bog'lash. Daraja (level) va ballar (XP) sinxronizatsiyasi.
2. **AI HelpDesk (RAG texnologiyasi) (`services/ai_service.py`):**
   - 50 dan ortiq rasmiy sud yo'riqnomalaridan (PDF-dan olingan MD format) foydalanib xodimlarning IT savollariga aniq "qadam-baqadam" javob beradi. 
   - Foydalanuvchining lavozimi (kotib yoki Oliy sud xodimi) ga qarab javob berish uslubi moslashadi ("hormang" kabi o'zbekona empatiya ishtirokida).
3. **Raqamli Savodxonlik Testlari / Gamifikatsiya (`handlers/quizzes.py`):**
   - Sud tizimi IT savodxonligi bo'yicha dinamik qisqa testlar. A'lo baholangan testlar uchun Firestore ga avtomatik tarzda (+XP) ballar qo'shiladi.
4. **Statistika va Profil (`handlers/stats.py`):**
   - Barcha foydalanuvchi ma'lumotlari, chat tarixi va testlar hisoboti. 

---

## 📁 4. Loyihaning Fayl Tuzilmasi (Directory Structure)
Loyiha moduli (Clean structure) tamoyilida shakllantirilgan:

```text
sudqollanma_bot/
│
├── main.py                    # Botni polling yoki webhook(Cloud Run) da tushirish (Entry point)
├── loader.py                  # Kesh, Bot, Dispatcher, Firebase va Gemini ulash konfiguratsiyalari
├── config.py                  # API Kalitlar va muhit (.env) o'zgaruvchilarini yuklash
├── Dockerfile                 # GCloud da deploy qilish uchun konteyner qo'llanmasi
├── requirements.txt           # Python kutubxonalari
│
├── .agent/                    # Dasturlash bo'yicha maxsus yordamchi agent/avtomatlashtirish fayllari 
│   └── skills/                # Muhit deploy yo'riqnomalari (masalan: GCloud, Github)
│
├── handlers/                  # Foydalanuvchi xabarlarini qabul qiluvchi controller'lar:
│   ├── commands.py            # /start, /help, /profile, /about ...
│   ├── helpdesk.py            # AI javoblar berishi uchun tayyorlangan asosiy RAG menyusi
│   ├── middleware.py          # Anti-spam (throttling) va xatolarni ushlab qoluvchi to'siq
│   ├── onboarding.py          # Ro'yxatdan o'tish (telefon va TG ID ni bog'lash)
│   ├── quizzes.py             # Test ishlash jarayoni
│   └── stats.py               # Statistika menyusi
│
├── services/                  # Asosiy biznes logikalar:
│   ├── ai_service.py          # Gemini API, Vector qidiruv, Promptlar, dinamik test shakllantirish
│   └── firestore_service.py   # Firestore bazasi bilan CRUD aloqalarni boshqarish
│
└── data/                      # Baza yo'riqnomalari (Knowledge Base):
    ├── adolat-sud-uz/         # "Adolat" elektron bazasi darslik va yo'riqnomalari
    ├── edo-sud-uz/            # "E-DO" elektron hujjati aylanmasi bo'yicha qo'llanmalar
    ├── jib-sud-uz/            # Jinoyat ishlari tizimi bo'yicha yo'riqnomalar
    └── knowledge.md           # PDF'lardan birlashtirilgan umumiy MarkDown bazasi
```

---

## 🚀 5. Skriptlar va Boshqaruv vositalari (Automation Scripts)
Baza (Knowledge Base) ni doimiy obyektdan uzoqlashmay ushlab turish uchun utilitar skriptlar mavjud:
- `pdf_to_md.py` — Barcha tuman, shahar sudlari arxivlangan PDF fayllari ushbu skript orqali o'qilib yagona `.md` fayl holiga keltiriladi.
- `upload_knowledge.py` — Markdown dagi eng so'nggi ma'lumotni Google Gemini Embedding orqali qismlarga (chunks) bo'lib, to'g'ridan-to'g'ri Firestore dagi `knowledge_base` vektor kolleksiyasiga yuklaydi (va eskisini obnavit qiladi).
- `list_models.py` — Gemini AI ni aktiv bo'lgan modellarini ro'yxatini ko'rish.

---

## 🔒 6. Infratuzilma (Muhit Sozlamalari / Secrets)
Loyiha xavfsiz ishlashi uchun `.env` da quydagi API kalitlari bo'lishi shart:
- `BOT_TOKEN`: Telegram @BotFather dan olingan ruxsatnoma
- `GEMINI_API_KEY`: Generatsiya va Vector embeddings uchun Google Gemini kaliti
- `FIREBASE_CREDENTIALS`: GCP Service Account JSON fayliga o'tuvchi yo'l
- `WEBHOOK_URL`: Google Cloud Run ga deploy qilingandan so'ng beriladigan server manzili. (Aks holda Polling ishlaydi).
- `ADMIN_IDS`: Adminlarning Telegram ID raqamlari.

---

## 🔮 7. Kelajakdagi Namunaviy Rejalar (Future Roadmap)
Ushbu bot doimiy rivojlanishda bo'ladi. Loyihani keyingi bosqichlarida quyidagi ishlar amalga oshirilishi rejalashtirilgan:

1. **Onboarding Jarayonini Kengaytirish:**
   - Ro'yxatdan o'tish (verifikatsiya) vaqtida respublikadagi aniq bir sud joylashuvi (Court Name) ro'yxatdan tanlanishi talab etiladi. Bu o'z navbatida, qaysi hudud va sudlarda qanday muammolar ko'p uchrayotganini bilish (statistik dashboard) imkonini beradi.
2. **"Texnik Xizmat" Tizimining Integratsiyasi (Ticketing System):**
   - RAG (AI) orqali yechim topilmagan murakkab muammolar bo'yicha bot ichida to'g'ridan-to'g'ri mutaxassisga yo'naltirilgan "Arizalar" qoldiriladi va bu bevosita IT bo'limning "Tiketlar" paneliga yuboriladi.
3. **Mukammal AI Bazasi (Big Data Knowledge Base):**
   - E-SUD, ADOLAT, JIB va barcha tizimlar bo'yicha RAG ma'lumotlari doimiy yig'ib borilib, O'zbekistondagi eng katta, mustaqil va umumiylashtirilgan "Sud IT Bilimlar Bazasi" ga ega bo'lamiz.
4. **Flutter Mobil Ilovasi Bilan Yakuniy Birlashuv (Unified Ecosystem):**
   - Ushbu botning eng muvaffaqiyatli va ommaviy xususiyatlari (AI HelpDesk, Quizzes va Statistika) loyiha davomida xodimlarning soni ortishi va talablarning oshishi orqasidan to'lig'icha "Sud Qo'llanma" (Flutter) ilovasining asosiy funksionaliga ko'chib o'tadi va foydalanuvchilar bir platformaga birlashtiriladi.

---

*Hujjat loyiha qanday o'zgarishlarga duch kelishiga qarab doimiy ravishda yangilanib boradi.*
