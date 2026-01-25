from aiogram import Router, F, types
from aiogram.filters import Command
from services import firestore_service, gemini_service

router = Router()

@router.message(Command("start"))
async def cmd_start(message: types.Message):
    user = await firestore_service.get_user(message.from_user.id)
    
    if user:
        await message.answer(f"Assalomu alaykum, {message.from_user.full_name}! Siz tizimga ulangansiz.")
    else:
        # Request contact
        kb = [
            [types.KeyboardButton(text="📱 Telefon raqamni yuborish", request_contact=True)]
        ]
        keyboard = types.ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)
        await message.answer("Assalomu alaykum! Iltimos, ilovadagi hisobingizni topish uchun telefon raqamingizni yuboring.", reply_markup=keyboard)

@router.message(F.contact)
async def handle_contact(message: types.Message):
    contact = message.contact
    phone = contact.phone_number
    # Normalize phone: +998...
    if not phone.startswith('+'):
        phone = '+' + phone
        
    success = await firestore_service.create_user_link(message.from_user.id, phone)
    
    if success:
        await message.answer("Rahmat! Hisobingiz muvaffaqiyatli bog'landi.", reply_markup=types.ReplyKeyboardRemove())
    else:
        await message.answer("Ushbu raqam bilan ilovada foydalanuvchi topilmadi. Iltimos, avval ilovadan ro'yxatdan o'ting.", reply_markup=types.ReplyKeyboardRemove())

@router.message()
async def handle_text(message: types.Message):
    await message.answer("🔍 Javob qidirilmoqda...")
    response = await gemini_service.generate_response(message.text)
    await message.answer(response)
