from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from services.firestore_service import FirestoreService
import logging

router = Router()

def get_courses_keyboard(courses):
    buttons = []
    for course in courses:
        buttons.append([InlineKeyboardButton(text=course['title'], callback_data=f"course_{course['id']}")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_modules_keyboard(course):
    buttons = []
    modules = course.get('modules', [])
    for i, module in enumerate(modules):
        buttons.append([InlineKeyboardButton(text=f"{i+1}. {module['title']}", callback_data=f"module_{course['id']}_{i}")])
    buttons.append([InlineKeyboardButton(text="⬅️ Kurslar ro'yxatiga", callback_data="course_list")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_lessons_keyboard(course_id, module, m_idx):
    buttons = []
    lessons = module.get('lessons', [])
    for i, lesson in enumerate(lessons):
        icon = "📹" if lesson['type'] == 'video' else "📄" if lesson['type'] == 'article' else "📂" if lesson['type'] == 'pdf' else "🧠"
        buttons.append([InlineKeyboardButton(text=f"{icon} {lesson['title']}", callback_data=f"lesson_{course_id}_{m_idx}_{i}")])
    buttons.append([InlineKeyboardButton(text="⬅️ Modullar ro'yxatiga", callback_data=f"course_{course_id}")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

@router.message(F.text == "🎓 Kurslar")
async def show_courses(message: Message):
    courses = await FirestoreService.get_courses()
    if not courses:
        await message.answer("Hozircha kurslar mavjud emas.")
        return
    
    await message.answer(
        "🎓 <b>O'quv kurslari</b>\n\nBilimingizni oshirish uchun quyidagi kurslardan birini tanlang:",
        reply_markup=get_courses_keyboard(courses),
        parse_mode="HTML"
    )

@router.callback_query(F.data == "course_list")
async def callback_show_courses(callback: CallbackQuery):
    courses = await FirestoreService.get_courses()
    await callback.message.edit_text(
        "🎓 <b>O'quv kurslari</b>\n\nBilimingizni oshirish uchun quyidagi kurslardan birini tanlang:",
        reply_markup=get_courses_keyboard(courses),
        parse_mode="HTML"
    )
    await callback.answer()

@router.callback_query(F.data.startswith("course_"))
async def show_course_details(callback: CallbackQuery):
    course_id = callback.data.split("_")[1]
    course = await FirestoreService.get_course_by_id(course_id)
    
    if not course:
        await callback.answer("Kurs topilmadi.", show_alert=True)
        return
    
    text = (
        f"📘 <b>{course['title']}</b>\n\n"
        f"{course['description']}\n\n"
        f"📊 Daraja: {course['difficulty']}\n"
        f"⏱ Davomiyligi: {course['estimatedMinutes']} daqiqa\n\n"
        f"📚 <b>Modullar:</b>"
    )
    
    await callback.message.edit_text(text, reply_markup=get_modules_keyboard(course), parse_mode="HTML")
    await callback.answer()

@router.callback_query(F.data.startswith("module_"))
async def show_module_details(callback: CallbackQuery):
    parts = callback.data.split("_")
    course_id = parts[1]
    m_idx = int(parts[2])
    
    course = await FirestoreService.get_course_by_id(course_id)
    if not course or m_idx >= len(course.get('modules', [])):
        await callback.answer("Modul topilmadi.", show_alert=True)
        return
    
    module = course['modules'][m_idx]
    text = (
        f"📦 <b>{module['title']}</b>\n\n"
        f"{module['description']}\n\n"
        f"📖 <b>Darslar:</b>"
    )
    
    await callback.message.edit_text(text, reply_markup=get_lessons_keyboard(course_id, module, m_idx), parse_mode="HTML")
    await callback.answer()

@router.callback_query(F.data.startswith("lesson_"))
async def show_lesson_content(callback: CallbackQuery):
    parts = callback.data.split("_")
    course_id = parts[1]
    m_idx = int(parts[2])
    l_idx = int(parts[3])
    
    course = await FirestoreService.get_course_by_id(course_id)
    if not course or m_idx >= len(course.get('modules', [])):
        await callback.answer("Dars topilmadi.", show_alert=True)
        return
    
    module = course['modules'][m_idx]
    if l_idx >= len(module.get('lessons', [])):
        await callback.answer("Dars topilmadi.", show_alert=True)
        return
        
    lesson = module['lessons'][l_idx]
    
    icon = "📹" if lesson['type'] == 'video' else "📄" if lesson['type'] == 'article' else "📂" if lesson['type'] == 'pdf' else "🧠"
    
    text = (
        f"{icon} <b>{lesson['title']}</b>\n\n"
        f"Turi: {lesson['type'].capitalize()}\n"
        f"Davomiyligi: {lesson.get('estimatedMinutes', 10)} daqiqa\n\n"
    )
    
    if lesson['type'] == 'video':
        text += "🎬 Videoni ko'rish uchun quyidagi havola yoki ID dan foydalaning:\n"
        text += f"<code>{lesson['refId']}</code>"
    elif lesson['type'] == 'article':
        text += "📝 Maqolani o'qish uchun botning 'Maqolalar' bo'limidan foydalanishingiz mumkin."
    elif lesson['type'] == 'pdf':
        text += "📂 Faylni 'Qo'llanmalar' bo'limidan yuklab olishingiz mumkin."
    elif lesson['type'] == 'quiz':
        text += "🧠 Testni 'Test ishlash' bo'limidan boshlashingiz mumkin."

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Darslar ro'yxatiga", callback_data=f"module_{course_id}_{m_idx}")]
    ])
    
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    await callback.answer()
