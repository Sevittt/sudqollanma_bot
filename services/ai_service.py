import google.generativeai as genai
import config
from loader import db, model
import logging
import json

class AIService:
    @staticmethod
    async def get_system_manuals():
        """
        Fetch manual content from local JSON or Firestore.
        For MVP, we use a local JSON fallback if Firestore is empty.
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

            # 2. If nothing in DB, check local fallback
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
    async def generate_solution(user_query):
        """
        Generates a technical solution using Gemini 1.5 Flash (or Pro/Flash-Latest).
        Context: IT Support for Court Systems (E-SUD, E-XAT).
        """
        if not model:
            return "⚠️ AI tizimi ishlamayapti (API Key xatosi)."

        try:
            context = await AIService.get_system_manuals()
            
            # System Prompt: IT Support Persona
            system_prompt = (
                "You are an expert IT Support Specialist for the Uzbekistan Court System. "
                "Your goal is to help court employees use digital systems like E-SUD, E-XAT, and Video Conferencing. "
                "You are NOT a lawyer. Do not give legal advice. "
                "If the user asks a technical question, provide a clear, step-by-step solution based on the context. "
                "Tone: Professional, patient, and encouraging. "
                "Language: Uzbek (O'zbek tili). "
                "If you don't know the answer, suggest contacting the official HelpDesk at 1060."
            )
            
            full_prompt = (
                f"{system_prompt}\n\n"
                f"--- DRIVERS & MANUALS (CONTEXT) ---\n{context}\n"
                f"-----------------------------------\n\n"
                f"USER PROBLEM: {user_query}\n"
                f"YOUR SOLUTION:"
            )
            
            response = model.generate_content(full_prompt)
            return response.text
        except Exception as e:
            logging.error(f"AI Generation Error: {e}")
            return "Texnik xatolik yuz berdi. Iltimos, keyinroq urinib ko'ring."
