import google.generativeai as genai
import config
from loader import db, model
import logging
import json

SYSTEM_INSTRUCTION = r"""
Sening roling: O'zbekiston sud tizimi xodimlari uchun "Raqamli Mentor". 
Sening bilimlar bazang quyidagi rasmiy qo'llanmalarga asoslangan:
1. E-XSUD: Jinoiy, ma'muriy va fuqarolik ishlarini ro'yxatga olish tartibi.
2. JIB.SUD.UZ: Jinoiy ishlarni "bazaga urish" va natijalarni qayd etish.
3. E-IMZO: Hujjatlarni imzolashdagi texnik muammolar (C:\E-IMZO drayveri).
4. Sud iyerarxiyasi: Tuman, shahar, viloyat va Oliy sud xodimlarining vazifalari.

Qoidalar:
- Faqat sud tizimiga oid IT va texnik savollarga javob ber.
- Agar foydalanuvchi tuman sudi kotibi bo'lsa, unga operatsion (bazaga kiritish) bo'yicha yordam ber.
- Agar foydalanuvchi Oliy suddan bo'lsa, unga tahliliy va statistik amallar bo'yicha javob ber.
- Ohanging: Professional, qo'llab-quvvatlovchi va "hormang" kabi o'zbekona empatiya elementlari bilan boyitilgan.
- ChatGPT kabi umumiy emas, aynan bizning ichki qo'llanmalar asosida "qadam-baqadam" yo'l ko'rsat.
"""

# Gemini modelini chaqirishda ushbu instructionni ishlating:
# model = genai.GenerativeModel(model_name="gemini-3.0-flash", system_instruction=SYSTEM_INSTRUCTION)

class AIService:
    @staticmethod
    async def get_system_manuals():
        """
        Fetch manual content from local JSON, Firestore, and Markdown files.
        """
        context_parts = []
        try:
            # 1. Try Firestore 'articles' (Topic: Guides)
            if db:
                articles_ref = db.collection('articles').where('topic', '==', 'guide').limit(3).stream()
                for doc in articles_ref:
                    data = doc.to_dict()
                    if 'content' in data:
                        context_parts.append(f"Guide: {data.get('title', 'Untitled')}\n{data['content']}")

            # 2. Recursive Markdown File Search in 'data' directory
            import os
            data_dir = 'data'
            if os.path.exists(data_dir):
                for root, dirs, files in os.walk(data_dir):
                    for file in files:
                        if file.endswith(".md"):
                            file_path = os.path.join(root, file)
                            try:
                                with open(file_path, 'r', encoding='utf-8') as f:
                                    content = f.read()
                                    context_parts.append(f"Guide ({file}):\n{content}")
                            except Exception as read_err:
                                logging.warning(f"Failed to read manual {file}: {read_err}")

            # 3. Legacy JSON Fallback (if needed)
            if not context_parts:
                try:
                    with open('data/system_manuals.json', 'r', encoding='utf-8') as f:
                        manuals = json.load(f)
                        for m in manuals:
                            context_parts.append(f"System: {m['system']}\nInstruction: {m['content']}")
                except FileNotFoundError:
                    pass

            return "\n\n".join(context_parts)
        except Exception as e:
            logging.error(f"Error fetching manuals: {e}")
            return ""

    @staticmethod
    async def get_user_context(telegram_id):
        """
        Fetch user metadata (role, courtName, department) for personalized AI responses.
        """
        if not telegram_id:
            return ""
        
        try:
            from services.firestore_service import FirestoreService
            user = await FirestoreService.get_user(telegram_id)
            
            if not user:
                return ""
            
            role = user.get('role', 'foydalanuvchi')
            court_name = user.get('courtName', 'noma\'lum')
            department = user.get('department', '')
            first_name = user.get('firstName', '')
            
            context = f"""
--- FOYDALANUVCHI KONTEKSTI ---
Ism: {first_name}
Lavozim: {role}
Sud: {court_name}
Bo'lim: {department}
-----------------------------------
"""
            return context
        except Exception as e:
            logging.error(f"Error fetching user context: {e}")
            return ""

    @staticmethod
    async def generate_solution(user_query, telegram_id=None):
        """
        Generates a technical solution using Gemini 3 Flash Preview.
        Context: IT Support for Court Systems (E-SUD, E-XAT).
        Includes user context for personalized responses.
        """
        try:
            # Initialize model with specific system instruction
            # switch to gemini-3-flash-preview as requested/available
            model = genai.GenerativeModel(
                model_name="gemini-3-flash-preview", 
                system_instruction=SYSTEM_INSTRUCTION
            )
            
            # Fetch knowledge base
            manuals_context = await AIService.get_system_manuals()
            
            # Fetch user-specific context
            user_context = await AIService.get_user_context(telegram_id)
            
            full_prompt = (
                f"{user_context}\n"
                f"--- DRIVERS & MANUALS (CONTEXT) ---\n{manuals_context}\n"
                f"-----------------------------------\n\n"
                f"USER PROBLEM: {user_query}\n"
                f"YOUR SOLUTION:"
            )
            
            # Use async generation if available, otherwise sync
            response = await model.generate_content_async(full_prompt)
            return response.text
        except Exception as e:
            import traceback
            logging.error(f"AI Generation Error: {e}")
            logging.error(traceback.format_exc())
            return f"Texnik xatolik yuz berdi. (Model: gemini-3-flash-preview) Error: {str(e)}"
