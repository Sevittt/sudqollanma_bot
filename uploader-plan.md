# Sud Qo'llanma Bot — To'liq Tahlil va Reja

## Hozirgi Holat (MCP + Kod Audit natijalari)

### ✅ Firestore kolleksiyalari (HAQIQIY):
| Kolleksiya | Nima saqlangan | Status |
|---|---|---|
| `users` | telegram_id, role, xp, level, courtName, phoneNumber | ✅ To'g'ri |
| `courts` | courtName, courtType, region, isActive, order | ✅ To'g'ri |
| `quizzes` | title, description, category, resourceId | ✅ To'g'ri |
| `quizzes/{id}/questions` | questionText, options[], correctAnswer, explanation | ✅ To'g'ri |
| `knowledge_base` | title, content, systemId, tags[], description, pdfUrl | ✅ Mavjud (RAG uchun) |
| `resources` | title, description, url (Firebase Storage PDF), type | ✅ Mavjud |
| `faqs` | question, answer, category, tags | ✅ Mavjud |
| `conversations` | telegram_id, role, text, timestamp | ✅ To'g'ri |
| `quiz_attempts` | userId, quizId, score, totalQuestions, telegramId | ✅ To'g'ri |

---

## Muammolar va kerakli tuzatishlar

### 🔴 MUAMMO 1: AI model noto'g'ri
**Hozir:** `.env` da `GEMINI_MODEL=gemini-2.5-flash` ✅ (yaxshi)  
**Lekin:** `ai_service.py` 205-qator: `"Model: gemini-3-flash-preview"` — xato string  
**Tuzatish:** Error message ni to'g'irlash. Foydalanuvchi "3.1 pro"ga o'tishni so'ragan — bu `gemini-2.5-pro-preview-03-25` yoki `gemini-2.5-pro`.

> [!IMPORTANT]
> `.env` da `GEMINI_MODEL=gemini-2.5-flash` ni **`GEMINI_MODEL=gemini-2.5-pro`** ga o'zgartirish kerak.

---

### 🔴 MUAMMO 2: `courtType` key mismatch (ASOSIY MUAMMO!)
**Firestore `courts` kolleksiyasidagi haqiqiy `courtType` qiymatlari:**
- `"viloyat"` (kichik harf)

**Bot `onboarding.py` dagi `COURT_TYPES` (qidirish uchun):**
```python
COURT_TYPES = {
    "JIB": "...",
    "FIB": "...",
    "VILOYAT": "...",   # ← KATTA HARF!
    "IQTISODIY": "...",
    "OLIY": "...",
}
```
**Firestore query:** `.where('courtType', '==', court_type)` — "VILOYAT" != "viloyat"!  
Bu sababdan sudlar ro'yxati topilmaydi va "qo'lda kiriting" chiqadi!

**Tuzatish:** `COURT_TYPES` ni kichik harflarga o'zgartirish yoki query da `.lower()` ishlatish.

---

### 🟡 MUAMMO 3: `knowledge_base` RAG — `text` field yo'q
**Hozirgi kod (`ai_service.py`):**
```python
if 'text' in data:
    context_parts.append(data['text'])
```
**Lekin Firestoredagi field nomi:** `content` (text emas!)  
Vector search natijalari ishlamayapti!

**Tuzatish:** `data['text']` → `data.get('content', data.get('text', ''))`

---

### 🟡 MUAMMO 4: `articles` kolleksiyasi yo'q
**Hozirgi kod `ai_service.py`:**  
```python
articles_ref = get_db().collection('articles').where('topic', '==', 'guide')...
```
`articles` kolleksiyasi Firestorede YO'Q! `knowledge_base` ishlatilishi kerak.

---

### 🟡 MUAMMO 5: Bot yangi buyruqlar yo'q
Foydalanuvchi so'ragan:
- `/qollanma` — `resources` kolleksiyasidan PDF fayllar ko'rsatish
- `/faq` yoki `/yordam` — FAQs kolleksiyasidan savollar
- `/maqolalar` — `knowledge_base`dan maqolalar

---

### 🟡 MUAMMO 6: `get_relevant_context`dagi Vector Search
Vector index hali sozlanmagan. Fallback `get_system_manuals()` works, lekin u `articles` 
kolleksiyasini qidiradi (yo'q). `knowledge_base`dan `content` field bilan o'qishi kerak.

---

## Amalga oshirish rejasi

### QADAM 1: `.env` — Model yangilash
```env
GEMINI_MODEL=gemini-2.5-pro
```

### QADAM 2: `services/ai_service.py` — 3 ta tuzatish
1. `articles` → `knowledge_base`, `text` → `content`
2. `get_relevant_context` fallback `knowledge_base`dan o'qisin
3. Error message ichidagi model nomini to'g'irlash

### QADAM 3: `handlers/onboarding.py` — `COURT_TYPES` key tuzatish
```python
COURT_TYPES = {
    "jib": "⚖️ Jinoiy ishlar bo'yicha sud",
    "fib": "📋 Fuqarolik ishlar bo'yicha sud",
    "viloyat": "🏛 Viloyat sudi",
    "iqtisodiy": "💼 Iqtisodiy sud",
    "oliy": "🏛 Oliy sud",
}
```

### QADAM 4: `services/firestore_service.py` — 3 ta yangi metod
1. `get_resources_by_type(type)` — PDF/fayllar
2. `get_knowledge_base_articles(category=None, limit=10)` — Maqolalar
3. `get_faqs_by_category(category=None)` — FAQ

### QADAM 5: `handlers/resources.py` — YANGI fayl
`/qollanma` va `📚 Qo'llanmalar` button — resources ko'rsatish

### QADAM 6: `handlers/kb_articles.py` — YANGI fayl
`/maqolalar` va knowledge_base maqolalarini ko'rsatish

### QADAM 7: `handlers/__init__.py` va `main.py` da yangi routerlar ro'yxatdan o'tkaz

### QADAM 8: BotFather commands yangilash
```
start - Botni ishga tushirish
help - Yordam va buyruqlar
profile - Mening profilim
quiz - Bilim testini boshlash
qollanma - PDF qo'llanmalar va fayllar
maqolalar - Bilimlar bazasi va maqolalar
faq - Ko'p so'raladigan savollar
stats - Statistikam
reset - Suhbat tarixini tozalash
about - Bot haqida
```

---

## Tekshirish rejasi
1. Bot ishga tushirib, viloyat → sud turi → sud nomini tanlash (court type mismatch tuzatildi)
2. AI javob sifatini knowledge_base content bilan tekshirish
3. `/qollanma` buyrug'i bilan PDF havolalarini ko'rish
4. Gemini 2.5 Pro ishlayotganini log orqali tekshirish

---

> [!NOTE]
> `populate_faqs.py` script oldin ishlatilgan va `faqs` kolleksiyasi to'ldirilgan.
> knowledge_base ham maqolalar bilan to'la. Asosiy muammo — botning bu 
> kolleksiyalarga murojaat qilmasligi va `courtType` kichik/katta harf muammosi.
