from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from services.firestore_service import FirestoreService
from services.ai_service import AIService
import logging

router = Router()

# App deep link
APP_URL = "https://sudqollanma.uz"

class QuizState(StatesGroup):
    choosing_quiz = State()
    answering = State()

# ─── /quiz and "🧠 Test ishlash" button ────────────────────────
@router.message(Command("quiz"))
async def start_quiz(message: Message, state: FSMContext):
    """Show available quiz categories."""
    await _show_quiz_list(message, state)

@router.message(F.text == "🧠 Test ishlash")
async def start_quiz_button(message: Message, state: FSMContext):
    """Handle the test button press — same as /quiz."""
    await _show_quiz_list(message, state)

async def _show_quiz_list(message: Message, state: FSMContext):
    """Fetch all quizzes from Firestore and show as category buttons."""
    await state.clear()
    
    quizzes = await FirestoreService.get_all_quizzes()
    
    if not quizzes:
        # No quizzes in Firestore — show message with app link
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📱 Ilovadan test qo'shish", url=APP_URL)]
        ])
        await message.answer(
            "📭 Hozircha testlar mavjud emas.\n\n"
            "Ilovadan yangi testlar qo'shishingiz mumkin!",
            reply_markup=kb
        )
        return
    
    # Build quiz selection buttons
    buttons = []
    for quiz in quizzes:
        q_count = quiz.get('question_count', 0)
        title = quiz.get('title', 'Test')
        desc = quiz.get('description', '')
        
        # Button shows title + question count
        btn_text = f"📝 {title} ({q_count} savol)"
        buttons.append([InlineKeyboardButton(
            text=btn_text,
            callback_data=f"quiz_pick_{quiz['id']}"
        )])
    
    # Add "random all" option
    buttons.append([InlineKeyboardButton(
        text="🎲 Aralash test (barchasidan)",
        callback_data="quiz_pick_random"
    )])
    
    kb = InlineKeyboardMarkup(inline_keyboard=buttons)
    
    # Build quiz list text
    quiz_list = ""
    for i, quiz in enumerate(quizzes, 1):
        title = quiz.get('title', 'Test')
        desc = quiz.get('description', '')
        q_count = quiz.get('question_count', 0)
        desc_line = f"\n   📄 {desc}" if desc else ""
        quiz_list += f"\n{i}. <b>{title}</b> — {q_count} ta savol{desc_line}"
    
    await message.answer(
        f"🧠 <b>Mavzuni tanlang</b>\n"
        f"{quiz_list}\n\n"
        f"Qaysi mavzudan test yechmoqchisiz?",
        reply_markup=kb,
        parse_mode="HTML"
    )
    
    await state.set_state(QuizState.choosing_quiz)

# ─── Quiz selection handler ─────────────────────────────────────
@router.callback_query(F.data.startswith("quiz_pick_"))
async def pick_quiz(callback: CallbackQuery, state: FSMContext):
    """User picked a quiz category — load its questions."""
    quiz_id = callback.data.replace("quiz_pick_", "")
    
    await callback.message.edit_text("⏳ Savollar yuklanmoqda...")
    await _start_specific_quiz(callback.message, state, quiz_id)
    await callback.answer()

async def start_specific_quiz_from_deeplink(message: Message, state: FSMContext, quiz_id: str):
    """Start a specific quiz directly from a deep link."""
    await state.clear()
    msg = await message.answer("⏳ Savollar yuklanmoqda...")
    await _start_specific_quiz(msg, state, quiz_id)

