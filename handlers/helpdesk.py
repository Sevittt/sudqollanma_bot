from aiogram import Router, F
from aiogram.types import Message
from aiogram.enums import ChatAction
from services.ai_service import AIService
import logging

router = Router()

@router.message(F.text)
async def helpdesk_handler(message: Message):
    # Ignore commands (like /start, /quiz)
    if message.text.startswith('/'):
        return

    # Send "typing" action to show the bot is thinking
    await message.bot.send_chat_action(chat_id=message.chat.id, action=ChatAction.TYPING)
    
    # Generate solution using the AI Service (IT Persona)
    response = await AIService.generate_solution(message.text)
    
    # Split long messages if needed
    if len(response) > 4000:
        for x in range(0, len(response), 4000):
            await message.answer(response[x:x+4000])
    else:
        await message.answer(response)
