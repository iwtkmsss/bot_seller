from aiogram.filters import Filter
from aiogram.types import Message

from misc import BDB

class UserAdmin(Filter):
    async def __call__(self, message: Message) -> bool:
        for i in BDB.get_users_by_job_title("admin"):
            if message.from_user.id == i['telegram_id']:
                return True
        return False
