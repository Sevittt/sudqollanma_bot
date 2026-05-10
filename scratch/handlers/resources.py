"""
Handler: /qollanma — PDF qo'llanmalar va fayllar
Firestore 'resources' kolleksiyasidan fayllarni ko'rsatadi.
"""
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import (
    Message, CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton
)
from loader import get_db
import logging

router = Router()

# Resource type display names
RESOURCE_TYPE_NAMES = {
    "jibSud":   "⚖️ Jinoiy ishlar bo'yicha sud (JIB.SUD.UZ)",
    "fibSud":   "📋 Fuqarolik ishlar bo'yicha sud",
    "edoSud":   "📤 EDO — Elektron hujjat almashish (EDO.SUD.UZ)",
    "esud":     "🖥 E-SUD tizimi",
    "exat":     "📧 E-XAT tizimi",
    "eimzo":    "🔐 E-IMZO elektron imzo",
    "mysud":    "🌐 MY.SUD.UZ — Shaxsiy kabinet",
    "vks":      "📹 VKS — Videokonferensiya",
    "other":    "📎 Boshqa qo'llanmalar",
}


async def _get_resources(type_filter=None) -> list:
    """Firestore 'resources' kolleksiyasidan resurslar olish."""
    if not get_db():
        return []
    try:
        ref = get_db().collection('resources')
        if type_filter:
            docs = ref.where('type', '==', type_filter).stream()
        else:
            docs = ref.stream()

        results = []
        for doc in docs:
            data = doc.to_dict()
            data['id'] = doc.id
            results.append(data)

        # Sort by title
        results.sort(key=lambda x: x.get('title', ''))
        return results
    except Exception as e:
        logging.error(f"Error fetching resources: {e}")
        return []


def _build_type_selection_keyboard():
    """Resurs turi tanlash tugmalari."""
    buttons = [
        [InlineKeyboardButton(text=name, callback_data=f"res_type_{key}")]
        for key, name in RESOURCE_TYPE_NAMES.items()
    ]
    buttons.append([
        InlineKeyboardButton(text="📚 Barchasi", callback_data="res_type_all")
    ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


# ─── /qollanma Command ──────────────────────────────────────────
@router.message(Command("qollanma"))
async def qollanma_command(message: Message):
    """PDF qo'llanmalar va fayllar — tur bo'yicha tanlash."""
    await _show_type_selection(message)


@router.message(F.text.in_({"📚 Qo'llanmalar", "📚 Qollanmalar"}))
async def qollanma_button(message: Message):
    """Menyu tugmasi — /qollanma bilan bir xil."""
    await _show_type_selection(message)


async def _show_type_selection(message: Message):
    await message.answer(
        "📚 <b>Qo'llanmalar va fayllar</b>\n\n"
        "Qaysi tizim bo'yicha qo'llanma kerak?\n"
        "Tanlang 👇",
        reply_markup=_build_type_selection_keyboard(),
        parse_mode="HTML"
    )


# ─── Resource type callback ─────────────────────────────────────
@router.callback_query(F.data.startswith("res_type_"))
async def handle_resource_type(callback: CallbackQuery):
    """Tanlangan tur bo'yicha resurslarni ko'rsatish."""
    type_key = callback.data.replace("res_type_", "")
    await callback.message.edit_text("⏳ Yuklanmoqda...")

    if type_key == "all":
        resources = await _get_resources()
        type_label = "📚 Barcha qo'llanmalar"
    else:
        resources = await _get_resources(type_filter=type_key)
        type_label = RESOURCE_TYPE_NAMES.get(type_key, type_key)

    if not resources:
        buttons = [
            [InlineKeyboardButton(text="⬅️ Orqaga", callback_data="res_back")]
        ]
        await callback.message.edit_text(
            f"📭 <b>{type_label}</b>\n\n"
            "Hozircha bu bo'limda fayllar mavjud emas.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
            parse_mode="HTML"
        )
        await callback.answer()
        return

    # Build resource list with PDF buttons
    text = f"📚 <b>{type_label}</b>\n\n"
    buttons = []

    for i, res in enumerate(resources, 1):
        title = res.get('title', 'Nomsiz')
        desc = res.get('description', '')
        url = res.get('url', '')

        if desc:
            text += f"{i}. <b>{title}</b>\n   📄 {desc}\n\n"
        else:
            text += f"{i}. <b>{title}</b>\n\n"

        if url:
            buttons.append([
                InlineKeyboardButton(
                    text=f"📥 {i}. {title[:40]}",
                    url=url
                )
            ])

    buttons.append([
        InlineKeyboardButton(text="⬅️ Orqaga", callback_data="res_back")
    ])

    # Telegram message limit
    if len(text) > 4000:
        text = text[:3900] + "\n\n..."

    await callback.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "res_back")
async def resource_back(callback: CallbackQuery):
    """Tur tanlash sahifasiga qaytish."""
    await callback.message.edit_text(
        "📚 <b>Qo'llanmalar va fayllar</b>\n\n"
        "Qaysi tizim bo'yicha qo'llanma kerak?\n"
        "Tanlang 👇",
        reply_markup=_build_type_selection_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()
