import firebase_admin
from firebase_admin import credentials, firestore
import json
import os
from dotenv import load_dotenv

load_dotenv()

# Use the credentials path from .env
cred_path = os.getenv("FIREBASE_CREDENTIALS")
if not cred_path:
    print("FIREBASE_CREDENTIALS not found in .env")
    exit()

if not firebase_admin._apps:
    cred = credentials.Certificate(cred_path)
    firebase_admin.initialize_app(cred)

db = firestore.client()

def get_collection_samples(collection_name, limit=5):
    print(f"\n--- {collection_name} ---")
    docs = db.collection(collection_name).limit(limit).stream()
    for doc in docs:
        print(f"ID: {doc.id}")
        print(json.dumps(doc.to_dict(), indent=2, ensure_ascii=False))

get_collection_samples('resources')
get_collection_samples('kb_articles')
get_collection_samples('faqs')
