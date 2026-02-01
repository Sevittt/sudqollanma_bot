name: managing-flutter-clean-architecture
description: Flutter loyihalarini Clean Architecture (Feature-First) va Glassmorphism dizayn standartlari asosida boshqaradi.

# Flutter Clean Architecture Expert Skill

## When to use this skill
- Har qanday yangi funksiya (feature) qo'shilganda.
- UI dizaynini o'zgartirish yoki refactoring qilish kerak bo'lganda.
- Kod sifatini tekshirish (code review) zarur bo'lganda.

## Logic Framework (The Workflow)
1. **Presentation Layer:** Faqat `screens`, `widgets` va `providers` bo'lishi shart.
2. **Domain Layer:** Faqat `entities`, `repositories` (interface) va `usecases`. Hech qanday tashqi kutubxona (Firebase/API) bo'lmasligi kerak.
3. **Data Layer:** `models`, `repositories` (implementation) va `datasources`.

## Rules
- **Naming:** Fayl nomlari kichik harflarda va pastki chiziq (_) bilan yozilsin.
- **Glassmorphism:** Har bir yangi Card uchun `GlassCard` widgetidan foydalanilsin.
- **Atomic Updates:** Firestore ma'lumotlarini yangilashda har doim `FieldValue.increment()` ishlatilsin.