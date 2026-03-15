import time
import logging
from typing import Any, Awaitable, Callable, Dict
from aiogram import BaseMiddleware
from aiogram.types import Message, TelegramObject

class ThrottlingMiddleware(BaseMiddleware):
    """
    Anti-spam middleware: limits messages to 1 per second per user.
    Prevents bot overload from rapid message sending.
    """
    
    def __init__(self, rate_limit: float = 1.0):
        self.rate_limit = rate_limit  # seconds between messages
        self.user_last_message: Dict[int, float] = {}
        super().__init__()
    
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        if not isinstance(event, Message):
            return await handler(event, data)
        
        user_id = event.from_user.id
        current_time = time.time()
        last_time = self.user_last_message.get(user_id, 0)
        
        if current_time - last_time < self.rate_limit:
            # User is sending too fast — silently ignore
            logging.debug(f"Throttled user {user_id}")
            return
        
        self.user_last_message[user_id] = current_time
        return await handler(event, data)


class ErrorHandlerMiddleware(BaseMiddleware):
    """
    Global error handler middleware.
    Catches unhandled exceptions and sends a user-friendly Uzbek message.
    """
    
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        try:
            return await handler(event, data)
        except Exception as e:
            logging.error(f"Unhandled error in handler: {e}", exc_info=True)
            
            if isinstance(event, Message):
                try:
                    await event.answer(
                        "⚠️ <b>Kutilmagan xatolik yuz berdi.</b>\n\n"
                        "Tizim jamoasi bu haqda xabardor qilindi.\n"
                        "Iltimos, biroz kutib qayta urinib ko'ring.\n\n"
                        "Muammo davom etsa, /start buyrug'ini bosing."
                    )
                except Exception:
                    pass  # If even the error reply fails, just log it
