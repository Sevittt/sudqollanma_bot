# Sud Qo'llanma Bot — LLM Wiki ANALITIK / GROUNDING PROMPT

> Bu prompt implementatsiya buyrug'i EMAS. Bu — agentni to'xtatib, mavjud rejani
> Karpathy'ning haqiqiy LLM Wiki patterni va community tajribasi bilan solishtirib,
> qaror qabul qilishga majburlovchi tahliliy prompt. Avval shuni bajar, keyin kod yoz.

---

## Sening vazifang

Sen `sudqollanma_bot` loyihasiga LLM Wiki qatlamini qo'shish bo'yicha **avval berilgan
implementatsiya promptini tanqidiy baholashing** kerak. Kod yozishdan oldin, quyidagi
manbalarni o'qib chiq va rejani ularning yorug'ida qayta ko'rib chiq:

1. Karpathy'ning asl gisti: https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f
2. Loyiha holati: https://github.com/Sevittt/sudqollanma_bot (asosan `services/ai_service.py`)
3. Avval berilgan implementatsiya prompti (foydalanuvchida bor)

**Muhim:** men xato qilishdan qo'rqmayman. Senga to'liq erkinlik beraman —
agar reja noto'g'ri bo'lsa, ochiq ayt va sababini asosla. Maqtov kerak emas, haqiqat kerak.

---

## Kontekst: Karpathy patterni vs bizning holatimiz

Karpathy patterni **fayl-asosli, lokal, bitta foydalanuvchi** uchun mo'ljallangan
(Obsidian + Claude Code, markdown fayllar, git). Bizning holatimiz **butunlay boshqacha**:

| Karpathy | Bizning bot |
|----------|-------------|
| Lokal markdown fayllar | Firestore kolleksiyalari |
| Bitta foydalanuvchi (egasi) | Minglab sud xodimlari |
| Claude Code interaktiv | Cloud Run, scale-to-zero, avtonom |
| Obsidian'da ko'rib turadi | Telegram orqali, ko'rmaydi |
| Egasi sources'ni kuratsiya qiladi | Manbalar oldindan yuklangan (knowledge_base) |

**Birinchi tahliliy savol:** bu farqlar tufayli Karpathy patterning qaysi qismlari
to'g'ridan-to'g'ri ko'chiriladi, qaysilari moslashtiriladi, qaysilari umuman
qo'llanilmaydi? Har bir element uchun qaroringni asosla.

---

## Karpathy patternining to'liq elementlari (rejada borligini tekshir)

Karpathy gisti quyidagi elementlardan iborat. Bizning implementatsiya prompti
ularning qaysilarini qamragan, qaysilari yo'q — tahlil qil:

### Uch qatlam
- [ ] **Raw sources** (immutable) — bizda: `rag_chunks`, `knowledge_base`. Bor.
- [ ] **Wiki** (LLM owns) — bizda: `wiki_pages`. Rejada bor, lekin yuzaki.
- [ ] **Schema** (CLAUDE.md/AGENTS.md ekvivalenti) — **bizda YO'Q**. Bu eng muhim
      element: LLM'ni intizomli wiki saqlovchiga aylantiradi. Firestore kontekstida
      bu nima bo'lishi kerak? (Masalan: `wiki_schema` hujjati yoki kod ichidagi
      qat'iy prompt shabloni + qoidalar.)

### Uch operatsiya
- [ ] **Ingest** — manba qo'shilganda, LLM uni o'qiydi va **10-15 sahifani** cross-reference
      bilan yangilaydi. Bizning reja buni "3 chunkdan 1 sahifa" deb soddalashtirgan —
      bu Karpathy'ning ingestiga MOS EMAS. Tahlil qil: bizning miqyosda to'liq ingest
      kerakmi, yoki soddalashtirilgan versiya yetarlimi?
- [ ] **Query** — savolga javob + **javobni wiki'ga qaytarib filing qilish**
      ("good answers can be filed back as new pages"). Bizning reja query natijasini
      qaytarib saqlashni o'ylamagan.
- [ ] **Lint** — davriy sog'liq tekshiruvi: qarama-qarshilik, eskirish, yetim sahifa.
      **Bizda YO'Q** — bu bizning staleness muammosining yechimi.

