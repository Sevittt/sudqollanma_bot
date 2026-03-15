from aiogram import Router, F
from aiogram.types import Message
from aiogram.enums import ChatAction
from services.ai_service import AIService
import logging

router = Router()

# Menu button texts that should NOT be sent to AI
MENU_BUTTONS = {
    "🧠 Test ishlash", "❓ Yordam so'rash", "👤 Profil", 
    "📊 Statistikam", "ℹ️ Yordam"
}

@router.message(F.text == "❓ Yordam so'rash")
async def helpdesk_intro(message: Message):
    """Prompt user to ask their IT question."""
    await message.answer(
        "💬 <b>IT Yordam</b>\n\n"
        "Savolingizni yozib yuboring — men sizga yordam beraman.\n\n"
        "Masalan:\n"
        "• \"E-SUD tizimiga faylni qanday yuklayman?\"\n"
        "• \"E-IMZO kalitim ishlamayapti\"\n"
        "• \"Videokonferensaloqa qotib qoldi\""
    )

@router.message(F.text)
async def helpdesk_handler(message: Message):
    """AI-powered IT helpdesk — answers technical questions."""
    # Ignore commands
    if message.text.startswith('/'):
        return
    
    # Ignore menu button presses (handled by their own routers)
    if message.text in MENU_BUTTONS:
        return

    # Send "typing" action to show the bot is thinking
    await message.bot.send_chat_action(chat_id=message.chat.id, action=ChatAction.TYPING)
    
    # Generate solution using the AI Service with user context
    response = await AIService.generate_solution(message.text, telegram_id=message.from_user.id)
    
    # Split long messages if needed (Telegram limit: 4096 chars)
    if len(response) > 4000:
        for x in range(0, len(response), 4000):
            await message.answer(response[x:x+4000])
    else:
        await message.answer(response)
