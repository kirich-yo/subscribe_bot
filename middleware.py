from typing import Callable, Dict, Any, Awaitable

from aiogram import BaseMiddleware, html
from aiogram.types import Message

class GroupMiddleware(BaseMiddleware):
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

        return await handler(event, data)
