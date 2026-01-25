from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from services.firestore_service import FirestoreService

router = Router()

# Simple hardcoded quiz for MVP
QUIZ_DATA = {
    "question": "E-SUD tizimiga kirish uchun qaysi kalit kerak?",
    "options": ["Login/Parol", "E-IMZO", "Pasport seriyasi"],
    "correct_index": 1, 
    "xp_reward": 10
}

@router.message(Command("quiz"))
async def start_quiz(message: Message):
    buttons = [
        [InlineKeyboardButton(text=opt, callback_data=f"quiz_ans_{i}")]
        for i, opt in enumerate(QUIZ_DATA["options"])
    ]
    kb = InlineKeyboardMarkup(inline_keyboard=buttons)
    
    await message.answer(
        f"🧠 <b>Raqamli Bilim Testi</b>\n\n{QUIZ_DATA['question']}",
        reply_markup=kb
    )

@router.callback_query(F.data.startswith("quiz_ans_"))
async def check_answer(callback: CallbackQuery):
    ans_idx = int(callback.data.split("_")[-1])
    
    if ans_idx == QUIZ_DATA["correct_index"]:
        # Atomic XP Update
        await FirestoreService.add_xp(callback.from_user.id, QUIZ_DATA["xp_reward"])
        await callback.message.edit_text(
            f"✅ <b>To'g'ri!</b>\n\n"
            f"Siz {QUIZ_DATA['xp_reward']} XP oldingiz.\n"
            f"E-SUD tizimiga faqat E-IMZO orqali kiriladi."
        )
    else:
        await callback.message.edit_text(
            f"❌ <b>Noto'g'ri javob.</b>\n\n"
            f"E-SUD ga kirish uchun E-IMZO kerak bo'ladi."
        )
    await callback.answer()
