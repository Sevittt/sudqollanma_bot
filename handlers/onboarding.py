from aiogram import Router, F
from aiogram.filters import CommandStart
from aiogram.types import (
    Message, ReplyKeyboardMarkup, KeyboardButton,
    ReplyKeyboardRemove, InlineKeyboardMarkup, InlineKeyboardButton,
    CallbackQuery
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from services.firestore_service import FirestoreService
from firebase_admin import firestore
import logging

class OnboardingState(StatesGroup):
    question_1 = State()
    question_2 = State()
    question_3 = State()
    select_region = State()
    select_court_type = State()
    select_court = State()
    select_position = State()

COMPETENCY_QUIZ = [
    {
        "question": "1. 🔐 E-SUD tizimida hujjatni elektron imzolashda 'E-IMZO topilmadi' xatosi chiqsa, eng birinchi nimalar qilasiz?",
        "options": [
            "🅰️ E-IMZO modulini ishga tushirib, sahifani yangilayman",
            "🅱️ Kompyuterni o'chirib yoqaman",
            "🅲️ Viloyat ma'muriga qo'ng'iroq qilaman",
            "🅳️ Yangi elektron kalit sotib olaman"
        ],
        "correct_index": 0
    },
    {
        "question": "2. ⌨️ Sud hujjatlaridagi matnlarni tezkor nusxalash va joylash (Copy/Paste) uchun qaysi klaviatura tugmalaridan foydalaniladi?",
        "options": [
            "🅰️ Ctrl + C va Ctrl + V",
            "🅱️ Alt + C va Alt + V",
            "🅲️ Shift + C va Shift + V",
            "🅳️ Tab + C va Tab + V"
        ],
        "correct_index": 0
    },
    {
        "question": "3. 📧 Shubhali elektron pochta xabari (masalan, 'Siz yutdingiz! Havolaga kiring') kelganda xavfsizlik qoidasiga ko'ra nima qilish kerak?",
        "options": [
            "🅰️ Havolaga kirib, kiritilgan ma'lumotlarni ko'raman",
            "🅱️ Havolani ochmayman va xabarni o'chirib yuboraman",
            "🅲️ Barcha hamkasblarimga jo'nataman",
            "🅳️ Havolani telefonimdan ochib ko'raman"
        ],
        "correct_index": 1
    }
]

router = Router()

def get_main_menu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🎓 Kurslar"),          KeyboardButton(text="🧠 Test ishlash")],
            [KeyboardButton(text="📚 Qo'llanmalar"),      KeyboardButton(text="👤 Mening profilim")],
            [KeyboardButton(text="📊 Statistikam"),       KeyboardButton(text="❓ FAQ")],
            [KeyboardButton(text="ℹ️ Yordam")],
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

ROLE_NAMES = {
    "judge": "👨‍⚖️ Sudya",
    "assistant": "👨‍💻 Sudya yordamchisi",
    "chancellery": "📂 Devonxona mudiri",
    "archive": "🗄 Arxiv mudiri",
    "ict_specialist": "💻 AKT xodimi",
    "user": "👤 Foydalanuvchi",
    "admin": "🛡 Administrator",
}

POSITION_OPTIONS = [
    "Sudya", "Sudya yordamchisi", "Devonxona mudiri",
    "Arxiv mudiri", "Kotib", "AKT mutaxassisi", "Boshqa"
]

COURT_TYPES = {
    "jib": "⚖️ Jinoiy ishlar bo'yicha sud",
    "fib": "📋 Fuqarolik ishlar bo'yicha sud",
    "viloyat": "🏛 Viloyat sudi",
    "iqtisodiy": "💼 Iqtisodiy sud",
    "oliy": "🏛 Oliy sud",
}


@router.message(CommandStart())
async def start_command(message: Message, state: FSMContext):
    telegram_id = message.from_user.id
    user = await FirestoreService.get_user(telegram_id)

    args = message.text.split()
    deeplink_arg = args[1] if len(args) > 1 else None

    if user and deeplink_arg and deeplink_arg.startswith("quiz_"):
        quiz_id = deeplink_arg.replace("quiz_", "")
        from handlers.quizzes import start_specific_quiz_from_deeplink
        await start_specific_quiz_from_deeplink(message, state, quiz_id)
        return

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
            role_display = ROLE_NAMES.get(role, role)
            await message.answer(
                f"👋 <b>Assalomu alaykum, {name}!</b>\n\n"
                f"📋 Lavozim: {role_display}\n"
                f"📊 Daraja: {level} | {xp} XP\n\n"
                f"💻 Men sizga E-SUD, E-XAT va boshqa tizimlar bo'yicha yordam beraman.\n"
                f"Savolingizni yozib yuboring yoki 🧠 <b>Test ishlash</b> ni bosing!",
                reply_markup=get_main_menu()
            )
    else:
        await state.update_data(first_name=message.from_user.first_name)
        await message.answer(
            f"👋 <b>Assalomu alaykum, {message.from_user.first_name}!</b>\n\n"
            "Men — <b>Sud Digital Assistant</b>, sud xodimlari uchun raqamli yordamchi.\n\n"
            "💻 Tizimdan to'liq foydalanish uchun o'z lavozimingizni tanlang:",
            reply_markup=get_role_selection_keyboard()
        )


@router.message(F.contact)
async def sync_user_by_contact(message: Message, state: FSMContext):
    # OWASP Security: prevent identity spoofing
    if message.contact.user_id != message.from_user.id:
        logging.warning(
            f"Contact spoofing attempt! from_user={message.from_user.id}, "
            f"contact.user_id={message.contact.user_id}"
        )
        await message.answer(
            "⚠️ <b>Xavfsizlik ogohlantirishi!</b>\n\n"
            "Faqat o'zingizning telefon raqamingizni yuborishingiz mumkin.\n"
            "Boshqa kishining kontaktini yuborish taqiqlanadi.",
            reply_markup=ReplyKeyboardMarkup(
                keyboard=[[KeyboardButton(text="📱 Telefon raqamni yuborish", request_contact=True)]],
                resize_keyboard=True, one_time_keyboard=True
            )
        )
        return

    phone_clean = message.contact.phone_number.replace("+", "")
    tg_id = str(message.from_user.id)

    try:
        status, user_data = await FirestoreService.link_telegram_to_phone(
            '+' + phone_clean,
            tg_id,
            message.from_user.full_name
        )

        if status in ["linked", "created"]:
            digital_level = user_data.get('digital_level')
            if not digital_level:
                await state.update_data(score=0, phone_status=status, user_data=user_data)
                await message.answer(
                    "🎉 <b>Ajoyib!</b> Raqamingiz tasdiqlandi.\n\n"
                    "Ilovadan to'liq foydalanishdan oldin, sizning IT bilimlaringizni (Raqamli Kompetensiya) qisqacha aniqlab olamiz. "
                    "Bu bor-yo'g'i 3 ta savoldan iborat.\n\n"
                    "Tayyormisiz? Qani, boshladik! 👇",
                    reply_markup=ReplyKeyboardRemove()
                )
                await ask_competency_question(message, state, 0)
                return

            xp = user_data.get('xp', 0)
            court_name = user_data.get('courtName', '')
            full_name = user_data.get('firstName', message.from_user.full_name)
            role = user_data.get('role', 'user')
            court_info = f"\n🏛 Sud: {court_name}" if court_name else ""

            if role == 'user':
                await message.answer(
                    f"✅ <b>Xush kelibsiz, {full_name}!</b>\n\n"
                    f"Sizni tanidim.{court_info}\n\n"
                    f"Iltimos, lavozimingizni tanlang:",
                    reply_markup=get_role_selection_keyboard()
                )
            else:
                role_display = ROLE_NAMES.get(role, role)
                await message.answer(
                    f"✅ <b>Xush kelibsiz, {full_name}!</b>\n\n"
                    f"📋 Lavozim: {role_display}{court_info}\n"
                    f"📊 XP: {xp}\n\n"
                    "Endi men sizga E-SUD yoki E-XAT bo'yicha tezkor yordam bera olaman!",
                    reply_markup=get_main_menu()
                )
        else:
            await message.answer(
                "❌ Sizning raqamingiz tizimda topilmadi.\n\n"
                "Iltimos, avval <b>Sud Qo'llanma</b> ilovasida ro'yxatdan o'ting,\n"
                "keyin qayta /start buyrug'ini bosing."
            )

    except Exception as e:
        logging.error(f"Error in sync: {e}")
        await message.answer(
            "⚠️ Tizimda xatolik yuz berdi.\n"
            "Iltimos, biroz kutib qayta urinib ko'ring."
        )


async def ask_competency_question(message: Message, state: FSMContext, index: int):
    question_data = COMPETENCY_QUIZ[index]
    options = question_data["options"]

    kb = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🅰️"), KeyboardButton(text="🅱️")],
            [KeyboardButton(text="🅲️"), KeyboardButton(text="🅳️")]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )

    text = f"<b>{question_data['question']}</b>\n\n"
    for opt in options:
        text += f"{opt}\n"

    if index == 0:
        await state.set_state(OnboardingState.question_1)
    elif index == 1:
        await state.set_state(OnboardingState.question_2)
    elif index == 2:
        await state.set_state(OnboardingState.question_3)

    await message.answer(text, reply_markup=kb, parse_mode="HTML")