### Ikki maxsus fayl
- [ ] **index.md** — kontentga yo'naltirilgan katalog. Karpathy da'vosi:
      **~100 manba / yuzlab sahifagacha bu embedding RAG'ni keraksiz qiladi.**
      Firestore'da bu `wiki_index` hujjati bo'lishi mumkin.
      **Muhim tahliliy savol:** bizning sud qo'llanmalari hajmi qancha? Agar
      ~hundreds of pages ichida bo'lsa, vector search o'rniga index-based navigation
      sodda va arzonroq bo'lishi mumkin. Buni hisobla va qaror ber.
- [ ] **log.md** — append-only xronologik jurnal. Firestore'da `wiki_log` kolleksiyasi.

---

## Community aniqlagan muammolar (bizning rejaga moslab tahlil qil)

Karpathy gistining izohlarida amaliyotchilar quyidagi muammolarni topgan.
Har biri bizning rejaga qanday tegishli — baholab chiq:

### 1. Identity (duplicate pages)
Bir tushuncha turli nomlar bilan ikki sahifa bo'lib ketadi
(masalan "E-IMZO drayveri" va "E-IMZO o'rnatish muammosi" = bir mavzu).
Bizning rejada slug oddiy `query[:60]` dan olinadi — bu ANIQ shu muammoga olib keladi.
**Yechim variantlari:** alias matching (Synto loyihasi), yoki ingest paytida
mavjud sahifalar bilan semantik o'xshashlikni tekshirib, yangi yaratish o'rniga
mavjudni yangilash.
→ Qaysi yechimni tanlaysan va nega?

