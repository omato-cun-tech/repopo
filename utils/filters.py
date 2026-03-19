from aiogram.filters import Filter
from aiogram.types import Message, CallbackQuery
from core.config import settings

class IsAdminFilter(Filter):
    async def __call__(self, event: Message | CallbackQuery) -> bool:
        user_id = event.from_user.id
        return user_id in settings.admin_ids