async def process_competency_answer(message: Message, state: FSMContext, current_idx: int, next_state):
    data = await state.get_data()
    score = data.get('score', 0)

    choices = ["🅰️", "🅱️", "🅲️", "🅳️"]
    if message.text not in choices:
        await message.answer("Iltimos, faqat pasdagi tugmalardan birini tanlang.")
        return

    user_answer_idx = choices.index(message.text)
    correct_idx = COMPETENCY_QUIZ[current_idx]['correct_index']

    if user_answer_idx == correct_idx:
        score += 1

    await state.update_data(score=score)

    if next_state:
        await ask_competency_question(message, state, current_idx + 1)
    else:
        level = "Boshlang'ich"
        if score == 2:
            level = "O'rta"
        elif score == 3:
            level = "Ilg'or"

        tg_id = message.from_user.id
        await FirestoreService.save_competency_level(tg_id, level, score)

        user_data = data.get('user_data', {})
        court_name = user_data.get('courtName', '')
        full_name = user_data.get('firstName', message.from_user.full_name)
        role = user_data.get('role', 'user')

        await message.answer(
            f"✅ <b>Tabriklaymiz! Test yakunlandi.</b>\n\n"
            f"To'g'ri javoblaringiz: <b>{score}/3</b>\n"
            f"Sizning Raqamli Kompetensiya darajangiz: <b>{level}</b>\n\n"
            f"Bu ma'lumot sizga tizimni samarali o'rganishingizda va biz yordam berishimizda kerak bo'ladi.",
            reply_markup=ReplyKeyboardRemove(),
            parse_mode="HTML"
        )
        await state.clear()

        if not court_name:
            await message.answer(
                f"🎉 <b>Barakalla, {full_name}!</b> Test yakunlandi.\n\n"
                f"✅ To'g'ri javoblar: <b>{score}/3</b>\n"
                f"Kompetensiya darajasi: <b>{level}</b>\n\n"
                f"Endi qaysi sudda ishlashingizni belgilaylik 👇",
                parse_mode="HTML"
            )
            await state.update_data(user_data=data.get('user_data', {}))
            await show_region_selection(message, state)
        else:
            role_display = ROLE_NAMES.get(role, role)
            court_info = f"\n🏛 Sud: {court_name}"
            await message.answer(
                f"🎉 <b>Barakalla, {full_name}!</b> Test yakunlandi.\n\n"
                f"✅ To'g'ri javoblar: <b>{score}/3</b> — Daraja: <b>{level}</b>\n"
                f"📋 Lavozim: {role_display}{court_info}\n\n"
                "Endi men sizga E-SUD, E-XAT va boshqa tizimlar bo'yicha yordam bera olaman!",
                reply_markup=get_main_menu(),
                parse_mode="HTML"
            )


