import os
import json
import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime

# Firebase ni initsializatsiya qilish
cred = credentials.Certificate('serviceAccountKey.json')
firebase_admin.initialize_app(cred)
db = firestore.client()

COLLECTION_NAME = 'news'

# Boshlang'ich sud yangiliklari va kerakli e'lonlar
NEWS_DATA = [
    {
        "title": "E-SUD Milliy axborot tizimi orqali sudlarga murojaat qilish tartibi",
        "source": "Oliy sud matbuot xizmati",
        "url": "https://sud.uz/e-sud-tizimi-haqida/",
        "imageUrl": "https://sud.uz/wp-content/uploads/2021/04/e-sud-1.jpg",
        "publicationDate": datetime.now()
    },
    {
        "title": "Adolat va qonun ustuvorligini ta'minlashda raqamlashtirishning o'rni",
        "source": "Kun.uz",
        "url": "https://kun.uz/uz/news/2023/12/15/adolat-va-qonun-ustuvorligini-taminlashda-raqamlashtirishning-orni",
        "imageUrl": "https://storage.kun.uz/source/9/0z1q9_C-q7cTj_R_o_d_y_P_W_H_z.jpg",
        "publicationDate": datetime.now()
    },
    {
        "title": "Oliy sudda E-Xat tizimida hujjatlar almashinuvi tezlashdi",
        "source": "Daryo.uz",
        "url": "https://daryo.uz/k/2023/11/20/oliy-sud-va-e-xat",
        "imageUrl": "https://daryo.uz/cache/2023/11/oliy_sud.jpg",
        "publicationDate": datetime.now()
    },
    {
        "title": "Sud qarorlarini ijroga qaratishda E-Qaror ning qulayliklari",
        "source": "Adliya Vazirligi",
        "url": "https://minjust.uz/uz/press-center/news/106654/",
        "imageUrl": "https://minjust.uz/upload/iblock/c3a/c3a0b5b1b4c9f1b2b8e8f8b5a3f2d2c1.jpg",
        "publicationDate": datetime.now()
    },
    {
        "title": "Sudyalar Oliy Kengashi ochiq muloqot o‘tkazdi",
        "source": "UzA.uz",
        "url": "https://uza.uz/uz/posts/sudyalar-oliy-kengashi-ochiq-muloqot-otkazdi",
        "imageUrl": "https://uza.uz/uploads/2023/10/sudyalar.jpg",
        "publicationDate": datetime.now()
    }
]

def clear_collection():
    """Eski barcha yangiliklarni bazadan o'chiradi."""
    docs = db.collection(COLLECTION_NAME).stream()
    deleted_count = 0
    for doc in docs:
        doc.reference.delete()
        deleted_count += 1
    print(f"Eski {deleted_count} ta yangilik o'chirildi.")

def populate_news():
    """Yangi, boshlang'ich yangiliklarni yuklaydi"""
    print(f"Boshlandi: {COLLECTION_NAME} kolleksiyasiga yangiliklarni kiritish...")
    
    # 1. Tozalash
    clear_collection()
    
    # 2. Qo'shish
    added_count = 0
    for news in NEWS_DATA:
        # Dokument qo'shish
        db.collection(COLLECTION_NAME).add(news)
        added_count += 1
        print(f"Qo'shildi: {news['title']}")

    print(f"\nYakunlandi! Jami {added_count} ta yangilik qo'shildi.")

if __name__ == '__main__':
    populate_news()
