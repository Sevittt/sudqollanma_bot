from aiogram import Router, F
from aiogram.types import Message
from aiogram.enums import ChatAction
from services.ai_service import AIService
import logging

router = Router()

MENU_BUTTONS = {
    "🧠 Test ishlash",
    "❓ Yordam so'rash",
    "❓ FAQ",
    "👤 Profil",
    "👤 Mening profilim",
    "📊 Statistikam",
    "ℹ️ Yordam",
    "📚 Qo'llanmalar",
    "📚 Qollanmalar",
    "🎓 Kurslar",
}

@router.message(F.text)
async def helpdesk_handler(message: Message):
    if message.text.startswith('/'):
        return

    if message.text in MENU_BUTTONS:
        return

    await message.bot.send_chat_action(chat_id=message.chat.id, action=ChatAction.TYPING)

    response = await AIService.generate_solution(message.text, telegram_id=message.from_user.id)

    if len(response) > 4000:
        for x in range(0, len(response), 4000):
            await message.answer(response[x:x+4000])
    else:
        await message.answer(response)
