import os
import random
import firebase_admin
from firebase_admin import credentials, firestore

valid_categories = [
    "Kirish Muammolari",
    "Parol Muammolari",
    "Fayl Yuklash",
    "Ruxsat",
    "Umumiy",
    "Texnik"
]

if not firebase_admin._apps:
    cred = credentials.Certificate("serviceAccountKey.json")
    firebase_admin.initialize_app(cred)

db = firestore.client()

def fix_categories():
    docs = db.collection('faqs').stream()
    count = 0
    for doc in docs:
        data = doc.to_dict()
        q = data.get('question', '').lower()
        
        # Aqlliroq tanlash (keyword asosida)
        new_cat = "Umumiy"
        if "parol" in q or "unutdim" in q:
            new_cat = "Parol Muammolari"
        elif "kirish" in q or "kiriladi" in q or "ID karta" in q:
            new_cat = "Kirish Muammolari"
        elif "yuklash" in q or "skaner" in q or "fayl" in q:
            new_cat = "Fayl Yuklash"
        elif "ruxsat" in q or "huquq" in q or "imzo" in q or "eri" in q:
            new_cat = "Ruxsat"
        elif "xato" in q or "nosozlik" in q or "texnik" in q or "brauzer" in q:
            new_cat = "Texnik"
        else:
            new_cat = random.choice(valid_categories)
            
        doc.reference.update({'category': new_cat})
        count += 1
        
    print(f"Jami {count} ta faqs category yangilandi!")

if __name__ == "__main__":
    fix_categories()