@router.message(OnboardingState.question_1)
async def competency_answer_q1(message: Message, state: FSMContext):
    await process_competency_answer(message, state, 0, OnboardingState.question_2)

@router.message(OnboardingState.question_2)
async def competency_answer_q2(message: Message, state: FSMContext):
    await process_competency_answer(message, state, 1, OnboardingState.question_3)

@router.message(OnboardingState.question_3)
async def competency_answer_q3(message: Message, state: FSMContext):
    await process_competency_answer(message, state, 2, None)


async def show_region_selection(message: Message, state: FSMContext):
    try:
        regions = await FirestoreService.get_unique_regions()
    except Exception:
        regions = [
            "Toshkent shahri", "Toshkent viloyati", "Samarqand viloyati",
            "Farg'ona viloyati", "Andijon viloyati", "Namangan viloyati",
            "Sirdaryo viloyati", "Jizzax viloyati", "Navoiy viloyati",
            "Buxoro viloyati", "Qashqadaryo viloyati", "Surxondaryo viloyati",
            "Xorazm viloyati", "Qoraqalpog'iston"
        ]

    rows = []
    for i in range(0, len(regions), 2):
        row = [KeyboardButton(text=regions[i])]
        if i + 1 < len(regions):
            row.append(KeyboardButton(text=regions[i + 1]))
        rows.append(row)

    kb = ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True, one_time_keyboard=True)
    await state.set_state(OnboardingState.select_region)
    await message.answer(
        "🏠 <b>Qaysi hudud/viloyatda ishlaysiz?</b>\n\nRo'yxatdan o'z hududingizni tanlang:",
        reply_markup=kb,
        parse_mode="HTML"
    )


