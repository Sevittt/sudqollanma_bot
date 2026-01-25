from aiogram import Router, F
from aiogram.types import Message
from aiogram.enums import ChatAction
from services.gemini_service import GeminiService
import logging

router = Router()

@router.message(F.text)
async def ai_chat_handler(message: Message):
    # Ignore commands
    if message.text.startswith('/'):
        return

    # Send "typing" action
    await message.bot.send_chat_action(chat_id=message.chat.id, action=ChatAction.TYPING)
    
    response = await GeminiService.generate_response(message.text)
    
    # Split long messages if needed (Telegram limit is 4096 chars)
    if len(response) > 4000:
        for x in range(0, len(response), 4000):
            await message.answer(response[x:x+4000])
    else:
        await message.answer(response)
