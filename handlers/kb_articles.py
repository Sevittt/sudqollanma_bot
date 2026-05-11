from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import (
    Message, CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton
)
from loader import get_db
import logging

router = Router()

CATEGORY_NAMES = {
    "esud":    "🖥 E-SUD tizimi",
    "exat":    "📧 E-XAT tizimi",
    "edo":     "📤 EDO tizimi",
    "mysud":   "🌐 MY.SUD.UZ",
    "general": "💻 Umumiy IT",
    "system":  "🔧 Tizim",
}


async def _get_knowledge_articles(category: str = None, limit: int = 20) -> list:
    if not get_db():
        return []
    try:
        ref = get_db().collection('knowledge_base')
        if category and category != "all":
            docs = ref.where('category', '==', category).limit(limit).stream()
        else:
            docs = ref.limit(limit).stream()
        results = []
        for doc in docs:
            data = doc.to_dict()
            data['id'] = doc.id
            results.append(data)
        return results
    except Exception as e:
        logging.error(f"Error fetching knowledge_base: {e}")
        return []


async def _get_faqs(category: str = None, limit: int = 20) -> list:
    if not get_db():
        return []
    try:
        ref = get_db().collection('faqs')
        if category and category != "all":
            docs = ref.where('category', '==', category).limit(limit).stream()
        else:
            docs = ref.limit(limit).stream()
        results = []
        for doc in docs:
            data = doc.to_dict()
            data['id'] = doc.id
            results.append(data)
        return results
    except Exception as e:
        logging.error(f"Error fetching faqs: {e}")
        return []


def _build_category_keyboard(prefix: str):
    buttons = [
        [InlineKeyboardButton(text=name, callback_data=f"{prefix}_cat_{key}")]
        for key, name in CATEGORY_NAMES.items()
    ]
    buttons.append([InlineKeyboardButton(text="📋 Barchasi", callback_data=f"{prefix}_cat_all")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


# ─── /maqolalar ─────────────────────────────────────────────────
@router.message(Command("maqolalar"))
async def maqolalar_command(message: Message):
    await message.answer(
        "📖 <b>Bilimlar bazasi</b>\n\n"
        "Qaysi mavzu bo'yicha maqola kerak?",
        reply_markup=_build_category_keyboard("kb"),
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("kb_cat_"))
async def handle_kb_category(callback: CallbackQuery):
    cat = callback.data.replace("kb_cat_", "")
    await callback.message.edit_text("⏳ Maqolalar yuklanmoqda...")

    articles = await _get_knowledge_articles(category=cat)

    if not articles:
        await callback.message.edit_text(
            "📭 Bu bo'limda hozircha maqolalar mavjud emas.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⬅️ Orqaga", callback_data="kb_back")]
            ])
        )
        await callback.answer()
        return

    cat_name = CATEGORY_NAMES.get(cat, "Barcha maqolalar")
    text = f"📖 <b>{cat_name}</b> — {len(articles)} ta maqola\n\n"
    buttons = []

    for i, art in enumerate(articles, 1):
        title = art.get('title', 'Nomsiz')
        desc = art.get('description', '')
        system_id = art.get('systemId', '')
        tag = f"[{system_id}] " if system_id else ""
        text += f"{i}. {tag}<b>{title}</b>\n"
        if desc:
            text += f"   📝 {desc[:100]}...\n"
        text += "\n"
        buttons.append([
            InlineKeyboardButton(
                text=f"📄 {i}. {title[:45]}",
                callback_data=f"kb_read_{art['id'][:40]}"
            )
        ])

    buttons.append([InlineKeyboardButton(text="⬅️ Orqaga", callback_data="kb_back")])

    if len(text) > 4000:
        text = text[:3900] + "\n\n..."

    await callback.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("kb_read_"))
