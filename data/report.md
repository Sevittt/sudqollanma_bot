# 🤖 Sud qo'llanma - To'liq Loyiha Hisoboti

## 📌 1. Loyihaning Maqsadi va Missiyasi
"Sud qo'llanma" — bu O'zbekiston sud tizimi xodimlari (Oliy sud, tuman, shahar va viloyat sudlari) uchun maxsus ishlab chiqilgan **Raqamli Murabbiy va Texnik Ko'makchi** telegram botidir. 

**Asosiy vazifalari:**
*   **IT Savodxonlikni oshirish:** Xodimlarning E-SUD, E-XAT, JIB.SUD.UZ, E-IMZO, VKS kabi idoraviy raqamli tizimlardan to'g'ri va xavfsiz foydalanish ko'nikmalarini rivojlantirish.
*   **Tezkor Texnik Yordam (HelpDesk):** Xodimlarga tizimlarda yuzaga keladigan texnik nosozliklarni bartaraf etishda qadam-baqadam yordam berish (masalan: "E-IMZO ishlamayapti", "Fayl yuklab bo'lmayapti").
*   **Ekotizim Integratsiyasi:** Bot mustaqil emas, u to'g'ridan-to'g'ri "Sud Qo'llanma" mobil ilovasining (Flutter) ekotizimiga ulangan. Foydalanuvchilarning botdagi faolliklari (testlar yechish, XP to'plash) markaziy ma'lumotlar bazasida (Firestore) sinxronlashadi.

*Muhim jihat:* Bot yuridik savollarga (masalan, kodeks moddalariga) emas, aynan raqamli tizimlar va kompyuter savodxonligiga oid savollarga javob berishga ixtisoslashgan.

---

## 🏗 2. Texnologik Stek (Texnologiyalar)
Bot ilg'or va zamonaviy texnologiyalar asosida qurilgan bo'lib, yuqori tezlik va aniqlikni ta'minlaydi.

*   **Dasturlash tili:** Python 3.11+
*   **Bot Asosi (Framework):** Aiogram 3.x (Asinxron ishlash uchun optimal tanlov)
*   **Ma'lumotlar Bazasi:** Firebase Firestore (NoSQL). *Mobil ilova bilan yagona baza ishlatiladi, ma'lumotlar duplikatsiyasining oldi olingan.*
*   **Sun'iy Intellekt (AI) & RAG:** Google Gemini
    *   Matn generatsiyasi uchun: `gemini-3.1-flash-lite`
    *   Vektorlashtirish (Embedding) uchun: `text-embedding-004` (yoki mos versiya)
*   **Qidiruv Mexanizmi:** Firestore Vector Search (Cosine distance orqali semantik qidiruv).
*   **Infratuzilma:** Google Cloud Run (Docker orqali webhook rejimida 24/7 ishlashga mo'ljallangan).

---

## ⚙️ 3. Asosiy Modullar va Funksiyalar
Loyihaning "Miyai" quyidagi asosiy mantiqiy bo'laklardan tashkil topgan:

### 3.1. Avtorizatsiya va Sinxronizatsiya (The Bridge)
*   **Foydalanuvchini tanish:** Botga `/start` bosilganda, tizim foydalanuvchining Firestore bazasida mavjudligini tekshiradi va u bilan interaktiv tarzda ishlaydi.
*   **Sinxronizatsiya:** Bot va Ilova o'rtasida ma'lumotlar almashinuvi ta'minlanadi. Daraja (Level) va Ballar (XP) hisobi yuritiladi.

### 3.2. AI HelpDesk (RAG texnologiyasi asosida qidiruv)
*   Bu botning eng kuchli funksiyasi. Tizim an'anaviy kalit so'zlarga emas, balki sun'iy intellektning semantik qidiruviga asoslangan (RAG - Retrieval-Augmented Generation).
*   **Ishlash jarayoni:**
    1. Foydalanuvchi muammoni yozadi (masalan: *"Parolimni qanday tiklayman?"*).
    2. Bot bu so'rovni Vektorga (raqamlar ketma-ketligiga) aylantiradi.
    3. Firestore dagi `rag_chunks` (yo'riqnomalar bazasi) dan eng o'xshash ma'lumotlar (Top-3) topiladi.
    4. Topilgan yo'riqnomalar Gemini AI ga yuboriladi (Kontekst sifatida).
    5. Gemini AI foydalanuvchiga faqat shu yo'riqnoma asosida, "IT Mutaxassisi" tilida, o'zbekona lutf bilan javob tayyorlaydi.

### 3.3. Raqamli Savodxonlik Testlari (Gamifikatsiya)
*   Xodimlarning IT bilimlarini muntazam oshirib borish uchun mo'ljallangan "Micro-learning" moduli.
*   Bot qisqa va aniq testlar beradi (masalan: axborot xavfsizligi, klaviatura qisqartmalari, tizim limitlari haqida).
*   To'g'ri topilgan javoblar uchun bazaga Avtomatik (Atomic update - `FieldValue.increment()`) ravishda ball (XP) qo'shiladi. Bu ballar xodimning reytingini oshiradi.

---

## 📁 4. Loyihaning Fayl Tuzilmasi (Arxitektura)
Bot kodi Clean Architecture (Toza Arxitektura) tamoyillari asosida modullarga ajratilgan:

```text
sudqollanma_bot/
├── main.py                    # Botning kirish nuqtasi (Entry point). Polling/Webhook boshqaruvi.
├── loader.py                  # Kesh, Bot, Dispatcher va Firebase ulanishlari markazi.
├── config.py                  # .env dan maxfiy kalitlarni o'quvchi modul.
├── requirements.txt           # Loyiha ishlashi uchun kerakli kutubxonalar ro'yxati.
├── Dockerfile                 # GCloud uchun deployment sozlamalari.
│
├── handlers/                  # Foydalanuvchi bilan muloqotni boshqaruvchi (Controller) qism:
│   ├── commands.py            # /start, /help kabi asosiy buyruqlar.
│   ├── onboarding.py          # Ro'yxatdan o'tish va akkauntlarni bog'lash jarayoni.
│   ├── helpdesk.py            # AI bilan savol-javob muloqoti (RAG chat).
│   ├── quizzes.py             # Test ishlash mantig'i.
│   ├── stats.py               # Foydalanuvchi reytingi va statistikasini ko'rsatish.
│   └── middleware.py          # Anti-spam himoyasi va so'rovlarni filtrlash.
│
├── services/                  # Asosiy biznes logikasi va tashqi API lar bilan ishlash:
│   ├── ai_service.py          # Gemini API, Vector qidiruv (RAG) va Promptlar.
│   └── firestore_service.py   # Firebase bazasi bilan CRUD (yozish/o'qish) amallari.
│
├── scripts/                   # Bazani to'ldirish va avtomatlashtirish uchun yordamchi skriptlar:
│   ├── populate_videos.py     
│   ├── populate_articles.py
│   ├── populate_faqs.py
│   └── upload_knowledge.py    # Ma'lumotlarni vektorlashtirib bazaga yuklash.
│
└── data/                      # Boshlang'ich yoki zaxira (fallback) ma'lumotlar.
```

---

## 🔒 5. Xavfsizlik va Ma'lumotlar Muhofazasi (Security)
Loyihada davlat tashkiloti xodimlari ishlaganligi sababli xavfsizlik birinchi o'rinda turadi:
*   **Telefon orqali verifikatsiya:** Telegram kontakt ma'lumoti (`message.contact.user_id`) aynan xabarni yuboruvchi (`message.from_user.id`) ga tegishli ekanligi qat'iy tekshiriladi (Identity Spoofing ning oldini olish).
*   **Maxfiy kalitlar:** Hech qanday API kalit (`BOT_TOKEN`, `GEMINI_API_KEY`) kod ichiga yozilmaydi, ular `.env` muhitida saqlanadi.
*   **Yagona Manba (Single Source of Truth):** Local JSON fayllarda hech qanday foydalanuvchi ma'lumoti saqlanmaydi, barchasi to'g'ridan-to'g'ri himoyalangan Firestore da ishlanadi.

---

## 🚀 6. Kelajakdagi Rivojlanish Rejalari (Roadmap)
Loyihaning navbatdagi bosqichlarida quyidagi funksiyalarni joriy etish rejalashtirilgan:

1.  **Ticketing System (Arizalar qoldirish):** Agar AI qoniqarli javob topa olmasa yoki muammo texnik bo'lsa (masalan: "Server ishlamayapti"), foydalanuvchi to'g'ridan-to'g'ri bot primary orqali IT bo'limiga ariza (ticket) yuborishi mumkin bo'ladi.
2.  **Sinxron Video Preview:** Xodim biron tizimning videosini qidirganda, bot videoning eng muhim 1 daqiqalik qismini (preview) yoki matnli xulosasini ko'rsatib, to'liq versiyasini ilovada ko'rishga yo'naltiradi.
3.  **Big Data Analytics:** Qaysi sudlarda, qaysi tizim bo'yicha qanday muammolar eng ko'p uchrashi haqida statistika yig'ish (Dashboard uchun). Bu orqali sud tizimi rahbariyati qaysi yo'nalishlarda o'quv seminarlari o'tish kerakligini tahlil qila oladi.
