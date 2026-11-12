import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
FIREBASE_CREDENTIALS = os.getenv("FIREBASE_CREDENTIALS")

# Gemini generation model (configurable via .env)
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

# ── Embedding konfiguratsiyasi ──────────────────────────────────────────────
# MUHIM: Bu model bilan rag_chunks va wiki_pages indexlangan bo'lishi SHART.
# Agar model o'zgarsа — barcha kolleksiyalarni qayta indexlash kerak!
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "gemini-embedding-2")
EMBEDDING_DIM = int(os.getenv("EMBEDDING_DIM", "768"))

# ── RAG va Wiki threshold konfiguratsiyasi ──────────────────────────────────
# Cosine distance threshold (kichikroq = qatiyroq moslik)
WIKI_HIT_THRESHOLD = float(os.getenv("WIKI_HIT_THRESHOLD", "0.35"))
# RAG vector search uchun necha chunk qaytarilsin
RAG_LIMIT = int(os.getenv("RAG_LIMIT", "3"))
# knowledge_base fallback uchun necha maqola o'qilsin
KB_FALLBACK_LIMIT = int(os.getenv("KB_FALLBACK_LIMIT", "5"))

# Admin Telegram IDs (comma-separated in .env, e.g., "123456,789012")
_admin_ids_raw = os.getenv("ADMIN_IDS", "")
ADMIN_IDS = [int(x.strip()) for x in _admin_ids_raw.split(",") if x.strip().isdigit()]

# Webhook configuration for Google Cloud Run
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "")
WEBAPP_HOST = os.getenv("WEBAPP_HOST", "0.0.0.0")
WEBAPP_PORT = int(os.getenv("PORT", 8080))  # Cloud Run sets PORT automatically
