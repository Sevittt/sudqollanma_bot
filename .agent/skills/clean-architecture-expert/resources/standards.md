# Detailed Project Standards: Sud Qo'llanma

## 🌐 Localization Standard
- UI strings MUST NOT be hardcoded. Use `AppLocalizations.of(context)!.[key]`.
- All keys must be present in `lib/l10n/app_uz.arb`.

## 🛡️ Error Handling (Senior Level)
- NEVER use empty `catch(e) {}`.
- Always show a `SnackBar` or `Dialog` to the user in Uzbek if an error occurs.
- Log errors using `LoggerService` for debugging.

## 🤖 AI Mentor Tone (Digital Competence)
- When generating content or AI responses, act as a supportive IT specialist.
- Focus on "How-to" steps for: E-SUD, E-XAT, E-IMZO, and Cybersecurity.
- Tone: Professional, clear, and encouraging.

## 📱 Bot-App Sync Logic
- Every Firestore update to a user's XP must include a `last_updated_by` field (either 'mobile_app' or 'telegram_bot').
- Use `phoneNumber` as the primary key for syncing.