async def _start_specific_quiz(message: Message, state: FSMContext, quiz_id: str):
    """Internal logic to fetch questions and start quiz flow."""
    if quiz_id == "random":
        # Random from all quizzes
        questions = await FirestoreService.get_random_quiz_questions(5)
        quiz_title = "Aralash test"
        quiz_id = "random_mix"
    else:
        # Get questions from specific quiz
        questions = await FirestoreService.get_quiz_questions_by_id(quiz_id)
        if questions:
            quiz_title = questions[0].get('quiz_title', 'Test')
        else:
            quiz_title = "Test"
    
    if not questions:
        await message.edit_text(
            "❌ Bu testda savollar topilmadi yoki test mavjud emas.\n"
            "Boshqa mavzuni tanlang: /quiz"
        )
        await state.clear()
        return
    
    total_q = len(questions)
    
    # Initialize quiz session
    await state.set_state(QuizState.answering)
    await state.update_data(
        questions=questions,
        current_index=0,
        total_correct=0,
        total_xp=0,
        quiz_id=quiz_id,
        quiz_title=quiz_title
    )
    
    await message.edit_text(
        f"📝 <b>{quiz_title}</b>\n\n"
        f"Jami {total_q} ta savol. Har bir to'g'ri javob = <b>+10 XP</b>\n\n"
        f"Boshlang! 👇",
        parse_mode="HTML"
    )
    
    # Small pause before first question
    import asyncio
    await asyncio.sleep(1)
    
    await _show_question(message, questions[0], 1, total_q)

async def _show_question(message, question, question_number, total_questions):
    """Display a quiz question with LABELED answer buttons (A, B, C, D)."""
    options = question.get("options", [])
    labels = ["🅰", "🅱", "🅲", "🅳"]
    
    # Build option text for the message body (full text visible)
    options_text = ""
    for i, opt in enumerate(options):
        label = labels[i] if i < len(labels) else f"{i+1}."
        options_text += f"\n{label}  {opt}"
    
    q_text = question.get("questionText", question.get("question", "Savol topilmadi"))
    
    # Buttons: compact 2x2 grid
    if len(options) == 4:
        buttons = [
            [InlineKeyboardButton(text=labels[0], callback_data="quiz_ans_0"),
             InlineKeyboardButton(text=labels[1], callback_data="quiz_ans_1")],
            [InlineKeyboardButton(text=labels[2], callback_data="quiz_ans_2"),
             InlineKeyboardButton(text=labels[3], callback_data="quiz_ans_3")]
        ]
    elif len(options) == 2:
        buttons = [
            [InlineKeyboardButton(text=labels[0], callback_data="quiz_ans_0"),
             InlineKeyboardButton(text=labels[1], callback_data="quiz_ans_1")]
        ]
    else:
        buttons = [
            [InlineKeyboardButton(text=labels[i] if i < len(labels) else str(i+1), 
                                  callback_data=f"quiz_ans_{i}")]
            for i in range(len(options))
        ]
    
    kb = InlineKeyboardMarkup(inline_keyboard=buttons)
    
    await message.edit_text(
        f"🧠 <b>Savol {question_number}/{total_questions}</b>\n\n"
        f"❓ {q_text}\n"
        f"{options_text}",
        reply_markup=kb,
        parse_mode="HTML"
    )

