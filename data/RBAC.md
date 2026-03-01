1. Rollar Logikasi va UI/UX Taqsimoti
Tizimga kirganda (Botda ham, App'da ham) foydalanuvchiga uning lavozimidan kelib chiqib faqat unga kerakli asboblar ko'rsatiladi.

💼 1. Devonxona mudiri (Har qanday sudning "Yuragi")
Asosiy muammosi: Kunlik yuzlab xatlarni ro'yxatga olish, sudtyalarga taqsimlash, E-XAT va E-SUD integratsiyasi xatolari, pochta jo'natmalari.

App/Botdagi UI va AI Logikasi:

Tezkor menyu: "Kirim qilish", "Hujjat taqsimlash", "E-XAT nosozliklari", "Fuqarolar qabuli".

AI yondashuvi: Devonxona xodimi savol bersa, AI javobni avtomatik ravishda Kanselyariya yo'riqnomalaridan (sizdagi 3, 4, 5, 24-yo'riqnomalar va "Sudda ish yuritish" kitobining 1-bobi) qidiradi.

⚖️ 2. Sudya
Asosiy muammosi: Ishlarni o'z vaqtida ko'rish, VKA (videokonferensiya) orqali sud o'tkazish, elektron imzo (ERI) bilan qarorlarni tasdiqlash, ijro hujjatlarini yuborish.

App/Botdagi UI va AI Logikasi:

Tezkor menyu: "VKA sozlamalari", "Hujjat imzolash", "Ishni boshqa sudyaga o'tkazish", "Protestlar".

AI yondashuvi: AI ularga faqat qisqa, aniq va texnik/huquqiy yechimlarni beradi. "Qanday imzolayman?" desa, ortiqcha gaplarsiz 9-yo'riqnomani (Imzolash) ko'rsatadi.

📝 3. Sudya yordamchisi
Asosiy muammosi: Sud jarayonini tizimga kiritish, taraflarga SMS xabar yuborish, ishni birlashtirish/ajratish, ijroga qaratish.

App/Botdagi UI va AI Logikasi:

Tezkor menyu: "SMS yuborish", "Ijro varaqasi xatolari", "Ishlarni birlashtirish", "Muddatni uzaytirish".

AI yondashuvi: Yordamchilar tizimda eng ko'p ishlaydigan xodimlar. AI ularga bosqichma-bosqich (Step-by-step) qo'llanmalarni skrinshotlari bilan chiqarib beradi.

🗄 4. Arxiv mudiri
Asosiy muammosi: Tugatilgan ishlarni E-SUD dan arxivga qabul qilish, yo'q qilish muddatlari, davlat boji undirib nusxa berish.

App/Botdagi UI va AI Logikasi:

Tezkor menyu: "Arxivga qabul qilish", "Nusxa berish tartibi", "Davlat boji", "Eski ishlarni qidirish".

AI yondashuvi: Asosan "Sudda ish yuritish" kitobining III.7-bandiga (Sud arxivi ishlari) va qonunchilikka asoslanib javob beradi.

💻 5. AKT xodimi (IT Specialist)
Asosiy muammosi: Tizimga yangi xodim qo'shish, rollarni (huquqlarni) sozlash, tarmoq xatolari, elektron kalit (ERI) muddati tugashi.

App/Botdagi UI va AI Logikasi:

Tezkor menyu: "Foydalanuvchi yaratish (16-yo'riqnoma)", "Parol tiklash", "Texnik qo'llab-quvvatlash".

AI yondashuvi: IT atamalari bilan javob beradi. Tizimdagi admin panel huquqlari qanday berilishini tushuntiradi.

2. Dasturlashga Tatbiq etish (Texnik Arxitektura)
Ushbu logikani ishga tushirish uchun biz ma'lumotlar bazasi va AI promptlarini biroz o'zgartirishimiz kerak bo'ladi.

1-Qadam: Firestore users kolleksiyasini yangilash
Foydalanuvchi modeliga (Flutter'dagi AppUser yoki botdagi foydalanuvchi modeliga) role maydonini qo'shamiz.

// Flutter - lib/features/auth/domain/entities/app_user.dart
enum CourtRole {
  judge,          // Sudya
  assistant,      // Yordamchi
  chancellery,    // Devonxona
  archive,        // Arxiv
  ict_specialist, // AKT xodimi
  unknown
}

class AppUser {
  final String uid;
  final String name;
  final CourtRole role; // Yangi qo'shildi
  // ...
}

2-Qadam: AI ga Rolni tushuntirish (Eng muhim qism - Context injection)
AI (Gemini) ga savol yuborayotganda, biz endi "bu qanday odam ekanligini" yashirincha qo'shib yuboramiz. Bu orqali Gemini javobni o'sha xodimning tilida va unga tegishli yo'riqnomalardan izlab beradi.

Bot (Python) da ai_service.py o'zgarishi:

Python
async def get_smart_answer_for_bot(user_question: str, user_role: str) -> str:
    # Vektor qidiruv kodi...
    
    prompt = f"""
    Siz O'zbekiston Sud tizimi xodimlari uchun yordamchi AIsiz.
    Siz bilan suhbatlashayotgan xodimning lavozimi: {user_role}.
    
    Ma'lumotlar bazasidan topilgan yo'riqnomalar:
    {full_context}
    
    Foydalanuvchining lavozimidan kelib chiqib, yuqoridagi ma'lumotlar asosida 
    aniq, amaliy va faqat uning vakolatiga kiradigan qismlarni tushuntirib javob bering.
    
    Savol: {user_question}
    """
    
    response = generative_model.generate_content(prompt)
    return response.text

Flutter'da Har Bir Rol Uchun "Gamification" va Testlar
Sizda quizzes.py va Flutter appda test ishlash bor. Har bir xodim o'z yo'nalishi bo'yicha test ishlasa zo'r bo'ladi:

Devonxona mudiri uchun: "Kiruvchi xat necha kunda ro'yxatga olinishi kerak?"

Yordamchi uchun: "Ijro varaqasi qaysi menyudan yuboriladi?"
Firestore'dagi testlar (quizzes) kolleksiyasiga target_role (masalan, ['assistant', 'judge']) degan tag qo'shamiz. Xodim faqat o'ziga tegishli testlarni yechib, "XP" (ball) yig'adi.

