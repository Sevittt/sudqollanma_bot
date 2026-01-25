import asyncio
import logging
import sys
from loader import bot, dp
from handlers import auth, profile, ai

async def main():
    # Logging configuration
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    
    # Register Routers
    dp.include_router(auth.router)
    dp.include_router(profile.router)
    dp.include_router(ai.router) # AI handler should be last to catch text messages

    logging.info("Bot ishga tushdi... (Gemini va Firestore ulangan)")
    
    try:
        await dp.start_polling(bot)
    except Exception as e:
        logging.error(f"Error during polling: {e}")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("Bot to'xtatildi.")