### 2. Level (flat hierarchy)
Hamma sahifa bir xil darajada bo'lsa, muhimlik yo'qoladi
("E-SUD tizimi umumiy" va "tugma X ishlamasligi" bir xil vaznda).
Bir amaliyotchi yechimi: avval **citable claims** (sitata qilinadigan da'volar)
ajratiladi, keyin tushuncha qatlami ular ustiga quriladi — shunda muhimlik
strukturadan kelib chiqadi.
→ Bizning sud domeni uchun bu kerakmi, yoki ortiqcha murakkablikmi? Asosla.

### 3. Relationship (typed links)
"Bog'liq" deb belgilash yetarli emas — munosabat turi yo'qoladi
(similar / contains / contradicts / supersedes). Bizning rejada `related: [slug]`
bor edi, lekin tursiz. Sud domenida muhimi: bir tartib boshqasini **bekor qiladi**
(supersedes) — eski qonun, yangi qonun. Buni typed link bilan ifodalash kerakmi?

### 4. Staleness (eng katta muammo)
dtmoura: wiki eskirib qolishining oldini olish — eng qiyin qism.
"`claude.md`ga 'yangilashni unutma' deb yozish ishlamaydi."
Bizning Cloud Run + scale-to-zero muhitida bu yanada og'irroq, chunki avtonom
background pass yo'q. **Yechim:** lint'ni alohida script/cron sifatida tashkil qilish
(runtime'da emas). knowledge_base o'zgarganda qo'lda yoki rejalashtirilgan triggerda
ishga tushadigan.
→ Bizning infratuzilmada (Cloud Run, Cloud Scheduler bor) lint qanday amalga oshiriladi?

### 5. Quality gate / hallucination
Synthadoc yechimi: **Adversarial Review** — ikkinchi, mustaqil LLM (boshqa model
oilasi) har bir kompilyatsiya qilingan sahifani "overreach, asossiz umumlashtirish,
qarama-qarshilik" uchun tekshiradi. + har bir paragraf manbaga `^[fayl:satr]` bilan
bog'lanadi (claim-level provenance).
→ Bizning gallyutsinatsiyadan qochish maqsadimiz uchun bu KRITIK. Gemini bilan
bunday adversarial review qanday quriladi? (Masalan: yaratuvchi = Gemini Flash,
tekshiruvchi = Gemini Pro yoki teskarisi.) Asosla va minimal versiyasini taklif qil.

### 6. Fragmentation at scale
noirblue: pattern markdowndan tashqariga (PDF, docx, video) kengayganda
arxitektura parchalanadi. Bizda bu hozir muammo emas (faqat matn), lekin
kelajakda PDF qo'llanmalar qo'shilsa — buni hisobga ol.

### 7. Skeptik ovoz (muhim balans)
rstoye: "axborotni saqlash va izlash (information retrieval) nazariyasini o'rganing —
nega bu katta miqyosda ishlamasligini tushunasiz." Bu skeptisizmni jiddiy qabul qil:
LLM Wiki **kichik-o'rta miqyos** uchun (Karpathy o'zi ~100 manba deydi). Bizning
sud qo'llanmalari shu chegarada qoladimi? Agar tizim minglab hujjatga o'ssa,
vektor RAG yoki hibrid yondashuv to'g'riroq bo'ladimi? Ochiq baho ber.

---

## Sendan kutilayotgan natija (kod EMAS, tahlil)

Quyidagilarni markdown hujjat sifatida qaytar:

1. **Reja bahosi jadvali** — Karpathy elementlari × (bor / yo'q / moslashtirilgan)
   bizning rejada, har biri uchun bir jumlali izoh.

2. **Miqyos hisobi** — knowledge_base'dagi taxminiy hujjat/sahifa soni.
   index-based navigation yetarlimi, yoki vector search shartmi? Raqam bilan asosla.

3. **6 xom joy uchun aniq qaror** — yuqorida sanab o'tilgan har bir community
   muammosi uchun: bizning bot uchun bu muammo (a) jiddiy / (b) kichik / (c) tegishli emas,
   va tanlangan yechim + sababi.

4. **Tavsiya etilgan minimal arxitektura** — bizning holat uchun Karpathy patternining
   QAYSI qismlari kerak (hammasi emas — Karpathy o'zi "pick what's useful" deydi).
   Firestore kolleksiyalar sxemasi: wiki_pages, wiki_index, wiki_log, wiki_schema —
   qaysilari kerak, qaysilari ortiqcha.

5. **Tuzatilgan bosqichlar** — avvalgi implementatsiya promptidagi 3 bosqichni
   shu tahlil asosida qayta yoz. Ayniqsa: runtime build'ni o'chirib, ingest'ni
   batch/cron'ga ko'chirish; lint operatsiyasini qo'shish; adversarial review'ni
   integratsiya qilish.

6. **Ochiq risklar va noaniqliklar** — nimani bilmayapmiz, nimani sinab ko'rish kerak,
   qayerda xato chiqishi mumkin. Halol ro'yxat.

---

## Tahlil tamoyillari

- **Soddalik tarafdori bo'l, lekin asosli.** Foydalanuvchi "oddiy bo'lib qolishini
  xohlamayman" dedi — demak murakkablikdan qochma, lekin har bir murakkablikni asosla.
  Qo'shilgan har bir element o'z og'irligini oqlashi kerak.
- **Firebase/GCP'ning to'liq imkoniyatlaridan foydalan** — Cloud Scheduler (cron lint
  uchun), Firestore vector + oddiy index birga, Cloud Functions (background ingest uchun,
  Cloud Run scale-to-zero muammosini chetlab o'tish), Gemini ikki modeli (creator + reviewer).
- **Gallyutsinatsiyadan qochish — asosiy maqsad.** Har bir arxitektura qarori shu
  maqsadga xizmat qilishi kerak. Provenance (manba kuzatuvi) va adversarial review
  shuning uchun ustuvor.
- **Bosqichmalik.** Hammasini birdan qurma. Eng kam ishlaydigan versiyadan boshlab,
  har bosqichda sinab ko'rish mumkin bo'lsin.
- **Xato chiqsa — normal.** Foydalanuvchi tajriba qilishdan qo'rqmaydi. Lekin
  noaniqliklarni oldindan ochiq aytib qo'y, kutilmagan bo'lmasin.

---

## Eslatma: ikki agent solishtiruvi

Bu prompt Claude Code va Antigravity'ga alohida beriladi va natijalari solishtiriladi.
Shuning uchun tahliling **o'zini-o'zi tushuntiruvchi** bo'lsin — taxminlaringni va
qaror sabablaringni ochiq yoz, boshqa agent natijasi bilan solishtirish oson bo'lsin.