# ─── Answer handler ─────────────────────────────────────────────
@router.callback_query(F.data.startswith("quiz_ans_"))
async def check_answer(callback: CallbackQuery, state: FSMContext):
    """Check the answer and move to next question or show results."""
    data = await state.get_data()
    questions = data.get("questions", [])
    current_idx = data.get("current_index", 0)
    
    if not questions or current_idx >= len(questions):
        await callback.message.edit_text(
            "❌ Test ma'lumotlari topilmadi.\n"
            "Yangi test boshlash uchun /quiz ni bosing."
        )
        await callback.answer()
        await state.clear()
        return
    
    try:
        ans_idx = int(callback.data.split("_")[-1])
        current_q = questions[current_idx]
        total_correct = data.get("total_correct", 0)
        total_xp = data.get("total_xp", 0)
        total_q = len(questions)
        
        # Determine correct answer
        correct_answer = current_q.get("correctAnswer", "")
        options = current_q.get("options", [])
        explanation = current_q.get("explanation", "")
        labels = ["🅰", "🅱", "🅲", "🅳"]
        
        # Check answer
        selected_option = options[ans_idx] if 0 <= ans_idx < len(options) else ""
        is_correct = selected_option == correct_answer
        
        # Fallback: check by correct_index (AI-generated questions)
        if not is_correct and "correct_index" in current_q:
            is_correct = ans_idx == current_q["correct_index"]
        
        # Find correct label
        correct_label = "?"
        for ci, opt in enumerate(options):
            if opt == correct_answer:
                correct_label = labels[ci] if ci < len(labels) else str(ci+1)
                break
        
        if is_correct:
            total_correct += 1
            total_xp += 10
            result_line = "✅ <b>To'g'ri!</b> (+10 XP)"
        else:
            result_line = f"❌ <b>Noto'g'ri.</b> To'g'ri javob: {correct_label} {correct_answer}"
        
        next_idx = current_idx + 1
        
        # Last question?
        if next_idx >= total_q:
            await state.clear()
            
            # Save XP and stats
            if total_xp > 0:
                await FirestoreService.add_xp(callback.from_user.id, total_xp)
            if total_correct > 0:
                await FirestoreService.increment_quiz_correct(callback.from_user.id, total_correct)
            
            # Save quiz_attempt (synced with Flutter app)
            await FirestoreService.save_quiz_attempt(
                telegram_id=str(callback.from_user.id),
                quiz_id=data.get("quiz_id", "bot_quiz"),
                quiz_title=data.get("quiz_title", "Bot testi"),
                score=total_correct,
                total_questions=total_q
            )
            
            # Result message
            pct = (total_correct / total_q) * 100
            if pct >= 80:
                result_emoji, result_text = "🏆", "Ajoyib natija!"
            elif pct >= 60:
                result_emoji, result_text = "👍", "Yaxshi natija!"
            elif pct >= 40:
                result_emoji, result_text = "📚", "Yomon emas, lekin mashq qiling!"
            else:
                result_emoji, result_text = "💪", "Ko'proq o'qish kerak!"
            
            explanation_line = f"\n💡 <b>Izoh:</b> {explanation}" if explanation else ""
            
            app_button = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📱 Ilovada davom etish", url=APP_URL)],
                [InlineKeyboardButton(text="🔄 Boshqa mavzu tanlash", callback_data="quiz_restart")],
            ])
            
            await callback.message.edit_text(
                f"{result_line}{explanation_line}\n\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"{result_emoji} <b>{data.get('quiz_title', 'TEST')} YAKUNLANDI</b>\n\n"
                f"📊 Natija: <b>{total_correct}/{total_q}</b>\n"
                f"🎯 Foiz: {pct:.0f}%\n"
                f"💰 Yig'ilgan XP: <b>+{total_xp} XP</b>\n\n"
                f"{result_text}\n\n"
                f"📱 Ko'proq testlar uchun ilovaga kiring!",
                reply_markup=app_button,
                parse_mode="HTML"
            )
        else:
            # Feedback + next question
            explanation_line = f"\n💡 <b>Izoh:</b> {explanation}" if explanation else ""
            
            await callback.message.edit_text(
                f"{result_line}{explanation_line}\n\n"
                f"⏳ Keyingi savol...",
                parse_mode="HTML"
            )
            
            await state.update_data(
                current_index=next_idx,
                total_correct=total_correct,
                total_xp=total_xp
            )
            
            import asyncio
            await asyncio.sleep(1.5)
            
            await _show_question(callback.message, questions[next_idx], next_idx + 1, total_q)
        
    except Exception as e:
        logging.error(f"Quiz callback error: {e}")
        await callback.message.edit_text(
            "⚠️ Xatolik yuz berdi.\nYangi test uchun /quiz ni bosing."
        )
        await state.clear()
    
    await callback.answer()

# ─── Restart quiz callback ──────────────────────────────────────
@router.callback_query(F.data == "quiz_restart")
async def quiz_restart(callback: CallbackQuery, state: FSMContext):
    """Go back to quiz category selection."""
    await callback.answer()
    await _show_quiz_list(callback.message, state)
