# Sud Qo'llanma Bot — LLM Wiki YAKUNIY DEPLOY PROMPTI (Real qiymatlar bilan)

> Bu yakunlovchi promptning real GCP qiymatlari bilan to'ldirilgan versiyasi.
> Ikki qismga ajratilgan: AGENT QISMI (Claude Code / Antigravity bajaradi) va
> SIZNING QISMINGIZ (Cloud Shell'da qo'lda bajariladi). Tartib muhim.

---

## Loyiha qiymatlari (haqiqiy)

```
Project ID:        educationapp-4780a
Region:            europe-west4
Bot service:       sudqollanmabot
Image repo:        europe-west4-docker.pkg.dev/educationapp-4780a/cloud-run-source-deploy/sudqollanma_bot/sudqollanmabot
Service account:   660835097321-compute@developer.gserviceaccount.com
Webhook URL:       https://sudqollanmabot-ccwuj74cjq-ez.a.run.app
Gen model:         gemini-3.1-flash-lite-preview
Secrets (SM):      BOT_TOKEN, GEMINI_API_KEY
Env vars:          GEMINI_MODEL, WEBHOOK_URL, FIREBASE_CREDENTIALS=serviceAccountKey.json
Lint jadvali:      shanba 09:00 (Asia/Tashkent)
```

---

# QISM A — AGENT BAJARADI (kod o'zgarishlari)

Allaqachon qurilgan va TEGINILMAYDI: adversarial review (Creator+Reviewer),
wiki_index gibrid qidiruv, slug builder, topic merge, wiki_log, wiki_service.py mantiqi.

## A1. `/wiki/lint` create_task endpoint'ini olib tashlash

`main.py`'dagi `/wiki/lint` HTTP handler `asyncio.create_task(lint())` ishlatadi —
Cloud Run scale-to-zero'da background task o'ldirilib, lint yarim qoladi (sokin nosozlik).
Lint endi alohida Cloud Run Job orqali ishlaydi, shuning uchun:
- `/wiki/lint` endpoint'ini va uning create_task mantiqini `main.py`'dan olib tashla
- `X-Wiki-Lint-Key` tekshiruvi ham endi keraksiz — olib tashla
- Bot service endi faqat webhook/bot vazifasini bajaradi

## A2. `scripts/wiki_linter.py`'ni Job sifatida ishga tushadigan qilish

- Skript `python -m scripts.wiki_linter` bilan ishlashi kerak.
  Buning uchun `scripts/__init__.py` mavjudligini tekshir (yo'q bo'lsa — yarat).
  Agar paket strukturasi murakkab bo'lsa, `python scripts/wiki_linter.py` shakliga
  moslab, importlarni absolyut qil (`from services.wiki_service import ...`).
- Skript `if __name__ == "__main__":` bloki orqali to'liq lint sikilini bajarib,
  tugagach jarayonni toza yakunlasin (exit 0). Xato bo'lsa exit 1 — Job retry ko'rsin.
- Skript boshlanishida barcha env'lar (GEMINI_MODEL, FIREBASE_CREDENTIALS, va h.k.)
  mavjudligini tekshirsin — yo'q bo'lsa aniq xato log qilsin (sokin nosozlikdan qochish).
- Lint log'lari `wiki_log` kolleksiyasiga yozilsin: nechta sahifa tekshirildi,
  nechta qayta kompilyatsiya qilindi, nechta past-ball sahifa topildi.

## A3. Firestore vector index + threshold (avvalgi P0'lar — hali bajarilmasa)

- `wiki_pages` uchun vector index yaratish komandasini README'ga yoz (dimension=768).
- `test_wiki_rag.py`'dagi SKIP (vector fallback) PASS bo'lsin.
- Threshold nomuvofiqligini (0.25 vs 0.35) bitta izchil qiymatga keltir.

## A4. Qayta deploy

Yuqoridagilar tugagach, bot'ni qayta deploy qil (source deploy yangi image SHA yaratadi).
Bu YANGI image `scripts/wiki_linter.py`'ni o'z ichiga oladi — Job shu image'dan foydalanadi.

---

# QISM B — SIZ BAJARASIZ (Cloud Shell, qo'lda)

