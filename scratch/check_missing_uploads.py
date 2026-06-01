"""
check_missing_uploads.py
========================
Ushbu skript Firebase Storage-dagi fayllarni tekshiradi va
mahalliy `sudqollanma_bot/data/` papkasidagi PDF va videolarning 
qaysilari Storage-ga yuklanmaganligini aniqlaydi.
"""

import os
import sys
from pathlib import Path
import firebase_admin
from firebase_admin import credentials, storage

# Konsolda o'zbekcha matnlarni to'g'ri ko'rsatish uchun
sys.stdout.reconfigure(encoding='utf-8')

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BOT_DIR = os.path.join(BASE_DIR, "sudqollanma_bot")
SERVICE_KEY = os.path.join(BOT_DIR, "serviceAccountKey.json")
STORAGE_BUCKET = "educationapp-4780a.firebasestorage.app"

if not os.path.exists(SERVICE_KEY):
    print(f"❌ Xato: serviceAccountKey.json topilmadi! ({SERVICE_KEY})")
    sys.exit(1)

# Firebase-ni faqat bitta marta ishga tushirish
if not firebase_admin._apps:
    cred = credentials.Certificate(SERVICE_KEY)
    firebase_admin.initialize_app(cred, {'storageBucket': STORAGE_BUCKET})

bucket = storage.bucket()

print("⏳ Firebase Storage-dagi mavjud fayllar ro'yxatini yuklamoqda...")
try:
    blobs = list(bucket.list_blobs())
    storage_files = {blob.name: blob for blob in blobs}
    print(f"✅ Storage-da jami {len(storage_files)} ta fayl topildi.")
except Exception as e:
    print(f"❌ Firebase Storage-dan ma'lumot olishda xatolik: {e}")
    sys.exit(1)

# ── 1. VIDEOLARNI TEKSHIRISH ────────────────────────────────────────────────

print("\n🎥 1. VIDEOLARNI TEKSHIRISH...")

# Video papkalari va ularning Storage-dagi yo'li
VIDEO_SOURCES = [
    {
        "folder": os.path.join(BOT_DIR, "data", "jib-sud-uz", "vids"),
        "storage_path": "videos/jib-sud-uz",
    },
    {
        "folder": os.path.join(BOT_DIR, "data", "ms-sud-uz", "vids"),
        "storage_path": "videos/ms-sud-uz",
    },
    {
        "folder": os.path.join(BOT_DIR, "data", "xatolik-vids"),
        "storage_path": "videos/xatolik-vids",
    },
]

total_videos = 0
uploaded_videos = 0
missing_videos = []

for src in VIDEO_SOURCES:
    folder = src["folder"]
    storage_base = src["storage_path"]
    
    if not os.path.exists(folder):
        print(f"⚠️  Papka mavjud emas: {folder}")
        continue
        
    video_files = [f for f in os.listdir(folder) 
                   if f.lower().endswith(('.mp4', '.webm', '.wmv', '.avi', '.mov'))]
                   
    for filename in sorted(video_files):
        total_videos += 1
        expected_storage_path = f"{storage_base}/{filename}"
        
        if expected_storage_path in storage_files:
            uploaded_videos += 1
        else:
            missing_videos.append((filename, os.path.join(folder, filename), expected_storage_path))

print(f"  📊 Jami videolar: {total_videos}")
print(f"  ✅ Yuklanganlar:  {uploaded_videos}")
print(f"  ❌ Yuklanmaganlar: {len(missing_videos)}")

if missing_videos:
    print("\n   ⚠️  Quyidagi videolar yuklanmagan:")
    for idx, (name, local_path, store_path) in enumerate(missing_videos, 1):
        size_mb = round(os.path.getsize(local_path) / (1024 * 1024), 2)
        print(f"     {idx}. {name} ({size_mb} MB) -> Storage-da kutilgan joyi: '{store_path}'")
else:
    print("   🎉 Barcha videolar to'liq yuklangan!")


# ── 2. PDF HUJJATLARNI TEKSHIRISH ───────────────────────────────────────────

print("\n📄 2. PDF HUJJATLARNI TEKSHIRISH...")

# Tizimdagi rasmiy yuklanishi shart bo'lgan 4 ta PDF fayl
OFFICIAL_FILES_TO_UPLOAD = [
    r"data\jib-sud-uz\Жиноят ишлари бўйича судлар учун қўлланма (мундарижа).pdf",
    r"data\adolat-sud-uz\Суд_hujjatlarini_internet_tarmog'ida_e'lon_qilish_tartibi_pdf.pdf",
    r"data\edo-sud-uz\10_Imzolangan_hujjatlarni_sud_tizimi_va_tashqi_tashkilotlarga_yuborish.pdf",
    r"data\e-imzo\E-IMZO Modulidan foydalanish boʼyicha qoʼllanma.pdf"
]

# Barcha local PDF-larni qidiramiz
total_pdfs = 0
uploaded_pdfs = 0
missing_pdfs = []
missing_official_pdfs = []

# data papkalarini aylanib chiqish
for root, dirs, files in os.walk(os.path.join(BOT_DIR, "data")):
    for file in files:
        if file.lower().endswith(".pdf"):
            total_pdfs += 1
            local_full_path = os.path.join(root, file)
            expected_storage_path = f"resources_pdfs/{file}"
            
            # Bu rasmiy PDF-mi?
            rel_path = os.path.relpath(local_full_path, BOT_DIR)
            is_official = False
            for off_p in OFFICIAL_FILES_TO_UPLOAD:
                # normalize path comparison
                if off_p.replace('\\', '/').lower() in rel_path.replace('\\', '/').lower():
                    is_official = True
                    break
            
            if expected_storage_path in storage_files:
                uploaded_pdfs += 1
            else:
                if is_official:
                    missing_official_pdfs.append((file, local_full_path, expected_storage_path))
                else:
                    missing_pdfs.append((file, local_full_path, expected_storage_path))

print(f"  📊 Jami PDF-lar:  {total_pdfs}")
print(f"  ✅ Yuklanganlar:  {uploaded_pdfs}")
print(f"  ❌ Yuklanmaganlar: {len(missing_official_pdfs) + len(missing_pdfs)}")
print(f"     - Shundan yuklanishi SHART bo'lgan rasmiy PDF-lar: {len(missing_official_pdfs)}")
print(f"     - Boshqa qo'shimcha PDF-lar (ixtiyoriy): {len(missing_pdfs)}")

if missing_official_pdfs:
    print("\n   ⚠️  QUYIDAGI RASMIY PDF-LAR STORAGE'GA YUKLANMAGAN (MUHIM!):")
    for idx, (name, local_path, store_path) in enumerate(missing_official_pdfs, 1):
        print(f"     {idx}. {name} -> Kutilgan joyi: '{store_path}'")

if missing_pdfs:
    print("\n   ℹ️  Yuklanmagan qo'shimcha PDF-lar (Bular populate_files.py da yo'q, lekin data papkasida bor):")
    # faqat birinchi 15 tasini ko'rsatamiz konsol to'lib ketmasligi uchun
    for idx, (name, local_path, store_path) in enumerate(missing_pdfs[:15], 1):
        print(f"     {idx}. {name}")
    if len(missing_pdfs) > 15:
        print(f"     ... va yana {len(missing_pdfs) - 15} ta qo'shimcha PDF fayl.")
else:
    print("   🎉 Hamma PDF-lar to'liq yuklangan!")

print("\n💡 Eslatma: Yuklanmagan rasmiy PDF fayllarni 'populate_files.py', videolarni esa 'populate_videos.py' yordamida yuklash mumkin.")
