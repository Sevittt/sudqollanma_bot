from aiogram import Router, F
from aiogram.filters import CommandStart
from aiogram.types import (
    Message, ReplyKeyboardMarkup, KeyboardButton, 
    ReplyKeyboardRemove, InlineKeyboardMarkup, InlineKeyboardButton,
    CallbackQuery
)
from services.firestore_service import FirestoreService
import logging

router = Router()

def get_main_menu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🧠 Test ishlash")],
            [KeyboardButton(text="👤 Profil"), KeyboardButton(text="❓ Yordam so'rash")]
        ],
        resize_keyboard=True
    )

def get_role_selection_keyboard():
    buttons = [
        [InlineKeyboardButton(text="👨‍⚖️ Sudya", callback_data="setrole_judge")],
        [InlineKeyboardButton(text="👨‍💻 Sudya yordamchisi", callback_data="setrole_assistant")],
        [InlineKeyboardButton(text="📂 Devonxona mudiri", callback_data="setrole_chancellery")],
        [InlineKeyboardButton(text="🗄 Arxiv mudiri", callback_data="setrole_archive")],
        [InlineKeyboardButton(text="💻 AKT xodimi", callback_data="setrole_ict_specialist")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

@router.message(CommandStart())
async def start_command(message: Message):
    telegram_id = message.from_user.id
    user = await FirestoreService.get_user(telegram_id)

    if user:
        name = user.get('firstName', 'Hamkasb')
        level = user.get('level', 1)
        xp = user.get('xp', 0)
        role = user.get('role', 'user')
        
        if role == 'user':
            await message.answer(
                f"👋 <b>Assalomu alaykum, {name}!</b>\n\n"
                f"Siz 'Sud Digital Assistant' tizimiga kirdingiz.\n"
                f"Iltimos, tizimdan to'liq foydalanish uchun o'z lavozimingizni tanlang:",
                reply_markup=get_role_selection_keyboard()
            )
        else:
            await message.answer(
                f"👋 <b>Assalomu alaykum, {name}!</b>\n\n"
                f"Siz 'Sud Digital Assistant' tizimiga kirdingiz.\n"
                f"📊 Darajangiz: {level} ({xp} XP)\n\n"
                f"💻 Men sizga E-SUD, E-XAT va boshqa tizimlar bo'yicha yordam beraman.\n"
                f"Savolingizni yozib yuboring yoki /quiz bosib bilimingizni sinang!",
                reply_markup=get_main_menu()
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
async def sync_user_by_contact(message: Message):
    phone = message.contact.phone_number
    if phone.startswith('+'):
        phone = phone[1:] 
        
    phone_clean = message.contact.phone_number.replace("+", "")
    tg_id = str(message.from_user.id)
    
    try:
        from loader import db
        status, user_data = await FirestoreService.link_telegram_to_phone(
           '+' + phone_clean,
           tg_id, 
           message.from_user.full_name
        )

        if status in ["linked", "created"]:
            xp = user_data.get('xp', 0)
            court_name = user_data.get('courtName', 'Siz biriktirilgan')
            full_name = user_data.get('firstName', message.from_user.full_name)
            role = user_data.get('role', 'user')
            
            if role == 'user':
                await message.answer(
                    f"Xush kelibsiz, {full_name}! 👋\n\n"
                    f"Sizni tanidim. Iltimos, lavozimingizni tanlang:",
                    reply_markup=get_role_selection_keyboard()
                )
            else:
                await message.answer(
                    f"Xush kelibsiz, {full_name}! 👋\n\n"
                    f"Sizni tanidim. Hozirda {xp} XP ballingiz bor.\n"
                    f"Siz {court_name} sudi xodimisiz.\n\n"
                    "Endi men sizga E-SUD yoki E-XAT bo'yicha tezkor yordam bera olaman!",
                    reply_markup=get_main_menu()
                )
        else:
             await message.answer("Sizning raqamingiz tizimda topilmadi. Iltimos, ilovada ro'yxatdan oting.")
             
    except Exception as e:
        logging.error(f"Error in sync: {e}")
        await message.answer("Xatolik yuz berdi.")

@router.callback_query(F.data.startswith("setrole_"))
async def set_role_callback(callback: CallbackQuery):
    role_key = callback.data.split("_", 1)[1]
    
    role_names = {
        "judge": "👨‍⚖️ Sudya",
        "assistant": "👨‍💻 Sudya yordamchisi",
        "chancellery": "📂 Devonxona mudiri",
        "archive": "🗄 Arxiv mudiri",
        "ict_specialist": "💻 AKT xodimi"
    }
    
    friendly_name = role_names.get(role_key, role_key)
    
    # Update explicitly in Firestore
    success = await FirestoreService.update_user_role(callback.from_user.id, role_key)
    
    if success:
        await callback.message.delete()
        await callback.message.answer(
            f"✅ Lavozimingiz <b>{friendly_name}</b> etib belgilandi!\n\n"
            f"Endi men sizga faqat shu lavozimga oid yordam berishga harakat qilaman.",
            parse_mode="HTML",
            reply_markup=get_main_menu()
        )
    else:
        await callback.answer("❌ Xatolik yuz berdi. Iltimos qayta urinib ko'ring.", show_alert=True)
    
    await callback.answer()

