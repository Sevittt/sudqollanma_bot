# pyrefly: ignore [missing-import]
from google import genai
import asyncio
import config
from loader import get_db, init_gemini
import logging
import json

SYSTEM_INSTRUCTION = r"""
Sening roling: O'zbekiston sud tizimi xodimlari uchun "Raqamli Mentor". 
Sening bilimlar bazang quyidagi rasmiy qo'llanmalarga asoslangan:
1. E-XSUD: Jinoiy, ma'muriy va fuqarolik ishlarini ro'yxatga olish tartibi.
2. JIB.SUD.UZ va ADOLAT.SUD.UZ: ishlarni "bazaga urish" va natijalarni qayd etish.
3. E-IMZO: Hujjatlarni imzolashdagi texnik muammolar (C:\E-IMZO drayveri).
4. Sud iyerarxiyasi: Tuman, shahar, viloyat va Oliy sud xodimlarining vazifalari.

Qoidalar:
- Faqat sud tizimiga oid IT va texnik savollarga javob ber. Agar savol sud muhitiga yoki xodimlarning kundalik amaliy tajribasiga xos bo'lsa (baza va qo'llanmadan tashqarida ham), IT mutaxassisi sifatida o'zingning umumiy mantiqiy bilimlaringdan foydalanib yordam ber.
- Agar foydalanuvchi tuman sudi kotibi bo'lsa, unga operatsion (bazaga kiritish) uslubida yordam ber. Oliy suddan bo'lsa tahliliy uslubda.
- Ohanging: Professional, qo'llab-quvvatlovchi va "hormang, charchamang" kabi o'zbekona empatiya elementlari bilan boyitilgan.
- Faqat berilgan matnga cheklanib "men bilmayman" deyishdan qoch! Mumkin qadar vaziyatga mos mantiqiy yechim yo'lini ko'rsat.
"""

# Gemini modelini chaqirishda ushbu instructionni ishlating:
# model = genai.GenerativeModel(model_name="gemini-3.0-flash", system_instruction=SYSTEM_INSTRUCTION)

