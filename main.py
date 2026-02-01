import asyncio
import logging
import sys
from loader import bot, dp
from handlers import router as main_router

async def main():
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    
    # Register Main Router (handles onboarding, quizzes, helpdesk)
    dp.include_router(main_router)

    logging.info("IT Support Bot ishga tushdi...")
    
    try:
        await dp.start_polling(bot)
    except Exception as e:
        logging.error(f"Polling error: {e}")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("Bot to'xtatildi.")
