import asyncio
import logging
import sys
from aiogram.types import BotCommand
from aiogram import Bot
from aiohttp import web
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application

import config
from loader import bot, dp
from handlers import onboarding, helpdesk, quizzes, commands, stats, resources, kb_articles, courses
from handlers.middleware import ThrottlingMiddleware, ErrorHandlerMiddleware

async def on_startup(bot: Bot):
    if config.WEBHOOK_URL:
        webhook_url = f"{config.WEBHOOK_URL}/webhook"
        await bot.set_webhook(webhook_url)
        logging.info(f"✅ Webhook o'rnatildi: {webhook_url}")

async def on_shutdown(bot: Bot):
    if config.WEBHOOK_URL:
        # Webhookni o'chirmaymiz. Bu Cloud Run "scale-to-zero" bo'lganda
        # Telegram hali ham xabarlarni yuborishda davom etishi uchun kerak.
        logging.info("❗️ Konteyner o'chmoqda (scale-to-zero), lekin Webhook manzili saqlab qolindi.")

def setup_handlers_and_middlewares():
    # Register middleware (order matters: error handler first, then throttle)
    dp.message.middleware(ErrorHandlerMiddleware())
    dp.message.middleware(ThrottlingMiddleware(rate_limit=1.0))
    
    # Register routers (order matters!)
    dp.include_router(onboarding.router)    # 1. Onboarding (/start, contact)
    dp.include_router(commands.router)       # 2. Commands (/help, /about, /profile, /reset)
    dp.include_router(stats.router)          # 3. Stats (/stats, button)
    dp.include_router(quizzes.router)        # 4. Quizzes (/quiz, button)
    dp.include_router(resources.router)      # 5. Resources (/qollanma, PDF fayllar)
    dp.include_router(kb_articles.router)    # 6. Knowledge base (/maqolalar, /faq)
    dp.include_router(courses.router)        # 7. Courses (🎓 Kurslar)
    dp.include_router(helpdesk.router)       # 8. Helpdesk (catch-all text) — MUST be last!

async def set_bot_commands():
    """BotFather commands ro'yxatini avtomatik o'rnatish."""
    commands_list = [
        BotCommand(command="start",      description="Botni ishga tushirish"),
        BotCommand(command="help",        description="Yordam va buyruqlar"),
        BotCommand(command="profile",     description="Mening profilim"),
        BotCommand(command="quiz",        description="Bilim testini boshlash"),
        BotCommand(command="qollanma",    description="PDF qo'llanmalar va fayllar"),
        BotCommand(command="maqolalar",   description="Bilimlar bazasi va maqolalar"),
        BotCommand(command="faq",         description="Ko'p so'raladigan savollar"),
        BotCommand(command="stats",       description="Mening statistikam"),
        BotCommand(command="reset",       description="Suhbat tarixini tozalash"),
        BotCommand(command="about",       description="Bot haqida ma'lumot"),
    ]
    try:
        from loader import bot as _bot
        await _bot.set_my_commands(commands_list)
        logging.info(f"✅ Bot commands o'rnatildi: {len(commands_list)} ta buyruq")
    except Exception as e:
        logging.warning(f"Bot commands o'rnatishda xatolik: {e}")

async def start_polling():
    logging.info("♻️ Polling rejimida ishga tushirilmoqda...")
    setup_handlers_and_middlewares()
    await set_bot_commands()
    await bot.delete_webhook(drop_pending_updates=True)
    try:
        await dp.start_polling(bot)
    except Exception as e:
        logging.error(f"Polling error: {e}")

def main():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', stream=sys.stdout)
    logging.info("--- BOT STARTUP INITIALIZING ---")
    
    if config.WEBHOOK_URL:
        logging.info(f"🌐 Webhook mode detected. Port: {config.WEBAPP_PORT}")
        setup_handlers_and_middlewares()
        
        async def on_startup_wrapper(bot: Bot):
            logging.info("Executing on_startup tasks...")
            await set_bot_commands()
            await on_startup(bot)
            logging.info("Startup tasks completed.")
            
        dp.startup.register(on_startup_wrapper)
        dp.shutdown.register(on_shutdown)

        app = web.Application()
        webhook_requests_handler = SimpleRequestHandler(
            dispatcher=dp,
            bot=bot,
        )
        webhook_requests_handler.register(app, path="/webhook")
        setup_application(app, dp, bot=bot)
        
        logging.info(f"Starting aiohttp web app on {config.WEBAPP_HOST}:{config.WEBAPP_PORT}...")
        web.run_app(app, host=config.WEBAPP_HOST, port=config.WEBAPP_PORT)
    else:
        logging.info("♻️ Defaulting to Polling mode...")
        try:
            asyncio.run(start_polling())
        except KeyboardInterrupt:
            logging.info("Bot interrupted.")

if __name__ == "__main__":
    main()
