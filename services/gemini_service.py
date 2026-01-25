import google.generativeai as genai
import config
from loader import db, model
import logging

class GeminiService:
    @staticmethod
    async def get_relevant_context(query):
        """
        Simple RAG: Search Firestore for documents containing keywords from the query.
        In a production app, use Vector Search (Pinecone/Weaviate).
        Here we just fetch recent news or specific 'laws' collection if it existed.
        For now, let's assume we have a 'knowledge_base' collection.
        """
        if not db: return ""
        
        context_parts = []
        try:
            # Very basic keyword match simulation. 
            # In Firestore, we can't easily do full text search without extensions.
            # So we will just fetch a few documents or return general instructions.
            # TODO: Integrate valid Vector Search or Algolia.
            
            # Placeholder: fetching system prompts or static rules from DB
            knowledge_ref = db.collection('knowledge_base').limit(3).stream()
            for doc in knowledge_ref:
                data = doc.to_dict()
                if 'content' in data:
                    context_parts.append(data['content'])
            
            return "\n\n".join(context_parts)
        except Exception as e:
            logging.error(f"Error fetching context: {e}")
            return ""

    @staticmethod
    async def generate_response(query):
        if not model:
            return "AI xizmati vaqtincha ishlamayapti."

        try:
            context = await GeminiService.get_relevant_context(query)
            
            system_instruction = (
                "Siz O'zbekiston sud tizimi xodimlari va foydalanuvchilari uchun yuridik yordamchisiz. "
                "Faqat yuridik, sud va qonunchilikka oid savollarga javob bering. "
                "Javobingiz aniq, lo'nda va yuridik asoslangan bo'lsin. "
                "Agar savol yuridik bo'lmasa, 'Men faqat yuridik savollarga javob bera olaman' deb ayting."
            )
            
            if context:
                full_prompt = (
                    f"{system_instruction}\n\n"
                    f"Qo'shimcha ma'lumotlar (Kontekst):\n{context}\n\n"
                    f"Foydalanuvchi savoli: {query}"
                )
            else:
                full_prompt = f"{system_instruction}\n\nFoydalanuvchi savoli: {query}"
            
            response = model.generate_content(full_prompt)
            return response.text
        except Exception as e:
            logging.error(f"Gemini generation error: {e}")
            return f"Kechirasiz, xatolik yuz berdi (AI Error): {str(e)}"
