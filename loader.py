from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
import config
import logging
import firebase_admin
from firebase_admin import credentials, firestore
from google import genai

# Setup logging
logging.basicConfig(level=logging.INFO)

# Initialize Bot (Fast)
bot = Bot(token=config.BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

# Global variables for lazy initialization
_db = None
gemini_client = None

def get_db():
    global _db
    if _db is not None:
        return _db
    
    try:
        if not firebase_admin._apps:
            if config.FIREBASE_CREDENTIALS:
                cred = credentials.Certificate(config.FIREBASE_CREDENTIALS)
                firebase_admin.initialize_app(cred)
                logging.info("Firebase initialized successfully using Certificate.")
            else:
                logging.info("FIREBASE_CREDENTIALS missing. Attempting Application Default Credentials.")
                firebase_admin.initialize_app()
                logging.info("Firebase initialized successfully using ADC.")
        
        _db = firestore.client()
        return _db
    except Exception as e:
        logging.error(f"Error initializing Firebase: {e}")
        return None

def init_gemini():
    global gemini_client
    if gemini_client is not None:
        return gemini_client
        
    if config.GEMINI_API_KEY:
        try:
            gemini_client = genai.Client(api_key=config.GEMINI_API_KEY)
            logging.info(f"Gemini AI Client initialized (model: {config.GEMINI_MODEL}).")
            return gemini_client
        except Exception as e:
            logging.error(f"Error initializing Gemini: {e}")
            return None
    else:
        logging.warning("GEMINI_API_KEY not found in .env")
        return None

# For backward compatibility if needed at import time (risky but common)
# We will NOT initialize here to avoid blocking imports.
# Services should call get_db() and init_gemini()
