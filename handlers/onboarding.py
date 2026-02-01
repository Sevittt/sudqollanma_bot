from aiogram import Router, F
from aiogram.filters import CommandStart
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from services.firestore_service import FirestoreService
import logging

router = Router()

@router.message(CommandStart())
async def start_command(message: Message):
    telegram_id = message.from_user.id
    user = await FirestoreService.get_user(telegram_id)

    if user:
        name = user.get('firstName', 'Hamkasb')
        level = user.get('level', 1)
        xp = user.get('xp', 0)
        
        await message.answer(
            f"👋 <b>Assalomu alaykum, {name}!</b>\n\n"
            f"Siz 'Sud Digital Assistant' tizimiga kirdingiz.\n"
            f"📊 Darajangiz: {level} ({xp} XP)\n\n"
            f"💻 Men sizga E-SUD, E-XAT va boshqa tizimlar bo'yicha yordam beraman.\n"
            f"Savolingizni yozib yuboring yoki /quiz bosib bilimingizni sinang!",
            reply_markup=ReplyKeyboardRemove()
        )
    else:
        kb = ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="📱 Telefon raqamni yuborish", request_contact=True)]],
            resize_keyboard=True, one_time_keyboard=True
        )
        await message.answer(
            "Assalomu alaykum! Tizimdan foydalanish uchun shaxsingizni tasdiqlang.",
            reply_markup=kb
        )

@router.message(F.contact)
async def contact_handler(message: Message):
    logging.info(f"Contact received from user {message.from_user.id}")
    
    if message.contact.user_id != message.from_user.id:
        await message.answer("Iltimos, o'zingizning kontaktingizni yuboring.")
        return

    phone = message.contact.phone_number
    if not phone.startswith('+'): phone = '+' + phone
    
    logging.info(f"Linking phone {phone} to telegram_id {message.from_user.id}")
    
    try:
        status, user = await FirestoreService.link_telegram_to_phone(
            phone, message.from_user.id, message.from_user.full_name
        )
        logging.info(f"Link status: {status}")

        if status in ["linked", "created"]:
            await message.answer(
                f"✅ <b>Tabriklayman!</b>\n\n"
                f"Sizning hisobingiz muvaffaqiyatli ulandi.\n"
                f"Endi bemalol savollaringizni berishingiz mumkin.",
                reply_markup=ReplyKeyboardRemove()
            )
        else:
            await message.answer("Xatolik yuz berdi (bazaga bog'lanish). Iltimos keyinroq urinib ko'ring.")
    except Exception as e:
        logging.error(f"Error in contact_handler: {e}")
        await message.answer("Xatolik yuz berdi. Iltimos keyinroq urinib ko'ring.")