@router.message(OnboardingState.select_region)
async def handle_region_selection(message: Message, state: FSMContext):
    await state.update_data(region=message.text)

    rows = [[InlineKeyboardButton(text=name, callback_data=f"courttype_{code}")]
            for code, name in COURT_TYPES.items()]
    kb = InlineKeyboardMarkup(inline_keyboard=rows)

    await state.set_state(OnboardingState.select_court_type)
    await message.answer(
        f"✅ <b>{message.text}</b>\n\nSud turini tanlang:",
        reply_markup=kb,
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("courttype_"), OnboardingState.select_court_type)
async def handle_court_type_selection(callback: CallbackQuery, state: FSMContext):
    court_type = callback.data.split("_", 1)[1]
    data = await state.get_data()
    region = data.get("region", "")

    await state.update_data(courtType=court_type)
    await callback.message.edit_reply_markup(reply_markup=None)

    try:
        courts = await FirestoreService.get_courts_by_region_and_type(region, court_type)
    except Exception:
        courts = []

    if not courts:
        await state.set_state(OnboardingState.select_court)
        await callback.message.answer(
            "📝 Sud nomini qo'lda kiriting:",
            reply_markup=ReplyKeyboardRemove()
        )
        await callback.answer()
        return

    if len(courts) <= 8:
        rows = [[KeyboardButton(text=c["courtName"])] for c in courts]
    else:
        rows = []
        for i in range(0, len(courts), 2):
            row = [KeyboardButton(text=courts[i]["courtName"])]
            if i + 1 < len(courts):
                row.append(KeyboardButton(text=courts[i + 1]["courtName"]))
            rows.append(row)

    kb = ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True, one_time_keyboard=True)
    await state.set_state(OnboardingState.select_court)
    await callback.message.answer(
        f"🏛 <b>Qaysi sudda ishlaysiz?</b>\n({region} — {COURT_TYPES.get(court_type, court_type)})",
        reply_markup=kb,
        parse_mode="HTML"
    )
    await callback.answer()


