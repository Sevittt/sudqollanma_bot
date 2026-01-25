import asyncio
import logging
import sys
from loader import bot, dp
from handlers import onboarding, helpdesk, quizzes

async def main():
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    
    # Register Routers (Order matters!)
    dp.include_router(onboarding.router)  # /start
    dp.include_router(quizzes.router)     # /quiz
    dp.include_router(helpdesk.router)    # Text messages (Fallthrough)

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
