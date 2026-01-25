from aiogram import Router, F
from aiogram.filters import CommandStart
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from services.firestore_service import FirestoreService
import logging

router = Router()

@router.message(CommandStart())
async def bot_start(message: Message):
    telegram_id = message.from_user.id
    user = await FirestoreService.get_user(telegram_id)

    if user:
        name = user.get('firstName', 'Foydalanuvchi')
        xp = user.get('xp', 0)
        await message.answer(
            f"Assalomu alaykum, {name}!\n"
            f"Siz tizimga muvaffaqiyatli kirdingiz.\n"
            f"Sizning balingiz: {xp} XP.",
            reply_markup=ReplyKeyboardRemove()
        )
    else:
        # Request Contact
        kb = ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="📱 Telefon raqamni yuborish", request_contact=True)]
            ],
            resize_keyboard=True,
            one_time_keyboard=True
        )
        await message.answer(
            "Assalomu alaykum! Botdan foydalanish uchun iltimos, telefon raqamingizni yuboring.",
            reply_markup=kb
        )

@router.message(F.contact)
async def handle_contact(message: Message):
    contact = message.contact
    
    # Security Check: Ensure the contact belongs to the sender
    if contact.user_id != message.from_user.id:
        await message.answer("Iltimos, o'zingizning telefon raqamingizni yuboring.")
        return

    phone_number = contact.phone_number
    # Ensure phone number starts with + if missing (Telegram sometimes sends without)
    if not phone_number.startswith('+'):
        phone_number = '+' + phone_number

    full_name = message.from_user.full_name
    telegram_id = message.from_user.id

    status, user_data = await FirestoreService.link_telegram_to_phone(phone_number, telegram_id, full_name)

    if status == "linked":
        await message.answer(
            f"Rahmat! Sizning hisobingiz topildi va botga ulandi.\n"
            f"Xush kelibsiz, {user_data.get('firstName')}!",
            reply_markup=ReplyKeyboardRemove()
        )
    elif status == "created":
        await message.answer(
            f"Rahmat! Siz uchun yangi hisob yaratildi.\n"
            f"Xush kelibsiz, {full_name}!",
            reply_markup=ReplyKeyboardRemove()
        )
    else:
        await message.answer(
            "Xatolik yuz berdi. Iltimos keyinroq urinib ko'ring.",
            reply_markup=ReplyKeyboardRemove()
        )
