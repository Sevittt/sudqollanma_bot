"""
populate_videos.py
==================
data/jib-sud-uz/vids/ va data/xatolik-vids/ papkalaridagi barcha
video fayllarni Firebase Storage ga yuklaydi va
Firestore video_tutorials kolleksiyasiga meta-ma'lumot qo'shadi.

Ishlatish:
    pip install firebase-admin google-cloud-storage
    python populate_videos.py
"""

import os
import re
import logging
import asyncio
from pathlib import Path
import firebase_admin
from firebase_admin import credentials, firestore, storage

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Config ---
FIREBASE_CRED   = "serviceAccountKey.json"
STORAGE_BUCKET  = "educationapp-4780a.firebasestorage.app"

# Video papkalari va ularning tizim IDlari
VIDEO_SOURCES = [
    {
        "folder": "data/jib-sud-uz/vids",
        "systemId": "ESUD",
        "category": "guide",
        "storage_path": "videos/jib-sud-uz",
    },
    {
        "folder": "data/ms-sud-uz/vids",
        "systemId": "MS",
        "category": "guide",
        "storage_path": "videos/ms-sud-uz",
    },
    {
        "folder": "data/xatolik-vids",
        "systemId": "ESUD",
        "category": "troubleshooting",  # Xatoliklarni hal qilish
        "storage_path": "videos/xatolik-vids",
    },
]

# Video nomidan tartib raqamini va sarlavhani ajratib olish
def parse_video_name(filename: str) -> dict:
    """
    Fayl nomidan tartib raqami va sarlavhani ajratib oladi.
    Misol: "12. E-XSUD ахборот тизимига кириш..." -> {order: 12, title: "E-XSUD..."}
    """
    name = Path(filename).stem  # kengaytmasiz nom
    
    # "12. Title" formatini qidirish
    match = re.match(r'^(\d+)\.\s*(.+)', name)
    if match:
        return {
            "order": int(match.group(1)),
            "title": match.group(2).strip(),
        }
    
    # Raqam yo'q bo'lsa — sarlavhani to'g'ridan o'qish
    return {"order": 99, "title": name}

def get_tags_from_title(title: str, system_id: str) -> list:
    """Sarlavhadan tegishli taglar yaratish."""
    tags = [system_id.lower()]
    
    keywords = {
        "ro'yxat": "royxat",
        "rўйхат": "royxat",
        "тақсимот": "taqsimot",
        "taqsimot": "taqsimot",
        "arxiv": "arxiv",
        "ижро": "ijro",
        "ijro": "ijro",
        "апелляция": "apellyatsiya",
        "кассация": "kassatsiya",
        "кириш": "kirish",
        "kirish": "kirish",
        "автоматик": "avtomatik",
        "xato": "xato",
        "kesh": "kesh",
        "tiket": "tiket",
        "публикация": "publikatsiya",
    }
    
    title_lower = title.lower()
    for keyword, tag in keywords.items():
        if keyword in title_lower and tag not in tags:
            tags.append(tag)
    
    return tags

def upload_video_to_storage(bucket, local_path: str, storage_path: str) -> str:
    """Videoni Firebase Storage ga yuklaydi va public URL qaytaradi."""
    blob = bucket.blob(storage_path)
    
    # Mime type aniqlash
    ext = Path(local_path).suffix.lower()
    mime_map = {
        ".mp4": "video/mp4",
        ".webm": "video/webm",
        ".wmv": "video/x-ms-wmv",
        ".avi": "video/avi",
    }
    mime_type = mime_map.get(ext, "video/mp4")
    
    logger.info(f"  ⬆️  Yuklanmoqda: {storage_path}")
    blob.upload_from_filename(local_path, content_type=mime_type)
    
    # Public qilish
    blob.make_public()
    return blob.public_url

def get_thumbnail_url(video_filename: str) -> str | None:
    """Videoga mos thumbnail URL (YouTube uchun, local uchun None)."""
    return None  # Hozircha null, keyinchalik thumbnail generator qo'shamiz

def get_file_size_mb(filepath: str) -> float:
    """Fayl hajmini MB da qaytaradi."""
    return round(os.path.getsize(filepath) / (1024 * 1024), 2)

def populate_videos():
    """Barcha videolarni Storage ga yuklaydi va Firestore ga yozadi."""
    
    # Firebase init
    if not firebase_admin._apps:
        cred = credentials.Certificate(FIREBASE_CRED)
        firebase_admin.initialize_app(cred, {'storageBucket': STORAGE_BUCKET})
    
    db = firestore.client()
    bucket = storage.bucket()

    # =============================================
    # 1. Eski video_tutorials hujjatlarini o'chirish
    # =============================================
    logger.info("🗑️  video_tutorials kolleksiyasini tozalash...")
    existing = db.collection("video_tutorials").stream()
    deleted = 0
    for doc in existing:
        doc.reference.delete()
        deleted += 1
    logger.info(f"   ✅ {deleted} ta eski hujjat o'chirildi.")

    # =============================================
    # 2. Har bir papkadagi videolarni yuklash
    # =============================================
    total_uploaded = 0
    
    for source in VIDEO_SOURCES:
        folder = source["folder"]
        system_id = source["systemId"]
        category = source["category"]
        storage_base = source["storage_path"]
        
        if not os.path.exists(folder):
            logger.warning(f"⚠️  Papka topilmadi: {folder}")
            continue
        
        video_files = [f for f in os.listdir(folder) 
                       if f.lower().endswith(('.mp4', '.webm', '.wmv', '.avi'))]
        
        if not video_files:
            logger.warning(f"⚠️  {folder} da video topilmadi.")
            continue
        
        logger.info(f"\n📁 {folder}: {len(video_files)} ta video")
        
        for filename in sorted(video_files):
            local_path = os.path.join(folder, filename)
            storage_path = f"{storage_base}/{filename}"
            
            parsed = parse_video_name(filename)
            title = parsed["title"]
            order = parsed["order"]
            file_size_mb = get_file_size_mb(local_path)
            
            logger.info(f"  [{order:02d}] {title[:50]}... ({file_size_mb} MB)")
            
            try:
                # Storage ga yuklash
                public_url = upload_video_to_storage(bucket, local_path, storage_path)
                
                # Firestore ga meta-ma'lumot yozish
                doc_data = {
                    "title": title,
                    "description": f"{system_id} tizimi bo'yicha video yo'riqnoma: {title}",
                    "systemId": system_id,
                    "category": category,
                    "videoUrl": public_url,
                    "storagePath": storage_path,
                    "youtubeId": None,      # YouTube ga yuklangandan keyin qo'shiladi
                    "thumbnailUrl": get_thumbnail_url(filename),
                    "duration": None,        # ffprobe bilan aniqlanadi
                    "fileSizeMb": file_size_mb,
                    "order": order,
                    "tags": get_tags_from_title(title, system_id),
                    "views": 0,
                    "likes": 0,
                    "sourceFile": filename,
                    "createdAt": firestore.SERVER_TIMESTAMP,
                    "updatedAt": firestore.SERVER_TIMESTAMP,
                }
                
                db.collection("video_tutorials").add(doc_data)
                total_uploaded += 1
                logger.info(f"     ✅ Firestore ga yozildi.")
                
            except Exception as e:
                logger.error(f"     ❌ Xatolik: {filename} — {e}")
    
    logger.info(f"\n🎉 YAKUNLANDI! Jami {total_uploaded} ta video yuklandi.")
    logger.info("Keyingi qadam: YouTube ga yuklanganda youtubeId maydonini yangilang.")

if __name__ == "__main__":
    populate_videos()
