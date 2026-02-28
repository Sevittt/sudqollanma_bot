from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from services.firestore_service import FirestoreService
from services.ai_service import AIService
import logging

router = Router()

class QuizState(StatesGroup):
    answering = State()

@router.message(Command("quiz"))
async def start_quiz(message: Message, state: FSMContext):
    msg = await message.answer("🔄 Soniya kutib turing, siz uchun AI maxsus test tuzmoqda...")
    
    quiz_data = await AIService.generate_quiz(str(message.from_user.id))
    
    if not quiz_data:
        await msg.edit_text("❌ Test yaratishda xatolik yuz berdi. Iltimos, qayta urinib ko'ring.")
        return
        
    await state.set_state(QuizState.answering)
    await state.update_data(quiz_data=quiz_data)
    
    buttons = [
        [InlineKeyboardButton(text=opt, callback_data=f"quiz_ans_{i}")]
        for i, opt in enumerate(quiz_data.get("options", []))
    ]
    kb = InlineKeyboardMarkup(inline_keyboard=buttons)
    
    question_text = quiz_data.get("question", "Savol topilmadi")
    
    await msg.edit_text(
        f"🧠 <b>Raqamli bilim testi</b>\n\n{question_text}",
        reply_markup=kb,
        parse_mode="HTML"
    )

@router.callback_query(F.data.startswith("quiz_ans_"))
async def check_answer(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    quiz_data = data.get("quiz_data")
    
    if not quiz_data:
        await callback.message.edit_text("❌ Test ma'lumotlari topilmadi. Yana /quiz ni bosing.")
        await callback.answer()
        return
        
    try:
        ans_idx = int(callback.data.split("_")[-1])
        correct_idx = quiz_data.get("correct_index", -1)
        explanation = quiz_data.get("explanation", "")
        
        await state.clear()
        
        if ans_idx == correct_idx:
            xp_reward = 10
            await FirestoreService.add_xp(callback.from_user.id, xp_reward)
            await callback.message.edit_text(
                f"✅ <b>To'g'ri!</b>\n\n"
                f"Siz {xp_reward} XP oldingiz.\n\n"
                f"💡 <b>Izoh:</b> {explanation}",
                parse_mode="HTML"
            )
        else:
            await callback.message.edit_text(
                f"❌ <b>Noto'g'ri javob.</b>\n\n"
                f"💡 <b>Izoh:</b> {explanation}\n\n"
                f"Yana urinib ko'rish uchun /quiz ni bosing.",
                parse_mode="HTML"
            )
    except Exception as e:
        logging.error(f"Quiz callback error: {e}")
        await callback.message.edit_text("Xatolik yuz berdi.")
        
    await callback.answer()
