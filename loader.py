from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
import config
import logging
import firebase_admin
from firebase_admin import credentials, firestore
import google.generativeai as genai

# Setup logging
logging.basicConfig(level=logging.INFO)

# Initialize Bot
if not config.BOT_TOKEN:
    logging.error("BOT_TOKEN not found! Please check your .env file.")
    exit(1)

bot = Bot(token=config.BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

# Initialize Firebase
try:
    if not firebase_admin._apps:
        if config.FIREBASE_CREDENTIALS:
            cred = credentials.Certificate(config.FIREBASE_CREDENTIALS)
            firebase_admin.initialize_app(cred)
            logging.info("Firebase initialized successfully.")
        else:
            logging.warning("FIREBASE_CREDENTIALS not found in .env")
    
    db = firestore.client()
except Exception as e:
    logging.error(f"Error initializing Firebase: {e}")
    db = None

# Initialize Gemini
if config.GEMINI_API_KEY:
    genai.configure(api_key=config.GEMINI_API_KEY)
    model = genai.GenerativeModel('gemini-flash-latest')
    logging.info("Gemini AI initialized.")
else:
    logging.warning("GEMINI_API_KEY not found in .env")
    model = None