class AIService:
    @staticmethod
    async def get_system_manuals():
        """Test savoli uchun zaxira kontekst: knowledge_base'dan bir nechta maqola.

        Avval data/*.md fayllar (jumladan 1.4 MB knowledge.md) ham butunlay
        promptga qo'shilardi — bu olib tashlandi.
        """
        context_parts = []
        try:
            if get_db():
                kb_ref = get_db().collection('knowledge_base').limit(config.KB_FALLBACK_LIMIT).stream()
                for doc in kb_ref:
                    data = doc.to_dict()
                    content = data.get('content', data.get('text', ''))
                    if content:
                        title = data.get('title', 'Maqola')
                        context_parts.append(f"Qo'llanma: {title}\n{content[:3000]}")
            return "\n\n".join(context_parts)
        except Exception as e:
            logging.error(f"Error fetching manuals: {e}")
            return ""


    @staticmethod
    async def get_relevant_context(user_query, limit=3):
        """Savolga mos bo'laklarni rag_chunks_v2 vektor qidiruvidan oladi.

        Mos bo'lak topilmasa bo'sh satr qaytadi — prompt modelga umumiy
        bilimdan foydalanishni aytadi. Tasodifiy maqolalar qo'shilmaydi.
        """
        try:
            from services.rag_search import format_context, search
            hits = await search(user_query, limit=limit)
            return format_context(hits)
        except Exception as e:
            logging.error(f"Vector search xatosi: {e}")
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
            from services.firestore_service import FirestoreService

            # Fetch relevant knowledge base chunks using Vector Search
            manuals_context = await AIService.get_relevant_context(user_query, limit=3)
            
            # Fetch user-specific context
            user_context = await AIService.get_user_context(telegram_id)
            
            # Fetch recent chat history
            history = await FirestoreService.get_recent_messages(telegram_id)
            history_text = ""
            if history:
                history_text = "--- OLDINGI SUHBAT TARIXI ---\n"
                for msg in history:
                    sender = "Foydalanuvchi" if msg['role'] == 'user' else "Mentor (AI)"
                    history_text += f"{sender}: {msg['text']}\n\n"
                history_text += "-----------------------------------\n\n"
            
            full_prompt = (
                f"! DIQQAT: Foydalanuvchi ma'lumotlari !\n"
                f"{user_context}\n"
                f"Yuqoridagi lavozimdan kelib chiqib, aniq, amaliy va faqat uning vakolatiga kiradigan qismlarni tushuntirib javob bering.\n\n"
                f"--- DRIVERS & MANUALS (CONTEXT) ---\n{manuals_context}\n"
                f"-----------------------------------\n\n"
                f"Agar savol CONTEXT ichida to'liq yoritilmagan bo'lsa, sud sohasidagi va IT bo'yicha umumiy bilimlaringga asoslanib to'g'ri va mantiqiy javob qaytar.\n\n"
                f"{history_text}"
                f"USER PROBLEM: {user_query}\n"
                f"YOUR SOLUTION:"
            )
            
            # Save user query to history
            await FirestoreService.save_message(telegram_id, 'user', user_query)

            # Use async generation if available, otherwise sync
            response = await init_gemini().aio.models.generate_content(
                model=config.GEMINI_MODEL,
                contents=full_prompt,
                config=genai.types.GenerateContentConfig(
                    system_instruction=SYSTEM_INSTRUCTION
                )
            )

            # Save model response to history
            await FirestoreService.save_message(telegram_id, 'model', response.text)

            return response.text
        except Exception as e:
            import traceback
            logging.error(f"AI Generation Error: {e}")
            logging.error(traceback.format_exc())
            return f"Texnik xatolik yuz berdi. (Model: {config.GEMINI_MODEL}) Xato: {str(e)}"

    @staticmethod
    async def generate_quiz(telegram_id):
        """
        Generates a dynamic quiz question in JSON format based on the knowledge base.
        """
        try:
            # knowledge_base dan random chunks olish (text emas, content)
            random_docs = get_db().collection("knowledge_base").limit(3).get()
            context_parts = []
            for doc in random_docs:
                data = doc.to_dict()
                content = data.get('content', data.get('text', ''))
                if content:
                    context_parts.append(content[:2000])
            if not context_parts:
                manuals_context = await AIService.get_system_manuals()
            else:
                manuals_context = "\n\n".join(context_parts)
                
            user_context = await AIService.get_user_context(telegram_id)
            
            prompt = (
                f"! DIQQAT: Foydalanuvchi ma'lumotlari !\n"
                f"{user_context}\n"
                f"--- DRIVERS & MANUALS (CONTEXT) ---\n{manuals_context}\n"
                f"-----------------------------------\n\n"
                "Sen shu ma'lumotlar asosida bitta test savoli tuzishing kerak. "
                "DIQQAT: Savol qiyinligi va mavzusi foydalanuvchining yuqoridagi lavozimiga (va unga tegishli vazifalarga) mos bo'lishi shart!\n"
                "Javobni faqatgina quyidagi JSON formatida qaytar, qo'shimcha so'z yozma:\n"
                "{\n"
                '  "question": "Savol matni",\n'
                '  "options": ["A javob", "B javob", "C javob", "D javob"],\n'
                '  "correct_index": 0,\n'
                '  "explanation": "Nima mavzuga oid ekanligi va to\'g\'ri javob izohi"\n'
                "}\n"
                "Diqqat: correct_index 0 dan 3 gacha bo'lgan butun son bo'lishi kerak."
            )
            
            response = await init_gemini().aio.models.generate_content(
                model=config.GEMINI_MODEL,
                contents=prompt,
            )
            text = response.text
            start = text.find('{')
            end = text.rfind('}') + 1
            if start != -1 and end != 0:
                json_str = text[start:end]
                quiz_data = json.loads(json_str)
                return quiz_data
            else:
                return None
        except Exception as e:
            logging.error(f"Quiz Generation Error: {e}")
            return None
