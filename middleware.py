from typing import Callable, Dict, Any, Awaitable

from aiogram import BaseMiddleware, html
from aiogram.types import Message, ChatMember
from aiogram.enums import ChatMemberStatus

ADMINISTRATIVE_STATUSES = [
        ChatMemberStatus.CREATOR,
        ChatMemberStatus.ADMINISTRATOR
]

class ChatManagementMiddleware(BaseMiddleware):
    def __init__(self) -> None:
        pass

    async def __call__(
        self,
        handler: Callable[[Message, Dict[str, Any]], Awaitable[Any]],
        event: Message,
        data: Dict[str, Any]
    ) -> Any:
        if event.chat.type == 'private':
            await event.answer(html.bold('⚠️ Данная команда не может использоваться в личных сообщениях!'))
            return

        sender: ChatMember = await event.chat.get_member(event.from_user.id)
        if sender.status not in ADMINISTRATIVE_STATUSES:
            await event.answer(html.bold('⚠️ Данная команда может использоваться только администраторами чата!'))
            return

        return await handler(event, data)
