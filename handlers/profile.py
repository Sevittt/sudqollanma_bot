from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from services.firestore_service import FirestoreService

router = Router()

@router.message(Command("profile"))
async def show_profile(message: Message):
    telegram_id = message.from_user.id
    user = await FirestoreService.get_user(telegram_id)

    if not user:
        await message.answer("Siz hali ro'yxatdan o'tmagansiz. /start ni bosing.")
        return

    name = user.get('firstName', 'Foydalanuvchi')
    xp = user.get('xp', 0)
    level = user.get('level', 1)
    role = user.get('role', 'user')

    # Simple formatting
    text = (
        f"👤 <b>Mening Profilim</b>\n\n"
        f"📛 Ism: {name}\n"
        f"⭐️ XP: {xp}\n"
        f"🏆 Daraja: {level}\n"
        f"🛡 Rol: {role}\n"
    )
    
    await message.answer(text)