async def handle_kb_read(callback: CallbackQuery):
    article_id = callback.data.replace("kb_read_", "")
    await callback.message.edit_text("⏳ Yuklanmoqda...")

    try:
        doc = get_db().collection('knowledge_base').document(article_id).get()
        if not doc.exists:
            await callback.message.edit_text(
                "❌ Maqola topilmadi.",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="⬅️ Orqaga", callback_data="kb_back")]
                ])
            )
            await callback.answer()
            return

        data = doc.to_dict()
        title = data.get('title', 'Nomsiz')
        content = data.get('content', data.get('text', 'Matn mavjud emas'))
        pdf_url = data.get('pdfUrl', '')
        system_id = data.get('systemId', '')

        try:
            from google.cloud.firestore_v1 import Increment as _Inc
            doc.reference.update({'views': _Inc(1)})
        except Exception:
            pass

        header = f"📖 <b>{title}</b>\n"
        if system_id:
            header += f"🏷 Tizim: {system_id}\n"
        header += "\n"

        max_content = 4000 - len(header) - 200
        content_show = content[:max_content] + "\n\n... (matn qisqartirildi)" if len(content) > max_content else content

        buttons = []
        if pdf_url:
            buttons.append([InlineKeyboardButton(text="📥 PDF yuklab olish", url=pdf_url)])
        buttons.append([InlineKeyboardButton(text="⬅️ Orqaga", callback_data="kb_back")])

        await callback.message.edit_text(
            header + content_show,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
            parse_mode="HTML"
        )
    except Exception as e:
        logging.error(f"kb_read error: {e}")
        await callback.message.edit_text(
            "⚠️ Maqolani yuklashda xatolik yuz berdi.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⬅️ Orqaga", callback_data="kb_back")]
            ])
        )
    await callback.answer()


@router.callback_query(F.data == "kb_back")
async def kb_back(callback: CallbackQuery):
    await callback.message.edit_text(
        "📖 <b>Bilimlar bazasi</b>\n\n"
        "Qaysi mavzu bo'yicha maqola kerak?",
        reply_markup=_build_category_keyboard("kb"),
        parse_mode="HTML"
    )
    await callback.answer()


# ─── /faq ──────────────────────────────────────────────────────
@router.message(Command("faq"))
async def faq_command(message: Message):
    await _show_faq_menu(message)

@router.message(F.text == "❓ FAQ")
async def faq_button(message: Message):
    await _show_faq_menu(message)


async def _show_faq_menu(message: Message):
    await message.answer(
        "❓ <b>Ko'p so'raladigan savollar (FAQ)</b>\n\n"
        "Qaysi tizim bo'yicha qiziqasiz?",
        reply_markup=_build_category_keyboard("faq"),
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("faq_cat_"))
async def handle_faq_category(callback: CallbackQuery):
    cat = callback.data.replace("faq_cat_", "")
    await callback.message.edit_text("⏳ Yuklanmoqda...")

    faqs = await _get_faqs(category=cat)
    cat_name = CATEGORY_NAMES.get(cat, "Barcha savollar")

    if not faqs:
        await callback.message.edit_text(
            "📭 Bu bo'limda hozircha savollar mavjud emas.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⬅️ Orqaga", callback_data="faq_back")]
            ])
        )
        await callback.answer()
        return

    text = f"❓ <b>{cat_name}</b> — {len(faqs)} ta savol\n\n"
    for i, faq in enumerate(faqs, 1):
        question = faq.get('question', 'Savol')
        answer = faq.get('answer', '')
        difficulty = faq.get('difficulty', '')

        diff_icon = {"boshlang'ich": "🟢", "o'rta": "🟡", "murakkab": "🔴"}.get(
            difficulty.lower() if difficulty else '', "⚪"
        )
        text += f"{diff_icon} <b>S{i}: {question}</b>\n"
        if answer:
            short_answer = answer[:200] + ("..." if len(answer) > 200 else "")
            text += f"💡 {short_answer}\n\n"
        else:
            text += "\n"

        if len(text) > 3800:
            text += f"\n... va {len(faqs) - i} ta savol ko'rsatilmadi"
            break

    await callback.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Orqaga", callback_data="faq_back")]
        ]),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "faq_back")
async def faq_back(callback: CallbackQuery):
    await callback.message.edit_text(
        "❓ <b>Ko'p so'raladigan savollar (FAQ)</b>\n\n"
        "Qaysi tizim bo'yicha qiziqasiz?",
        reply_markup=_build_category_keyboard("faq"),
        parse_mode="HTML"
    )
    await callback.answer()
