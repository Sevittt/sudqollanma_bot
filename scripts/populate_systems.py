"""
populate_systems.py
===================
Sud tizimlari haqidagi metadata ma'lumotlarni Firestore-ga kirituvchi skript.
Har doim eski ma'lumotlarni tozalab, yangidan kiritadi.
"""

import logging
from loader import get_db

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

SYSTEMS_DATA = [
    {
        "id": "ESUD",
        "name": "E-SUD",
        "fullName": "JIB E-SUD Axborot Tizimi",
        "url": "jib.sud.uz",
        "logoUrl": "https://adolat.sud.uz/assets/images/logo.png",
        "description": "Jinoiy va qoida buzarlik ishlarni elektron ro'yxatdan o'tkazish, taqsimlash va elektron ish yuritish axborot tizimi.",
        "category": "primary",
        "status": "active",
        "supportPhone": "+998 71 207-00-11",
        "manualCount": 25,
        "faqIds": [],
        "videoGuideId": None,
        "loginGuideId": None,
        "order": 1
    },
    {
        "id": "ADOLAT",
        "name": "Adolat",
        "fullName": "Adolat Axborot Tizimlari Kompleksi",
        "url": "adolat.sud.uz",
        "logoUrl": "https://adolat.sud.uz/assets/images/logo.png",
        "description": "Sudlar interaktiv xizmatlari portali. Elektron shaklda sud hujjatlarini jo'natish, sud holati bo'yicha ma'lumot olish.",
        "category": "primary",
        "status": "active",
        "supportPhone": "+998 71 207-00-11",
        "manualCount": 10,
        "faqIds": [],
        "videoGuideId": None,
        "loginGuideId": None,
        "order": 2
    },
    {
        "id": "EDO",
        "name": "E-DO",
        "fullName": "Elektron Hujjat Aylanmasi Tizimi",
        "url": "edo.ijro.uz",
        "logoUrl": "https://edo.ijro.uz/assets/img/logo.png",
        "description": "Sud va adliya tizimining ichki elektron hujjat aylanmasi kompleks tizimi. Ichki va tashqi xat-hujjatlarni boshqarish.",
        "category": "internal",
        "status": "active",
        "supportPhone": "",
        "manualCount": 16,
        "faqIds": [],
        "videoGuideId": None,
        "loginGuideId": None,
        "order": 3
    },
    {
        "id": "EIMZO",
        "name": "E-IMZO",
        "fullName": "Elektron Raqamli Imzo Moduli",
        "url": "e-imzo.uz",
        "logoUrl": "https://e-imzo.uz/images/logo.svg",
        "description": "Barcha tizimlarga masofadan turib Elektron Raqamli Imzo orqali kirish va hujjatlarni imzolash imkonini beruvchi modul.",
        "category": "tool",
        "status": "active",
        "supportPhone": "+998 71 202-32-32",
        "manualCount": 5,
        "faqIds": [],
        "videoGuideId": None,
        "loginGuideId": None,
        "order": 4
    },
    {
        "id": "EXAT",
        "name": "E-XAT",
        "fullName": "Himoyalangan Elektron Pochta Tizimi",
        "url": "mail.e-xat.uz",
        "logoUrl": "https://mail.e-xat.uz/logo.png",
        "description": "Davlat idoralari o'rtasida himoyalangan hujjat va xabarlarni almashish uchun maxsus yopiq elektron pochta tarmog'i.",
        "category": "communication",
        "status": "active",
        "supportPhone": "+998 71 200-00-00",
        "manualCount": 8,
        "faqIds": [],
        "videoGuideId": None,
        "loginGuideId": None,
        "order": 5
    },
    {
        "id": "VKS",
        "name": "VKA Tizimi",
        "fullName": "Videokonferensaloqa Tizimi",
        "url": "",
        "logoUrl": "",
        "description": "Sud majlislarini videokonferensaloqa (VKA) rejimida ochiq hamda himoyalangan formatda o'tkazish apparat-dasturiy kompleksi.",
        "category": "communication",
        "status": "active",
        "supportPhone": "",
        "manualCount": 5,
        "faqIds": [],
        "videoGuideId": None,
        "loginGuideId": None,
        "order": 6
    },
    {
        "id": "SMS",
        "name": "SMS Tizimi",
        "fullName": "Sud xabarnomalari SMS tizimi",
        "url": "",
        "logoUrl": "",
        "description": "Sud ishtirokchilarini sud majlisi vaqti, joyi va natijalari haqida SMS xabarnoma orqali tezkor ogohlantirish elektron moduli.",
        "category": "communication",
        "status": "active",
        "supportPhone": "",
        "manualCount": 3,
        "faqIds": [],
        "videoGuideId": None,
        "loginGuideId": None,
        "order": 7
    },
    {
        "id": "MS",
        "name": "M-SUD",
        "fullName": "Ma'muriy ishlar bo'yicha E-SUD",
        "url": "ms.sud.uz",
        "logoUrl": "https://adolat.sud.uz/assets/images/logo.png",
        "description": "Ma'muriy huquqbuzarlik ishlari bo'yicha hujjatlarni ayblovchi organlardan elektron qabul qilish va sud orqali elektron ko'rib chiqish.",
        "category": "primary",
        "status": "active",
        "supportPhone": "+998 71 207-00-11",
        "manualCount": 12,
        "faqIds": [],
        "videoGuideId": None,
        "loginGuideId": None,
        "order": 8
    }
]

def populate_systems():
    db = get_db()
    if not db:
        logger.error("DB connection error!")
        return
        
    collection_ref = db.collection('systems')
    
    # 1. Eski datani tozalash
    docs = collection_ref.stream()
    deleted = 0
    for doc in docs:
        doc.reference.delete()
        deleted += 1
    logger.info(f"Mavjud {deleted} ta tizm o'chirildi.")
    
    # 2. Yangi tizimlarni yozish
    batch = db.batch()
    for sys_data in SYSTEMS_DATA:
        doc_ref = collection_ref.document(sys_data['id'])
        batch.set(doc_ref, sys_data)
        
    batch.commit()
    logger.info(f"Yangi {len(SYSTEMS_DATA)} ta tizim Firestore'ga (batch) yuklandi! ✅")

if __name__ == "__main__":
    populate_systems()
