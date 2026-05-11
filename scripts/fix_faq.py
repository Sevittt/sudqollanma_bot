import os
import sys

# Asosiy papka
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)

sys.stdout.reconfigure(encoding='utf-8')

# Fayl yo'llarini rootga nisbatan aniqlash
target_file = os.path.join(BASE_DIR, 'handlers', 'kb_articles.py')

if not os.path.exists(target_file):
    print(f"XATO - Fayl topilmadi: {target_file}")
    sys.exit(1)

with open(target_file, 'r', encoding='utf-8') as f:
    content = f.read()

# Eski faq_command ni yangi versiya bilan almashtirish
old_snippet = '@router.message(Command("faq"))\nasync def faq_command(message: Message):\n    """Ko\'p so\'raladigan savollar."""\n    await message.answer(\n        "❓ <b>Ko\'p so\'raladigan savollar (FAQ)</b>\\n\\n"\n        "Qaysi tizim bo\'yicha qiziqasiz?",\n        reply_markup=_build_category_keyboard("faq"),\n        parse_mode="HTML"\n    )'

new_snippet = '@router.message(Command("faq"))\nasync def faq_command(message: Message):\n    """Ko\'p so\'raladigan savollar."""\n    await _show_faq_menu(message)\n\n\n@router.message(F.text == "❓ FAQ")\nasync def faq_button(message: Message):\n    """Menyu tugmasi — /faq bilan bir xil."""\n    await _show_faq_menu(message)\n\n\nasync def _show_faq_menu(message: Message):\n    await message.answer(\n        "❓ <b>Ko\'p so\'raladigan savollar (FAQ)</b>\\n\\n"\n        "Qaysi tizim bo\'yicha qiziqasiz?",\n        reply_markup=_build_category_keyboard("faq"),\n        parse_mode="HTML"\n    )'

if old_snippet in content:
    content = content.replace(old_snippet, new_snippet)
    with open(target_file, 'w', encoding='utf-8') as f:
        f.write(content)
    print('OK - faq_button handler qoshildi')
else:
    print('XATO - eski matn topilmadi')
