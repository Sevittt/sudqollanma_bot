from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from services.firestore_service import FirestoreService
from handlers.onboarding import get_main_menu, ROLE_NAMES
import logging

router = Router()

APP_URL = "https://sudqollanma.uz"

# ─── /help Command ─────────────────────────────────────────────
@router.message(Command("help"))
async def help_command(message: Message):
    """Show all available commands and features."""
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📱 Ilovaga o'tish", url=APP_URL)]
    ])
    await message.answer(
        "📖 <b>Sud Digital Assistant — Buyruqlar</b>\n\n"
        "🔹 /start — Botni ishga tushirish\n"
        "🔹 /help — Shu ro'yxatni ko'rish\n"
        "🔹 /profile — Profilingiz ma'lumotlari\n"
        "🔹 /quiz — Raqamli bilim testi (5 ta savol)\n"
        "🔹 /stats — Statistikangiz\n"
        "🔹 /reset — Suhbat tarixini tozalash\n"
        "🔹 /about — Bot haqida ma'lumot\n\n"
        "💬 <b>Erkin yozing</b> — E-SUD, E-XAT yoki boshqa "
        "tizimlar bo'yicha savol bering, AI yordamchi javob beradi.\n\n"
        "📱 <b>Menyu tugmalari</b> — Pastdagi tugmalardan ham foydalaning.",
        reply_markup=get_main_menu()
    )

# ─── ℹ️ Yordam button (same as /help) ──────────────────────────
@router.message(F.text == "ℹ️ Yordam")
async def help_button(message: Message):
    """Handle the help button press — same as /help."""
    await help_command(message)

# ─── /about Command ────────────────────────────────────────────
@router.message(Command("about"))
async def about_command(message: Message):
    """Show information about the bot with app link."""
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🌐 sudqollanma.uz", url=APP_URL)]
    ])
    await message.answer(
        "ℹ️ <b>Sud Digital Assistant</b>\n\n"
        "🏛 Loyiha: <b>Sud Qo'llanma</b>\n"
        "🎯 Maqsad: Sud xodimlari raqamli kompetensiyasini oshirish\n\n"
        "🤖 AI Mentor: Gemini\n"
        "📦 Platforma: Telegram + Flutter + Firebase\n"
        "🌐 Veb-sayt: sudqollanma.uz\n"
        "👨‍💻 Versiya: 2.0\n\n"
        "Bot sizga quyidagilarda yordam beradi:\n"
        "• E-SUD tizimida ishlash\n"
        "• E-XAT orqali xat yuborish\n"
        "• E-IMZO sozlash va muammolarni hal qilish\n"
        "• Kompyuter savodxonligi bo'yicha maslahatlar\n"
        "• Axborot xavfsizligi bo'yicha bilimlar",
        reply_markup=kb
    )

# ─── /profile Command ──────────────────────────────────────────
@router.message(Command("profile"))
async def profile_command(message: Message):
    """Show user profile information."""
    user = await FirestoreService.get_user(message.from_user.id)
    
    if not user:
        await message.answer(
            "❌ Siz hali tizimga kirmadingiz.\n"
            "Iltimos, /start buyrug'ini bosing."
        )
        return
    
    name = user.get('firstName', 'Noma\'lum')
    role = user.get('role', 'user')
    role_display = ROLE_NAMES.get(role, role)
    xp = user.get('xp', 0)
    level = user.get('level', 1)
    court = user.get('courtName', 'Belgilanmagan')
    phone = user.get('phoneNumber', 'Belgilanmagan')
    
    # Calculate XP progress for next level (every 100 XP = 1 level)
    xp_for_next = (level * 100) - xp
    progress_pct = min(100, int((xp % 100) / 100 * 100))
    progress_bar = "█" * (progress_pct // 10) + "░" * (10 - progress_pct // 10)
    
    await message.answer(
        f"👤 <b>Sizning profilingiz</b>\n\n"
        f"📛 Ism: <b>{name}</b>\n"
        f"📋 Lavozim: {role_display}\n"
        f"🏛 Sud: {court}\n"
        f"📱 Telefon: {phone}\n\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"📊 <b>Daraja {level}</b> — {xp} XP\n"
        f"[{progress_bar}] {progress_pct}%\n"
        f"Keyingi darajagacha: {max(0, xp_for_next)} XP\n"
        f"━━━━━━━━━━━━━━━━━━\n\n"
        f"💡 Test yechib XP to'plang!",
        reply_markup=get_main_menu()
    )

# ─── 👤 Profil button ──────────────────────────────────────────
@router.message(F.text == "👤 Profil")
async def profile_button(message: Message):
    """Handle the profile button press — same as /profile."""
    await profile_command(message)

# ─── /reset Command ────────────────────────────────────────────
@router.message(Command("reset"))
async def reset_command(message: Message):
    """Clear conversation history."""
    success = await FirestoreService.clear_history(message.from_user.id)
    
    if success:
        await message.answer(
            "🗑 Suhbat tarixingiz tozalandi.\n\n"
            "Endi yangi savollar berishingiz mumkin.",
            reply_markup=get_main_menu()
        )
    else:
        await message.answer(
            "⚠️ Tarixni tozalashda xatolik yuz berdi.\n"
            "Iltimos, qayta urinib ko'ring."
        )
