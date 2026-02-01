import asyncio
import logging
import sys
from loader import bot, dp
from handlers import onboarding, helpdesk, quizzes

async def main():
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    
    # Routerlarni ro'yxatdan o'tkazish
    dp.include_router(onboarding.router) # Birinchi onboarding bo'lishi shart!
    dp.include_router(helpdesk.router)
    dp.include_router(quizzes.router)

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
