import os
import sys
import logging
from urllib.parse import quote
import firebase_admin
from firebase_admin import credentials, firestore, storage

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
sys.stdout.reconfigure(encoding='utf-8')

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def load_env():
    env_path = os.path.join(BASE_DIR, ".env")
    env = {}
    if os.path.exists(env_path):
        with open(env_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and "=" in line and not line.startswith("#"):
                    key, _, val = line.partition("=")
                    env[key.strip()] = val.strip()
    return env

ENV = load_env()

# Initialize Firebase
if not firebase_admin._apps:
    cred = credentials.Certificate(os.path.join(BASE_DIR, "serviceAccountKey.json"))
    # Project id for storage
    firebase_admin.initialize_app(cred, {
        'storageBucket': 'educationapp-4780a.firebasestorage.app'
    })

db = firestore.client()
bucket = storage.bucket()
COLLECTION = "resources"

# PDFs to upload and populate
FILES_TO_UPLOAD = [
    {
        "local_path": r"data\jib-sud-uz\Жиноят ишлари бўйича судлар учун қўлланма (мундарижа).pdf",
        "title": "Jinoyat ishlari bo'yicha sudlar uchun to'liq qo'llanma",
        "description": "JIB sudlari bo'yicha hujjatlarni qo'shish va rasmiylashtirish.",
        "type": "jibSud",
        "author": "Oliy Sud IT bo'limi"
    },
    {
        "local_path": r"data\adolat-sud-uz\Суд_hujjatlarini_internet_tarmog'ida_e'lon_qilish_tartibi_pdf.pdf",
        "title": "Sud hujjatlarini internetda e'lon qilish tartibi",
        "description": "Adolat axborot tizimida hujjatlarni ko'chmas va ommaviy holatga keltirish.",
        "type": "adolat",
        "author": "Adolat Loyihasi"
    },
    {
        "local_path": r"data\edo-sud-uz\10_Imzolangan_hujjatlarni_sud_tizimi_va_tashqi_tashkilotlarga_yuborish.pdf",
        "title": "Imzolangan hujjatlarni sud va tashqi tashkilotlarga yuborish",
        "description": "EDO tizimidan chiqish, hujjatni jo'natish yo'riqnomasi.",
        "type": "edoSud",
        "author": "EDO Administrator"
    },
    {
        "local_path": r"data\e-imzo\E-IMZO Modulidan foydalanish boʼyicha qoʼllanma.pdf",
        "title": "E-IMZO Modulidan foydalanish bo'yicha qo'llanma",
        "description": "ERI kalitlarini o'rnatish, maxsus dasturlarni avtorizatsiyadan o'tkazish.",
        "type": "other",
        "author": "IT Xavfsizlik bo'limi"
    }
]

def upload_to_storage_and_get_url(local_path: str) -> str:
    # check exists
    full_path = os.path.join(BASE_DIR, local_path)
    if not os.path.exists(full_path):
        logging.error(f"Fayl topilmadi: {full_path}")
        return ""
    
    filename = os.path.basename(local_path)
    storage_path = f"resources_pdfs/{filename}"
    blob = bucket.blob(storage_path)
    
    logging.info(f"YUKLANMOQDA: {filename} -> Firebase Storage")
    blob.upload_from_filename(full_path, content_type='application/pdf')
    
    # Try to make public
    try:
        blob.make_public()
        logging.info("  -> Fayl omma uchun ochiq (public) qilindi.")
        return blob.public_url
    except Exception as e:
        logging.warning(f"  -> make_public() ishlamadi, fallback tokenli URL olinmoqda... Xatolik: {e}")
        # Build REST URL alternative if make_public is blocked by uniform access
        safe_path = quote(storage_path, safe='')
        url = f"https://firebasestorage.googleapis.com/v0/b/{bucket.name}/o/{safe_path}?alt=media"
        return url

def populate_files():
    logging.info("🚀 FILES (Resources) populatsiyasi Firebase Storage orqali boshlandi...")
    
    existing = list(db.collection(COLLECTION).stream())
    if existing:
        logging.info(f"⚠ Mavjud {len(existing)} ta eski fayl recordlari o'chirilmoqda...")
        for i in range(0, len(existing), 100):
            chunk = existing[i:i+100]
            batch = db.batch()
            for doc in chunk:
                batch.delete(doc.reference)
            batch.commit()
    
    grand_total = 0
    for idx, f in enumerate(FILES_TO_UPLOAD):
        logging.info(f"--- Qadam {idx + 1}/{len(FILES_TO_UPLOAD)} ---")
        url = upload_to_storage_and_get_url(f["local_path"])
        
        if not url:
            logging.error(f"❌ Fayl yuklanib URL olinmadi: {f['local_path']}")
            continue
            
        doc_id = f"res_{f['type']}_{idx}"
        doc = {
            "title": f["title"],
            "description": f["description"],
            "author": f["author"],
            "authorId": "admin_bot",
            "type": f["type"],
            "url": url,
            "createdAt": firestore.SERVER_TIMESTAMP
        }
        
        db.collection(COLLECTION).document(doc_id).set(doc)
        grand_total += 1
        logging.info(f"✅ Firestorega muvaffaqiyatli saqlandi! ({doc_id})")

    logging.info(f"\n🎉 JAMI {grand_total} ta tayyor PDF fayllar Storage va Firestore-ga yuklandi!")

if __name__ == "__main__":
    populate_files()
