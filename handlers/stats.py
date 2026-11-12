from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message
from services.firestore_service import FirestoreService
from handlers.onboarding import get_main_menu
from services import gamification
import logging

# Ilova darajalari uchun belgi
LEVEL_EMOJI = {
    "levelBeginner": "🥉",
    "levelIntermediate": "🥉",
    "levelAdvanced": "🥈",
    "levelSpecialist": "🥈",
    "levelExpert": "🥇",
    "levelMaster": "🏆",
}

router = Router()

@router.message(Command("stats"))
async def stats_command(message: Message):
    stats = await FirestoreService.get_user_stats(message.from_user.id)

    if not stats:
        await message.answer(
            "❌ Statistika topilmadi.\n"
            "Iltimos, avval /start buyrug'ini bosing.",
            reply_markup=get_main_menu()
        )
        return

    xp = stats.get('xp', 0)
    level = stats.get('level', 'levelBeginner')
    quiz_count = stats.get('quiz_correct', 0)
    message_count = stats.get('message_count', 0)
    member_since = stats.get('member_since', "Noma'lum")

    rank_emoji = LEVEL_EMOJI.get(level, "🥉")
    rank_title = gamification.level_label(level)

    await message.answer(
        f"📊 <b>Sizning statistikangiz</b>\n\n"
        f"{rank_emoji} Daraja: <b>{rank_title}</b> ({xp} XP)\n\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"🧠 Testlar: {quiz_count} ta to'g'ri javob\n"
        f"💬 Savollar: {message_count} ta suhbat\n"
        f"📅 A'zo: {member_since}\n"
        f"━━━━━━━━━━━━━━━━━━\n\n"
        f"💡 Ko'proq test yechib yuqori unvonga chiqing!",
        reply_markup=get_main_menu()
    )

@router.message(F.text == "📊 Statistikam")
async def stats_button(message: Message):
    await stats_command(message)