> ⚠️ KRITIK TARTIB: bu buyruqlarni faqat QISM A tugab, bot qayta deploy qilingandan
> KEYIN bajaring. Aks holda Job eski image'ni oladi va wiki_linter.py topilmaydi.

## B1. Yangi image SHA'ni topish

```bash
gcloud run services describe sudqollanmabot \
  --region europe-west4 \
  --format "value(spec.template.spec.containers[0].image)"
```
Chiqgan to'liq image yo'lini (yangi SHA bilan) keyingi buyruqda ishlating.

## B2. Cloud Run Job yaratish

```bash
gcloud run jobs create wiki-linter \
  --image <B1_DAN_CHIQQAN_YANGI_IMAGE> \
  --region europe-west4 \
  --command python \
  --args=-m,scripts.wiki_linter \
  --service-account 660835097321-compute@developer.gserviceaccount.com \
  --set-secrets "BOT_TOKEN=BOT_TOKEN:latest,GEMINI_API_KEY=GEMINI_API_KEY:latest" \
  --set-env-vars "GEMINI_MODEL=gemini-3.1-flash-lite-preview,WEBHOOK_URL=https://sudqollanmabot-ccwuj74cjq-ez.a.run.app,FIREBASE_CREDENTIALS=serviceAccountKey.json" \
  --task-timeout 3600 \
  --max-retries 1
```

## B3. Qo'lda sinab ko'rish (deploy'dan oldin majburiy)

```bash
gcloud run jobs execute wiki-linter --region europe-west4
```
Log'da lint TO'LIQ tugaganini tekshiring (yarim qolmaganini). Bu — sokin
nosozlik yo'qligining isboti.

## B4. Scheduler'ga ruxsat berish

```bash
gcloud run jobs add-iam-policy-binding wiki-linter \
  --region europe-west4 \
  --member "serviceAccount:660835097321-compute@developer.gserviceaccount.com" \
  --role roles/run.invoker
```

## B5. Haftalik Scheduler (shanba 09:00 Toshkent)

```bash
gcloud scheduler jobs create http wiki-linter-weekly \
  --location europe-west4 \
  --schedule "0 9 * * 6" \
  --time-zone "Asia/Tashkent" \
  --uri "https://europe-west4-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/educationapp-4780a/jobs/wiki-linter:run" \
  --http-method POST \
  --oauth-service-account-email 660835097321-compute@developer.gserviceaccount.com
```

> URI formatini joriy gcloud versiyasida tekshiring (`v1/namespaces` shakli o'zgargan
> bo'lishi mumkin). Xato bersa: `gcloud scheduler jobs create http --help`.

## B6. Tekshirish

```bash
# Scheduler ro'yxati
gcloud scheduler jobs list --location europe-west4

# Schedulerni qo'lda majburlab ishga tushirib sinash
gcloud scheduler jobs run wiki-linter-weekly --location europe-west4

# Job bajarilish tarixi
gcloud run jobs executions list --job wiki-linter --region europe-west4
```

---

## Muvaffaqiyat mezonlari

- `test_wiki_rag.py`: 8 PASS, 0 FAIL, 0 SKIP
- `main.py`'da `/wiki/lint` va create_task YO'Q
- `gcloud run jobs execute wiki-linter` to'liq, xatosiz tugaydi (B3)
- Scheduler shanba 09:00'da Job'ni ishga tushiradi, `wiki_log`'da yozuv paydo bo'ladi
- Bot oddiy savollarga, `/quiz`, `/maqolalar`, `/faq` — hammasi oldingiday ishlaydi

---

## Eslatma: nima uchun bu bo'linish to'g'ri

- **Kod o'zgarishi (Qism A)** — har deploy'da takrorlanadi, agent ishi.
- **Infra sozlash (Qism B)** — bir martalik, qo'lda, sizning nazoratingizda.
  Job + Scheduler bir marta yaratiladi; keyingi deploy'larda Job avtomatik yangi
  image'ni olishi uchun `gcloud run jobs update wiki-linter --image <yangi>` ishlatiladi
  (yoki :latest tag'ga o'tasiz). Buni B bo'limiga kelajak uchun eslatma sifatida qoldiring.
