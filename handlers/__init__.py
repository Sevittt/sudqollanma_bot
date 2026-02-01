from aiogram import Router
from .onboarding import router as onboarding_router
from .quizzes import router as quizzes_router
from .helpdesk import router as helpdesk_router

router = Router()

# Order matters: onboarding (commands/contact) -> quizzes (commands) -> helpdesk (text fallthrough)
router.include_router(onboarding_router)
router.include_router(quizzes_router)
router.include_router(helpdesk_router)
