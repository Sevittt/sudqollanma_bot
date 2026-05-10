from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message
from services.firestore_service import FirestoreService
from handlers.onboarding import get_main_menu
import logging

router = Router()

# ─── /stats Command ────────────────────────────────────────────
@router.message(Command("stats"))
async def stats_command(message: Message):
    """Show detailed user statistics."""
    stats = await FirestoreService.get_user_stats(message.from_user.id)
    
    if not stats:
        await message.answer(
            "❌ Statistika topilmadi.\n"
            "Iltimos, avval /start buyrug'ini bosing.",
            reply_markup=get_main_menu()
        )
        return
    
    xp = stats.get('xp', 0)
    level = stats.get('level', 1)
    quiz_count = stats.get('quiz_correct', 0)
    message_count = stats.get('message_count', 0)
    member_since = stats.get('member_since', 'Noma\'lum')
    
    # XP rank emoji based on level
    if level >= 10:
        rank_emoji = "🏆"
        rank_title = "Ustoz"
    elif level >= 7:
        rank_emoji = "🥇"
        rank_title = "Tajribali"
    elif level >= 4:
        rank_emoji = "🥈"
        rank_title = "O'rganuvchi"
    else:
        rank_emoji = "🥉"
        rank_title = "Yangi"
    
    await message.answer(
        f"📊 <b>Sizning statistikangiz</b>\n\n"
        f"{rank_emoji} Unvon: <b>{rank_title}</b>\n"
        f"📈 Daraja: {level} ({xp} XP)\n\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"🧠 Testlar: {quiz_count} ta to'g'ri javob\n"
        f"💬 Savollar: {message_count} ta suhbat\n"
        f"📅 A'zo: {member_since}\n"
        f"━━━━━━━━━━━━━━━━━━\n\n"
        f"💡 Ko'proq test yechib yuqori unvonga chiqing!",
        reply_markup=get_main_menu()
    )

# ─── 📊 Statistikam button ─────────────────────────────────────
@router.message(F.text == "📊 Statistikam")
async def stats_button(message: Message):
    """Handle the stats button press — same as /stats."""
    await stats_command(message)