@router.message(OnboardingState.select_court)
async def handle_court_selection(message: Message, state: FSMContext):
    await state.update_data(courtName=message.text)

    rows = [[KeyboardButton(text=pos)] for pos in POSITION_OPTIONS]
    kb = ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True, one_time_keyboard=True)

    await state.set_state(OnboardingState.select_position)
    await message.answer(
        f"✅ <b>{message.text}</b>\n\n👔 Lavozimingizni tanlang:",
        reply_markup=kb,
        parse_mode="HTML"
    )


@router.message(OnboardingState.select_position)
async def handle_position_selection(message: Message, state: FSMContext):
    data = await state.get_data()
    position = message.text
    tg_id = message.from_user.id

    court_data = {
        "region": data.get("region", ""),
        "courtType": data.get("courtType", ""),
        "courtName": data.get("courtName", ""),
        "position": position,
    }

    try:
        await FirestoreService.update_court_info(tg_id, court_data)
    except Exception as e:
        logging.error(f"Court update xatolik: {e}")

    await state.clear()
    full_name = data.get("user_data", {}).get("firstName", message.from_user.first_name)

    await message.answer(
        f"🎉 <b>Ajoyib! Hamma narsa saqlandi.</b>\n\n"
        f"🏛 Sud: <b>{court_data['courtName']}</b>\n"
        f"📍 Hudud: {court_data['region']}\n"
        f"👔 Lavozim: {position}\n\n"
        f"Endi men sizga E-SUD, E-XAT va boshqa tizimlar bo'yicha yordam bera olaman!\n"
        f"Savolingizni yozib yuboring yoki 🧠 <b>Test ishlash</b> ni bosing!",
        reply_markup=get_main_menu(),
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("setrole_"))
async def set_role_callback(callback: CallbackQuery, state: FSMContext):
    role_key = callback.data.split("_", 1)[1]
    friendly_name = ROLE_NAMES.get(role_key, role_key)
    tg_id = callback.from_user.id

    user = await FirestoreService.get_user(tg_id)

    if not user:
        user_data = {
            'telegram_id': str(tg_id),
            'firstName': callback.from_user.first_name,
            'fullName': callback.from_user.full_name,
            'role': role_key,
            'xp': 0,
            'level': 1,
            'quiz_correct': 0,
            'createdAt': firestore.SERVER_TIMESTAMP,
            'last_updated_by': 'telegram_bot'
        }
        await FirestoreService.create_user(user_data)

        await callback.message.delete()
        await callback.message.answer(
            f"✅ Lavozimingiz <b>{friendly_name}</b> etib belgilandi!\n\n"
            "Endi IT bilimlaringizni (Raqamli Kompetensiya) qisqacha aniqlab olamiz. "
            "Bu bor-yo'g'i 3 ta savoldan iborat.\n\n"
            "Tayyormisiz? Qani, boshladik! 👇"
        )
        await state.update_data(score=0, user_data=user_data)
        await ask_competency_question(callback.message, state, 0)
    else:
        await FirestoreService.update_user_role(tg_id, role_key)
        await callback.message.delete()

        court_name = user.get("courtName", "")
        if not court_name:
            await callback.message.answer(
                f"✅ Lavozimingiz <b>{friendly_name}</b> etib belgilandi!\n\n"
                f"Endi qaysi sudda ishlashingizni belgilaylik:",
                parse_mode="HTML"
            )
            await state.update_data(user_data=user)
            await show_region_selection(callback.message, state)
        else:
            await callback.message.answer(
                f"✅ Lavozimingiz <b>{friendly_name}</b> etib belgilandi!\n\n"
                f"🏛 Sud: {court_name}\n"
                f"Endi men sizga E-SUD, E-XAT va boshqa tizimlar bo'yicha yordam bera olaman!",
                parse_mode="HTML",
                reply_markup=get_main_menu()
            )

    await callback.answer()
