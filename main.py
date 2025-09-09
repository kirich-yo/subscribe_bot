import asyncio
import logging
import sys
import os
import time
import signal
from collections import namedtuple
from typing import Optional

import redis

from aiogram import Bot, Dispatcher, Router, html, F
from aiogram.client.default import DefaultBotProperties
from aiogram.utils.formatting import Text, TextLink, Bold, Code
from aiogram.types.inline_keyboard_markup import InlineKeyboardMarkup
from aiogram.types.inline_keyboard_button import InlineKeyboardButton
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart, Command, CommandObject
from aiogram.types import Message, ChatMemberUpdated
from aiogram.enums import ChatMemberStatus
from aiogram.methods import GetChatMember

from middleware import GroupMiddleware


BAD_STATUSES = [
        ChatMemberStatus.RESTRICTED,
        ChatMemberStatus.LEFT,
        ChatMemberStatus.KICKED
]

AutoDeletingMessage = namedtuple('AutoDeletingMessage', ['message', 'deadline'])
FutureSubscriber = namedtuple('FutureSubscriber', ['user', 'chat', 'channel_id'])

to_monitor = redis.Redis(host='localhost', port=6379, db=0)
message_queue: list[AutoDeletingMessage] = []
future_subscribers: list[FutureSubscriber] = []

bot = Bot(token=os.environ['BOT_TOKEN'], default=DefaultBotProperties(parse_mode=ParseMode.HTML))

dp = Dispatcher()
group_only = Router()
group_only.message.middleware(GroupMiddleware())
dp.include_router(group_only)


def graceful_shutdown_handler(signum, frame):
    loop = asyncio.get_event_loop()
    loop.stop()


signal.signal(signal.SIGINT, graceful_shutdown_handler)
signal.signal(signal.SIGTERM, graceful_shutdown_handler)


def get_tg_channel(chat_id: int) -> Optional[str]:
    tg_channel = to_monitor.get(f"{chat_id}:channel")
    return tg_channel.decode() if tg_channel else None


def set_tg_channel(chat_id: int, tg_channel: str) -> None:
    to_monitor.set(f"{chat_id}:channel", tg_channel.replace('https://t.me/', '@'))


def delete_tg_channel(chat_id: int) -> None:
    to_monitor.delete(f"{chat_id}:channel")


def get_welcome_message(chat_id: int) -> Optional[str]:
    welcome_message = to_monitor.get(f"{chat_id}:welcome")
    return welcome_message.decode() if welcome_message else None


def set_welcome_message(chat_id: int, welcome_message: str) -> None:
    to_monitor.set(f"{chat_id}:welcome", welcome_message)


def delete_welcome_message(chat_id: int) -> None:
    to_monitor.delete(f"{chat_id}:welcome")


def mention_to_url(mention: str) -> str:
    return mention.replace('@', 'https://t.me/')


def add_message_to_queue(message: Message) -> None:
    deadline = time.time() + int(os.environ['MESSAGE_TIMEOUT'])
    message_queue.append(AutoDeletingMessage(message=message, deadline=deadline))


async def clean_messages() -> None:
    while True:
        await asyncio.sleep(0)
        for msg in message_queue:
            if msg.deadline < time.time():
                await msg.message.delete()
                message_queue.remove(msg)


async def monitor_future_subscribers() -> None:
    while True:
        await asyncio.sleep(0)
        for sub in future_subscribers:
            new_sub = await bot.get_chat_member(sub.channel_id, sub.user.id)
            if new_sub.status not in BAD_STATUSES:
                welcome_message = get_welcome_message(sub.chat.id)
                content = Text(
                    TextLink(sub.user.full_name, url=f"tg://user?id={sub.user.id}"), ",\n\n",
                    welcome_message
                )

                answer = await bot.send_message(sub.chat.id, **content.as_kwargs())
                add_message_to_queue(answer)
                future_subscribers.remove(sub)


@dp.message(CommandStart())
async def command_start_handler(message: Message) -> None:
    await message.answer(f"Привет! Этот бот предназначен для управления чатом и проверки участников чата на предмет подписки на канал. Для того, чтобы бот мог функционировать, пригласите его в чат и назначьте права администратора. Чтобы привязать его к каналу, подписчики которого будут отслеживаться, напишите команду {html.code('/bind https://t.me/ссылка_на_канал')}. Аналогично, чтобы отвязать чат от канала, напишите команду {html.code('/unbind')}. Не забудьте также добавить бота в канал и назначить права администратора.")


@group_only.message(Command('bind')) 
async def bind_command_handler(message: Message, command: CommandObject) -> None:
    if not command.args:
        answer = await message.answer(html.bold('⚠️ Укажите ссылку на канал, который вы хотите привязать к чату!'))
        await message.delete()
        add_message_to_queue(answer)
        return

    tg_channel = command.args.split(' ')[0]
    set_tg_channel(message.chat.id, tg_channel)

    answer = await message.answer(html.bold('✅ Канал успешно привязан!'))
    await message.delete()
    add_message_to_queue(answer)


@group_only.message(Command('unbind')) 
async def unbind_command_handler(message: Message, command: CommandObject) -> None:
    delete_tg_channel(message.chat.id)

    answer = await message.answer(html.bold('✅ Канал успешно отвязан!'))
    await message.delete()
    add_message_to_queue(answer)


@group_only.message(Command('show_bound_channel')) 
async def show_bound_channel_command_handler(message: Message, command: CommandObject) -> None:
    tg_channel = get_tg_channel(message.chat.id)
    answer = None

    if not tg_channel:
        answer = await message.answer(html.bold('ℹ️ К вашему чату не привязан канал!'))
    else:
        tg_channel_info = await bot.get_chat(tg_channel) 
        content = Text(
                Bold('ℹ️ К вашему чату привязан канал: '), Code(tg_channel_info.title)
        )
        buttons = [[InlineKeyboardButton(text='▶️ Открыть канал', url=mention_to_url(tg_channel))]]
        keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
        answer = await message.answer(**content.as_kwargs(), reply_markup=keyboard)

    await message.delete()
    add_message_to_queue(answer)


@group_only.message(Command('set_welcome')) 
async def set_welcome_command_handler(message: Message, command: CommandObject) -> None:
    if not command.args:
        answer = await message.answer(html.bold('⚠️ Укажите текст, который вы хотите установить в качестве приветствия для новых подписчиков канала!'))
        await message.delete()
        add_message_to_queue(answer)
        return

    set_welcome_message(message.chat.id, command.args)

    answer = await message.answer(html.bold('✅ Приветственное сообщение успешно установлено!'))
    await message.delete()
    add_message_to_queue(answer)


@group_only.message(Command('clear_welcome')) 
async def clear_welcome_command_handler(message: Message, command: CommandObject) -> None:
    delete_welcome_message(message.chat.id)

    answer = await message.answer(html.bold('✅ Приветственное сообщение успешно очищено!'))
    await message.delete()
    add_message_to_queue(answer)


@group_only.message(Command('show_welcome')) 
async def show_welcome_command_handler(message: Message, command: CommandObject) -> None:
    welcome_message = get_welcome_message(message.chat.id)
    answer = None

    if not welcome_message:
        answer = await message.answer(html.bold('ℹ️ В вашем чате не установлено приветственное сообщение!'))
    else:
        content = Text(
                Bold('ℹ️ В вашем чате установлено приветственное сообщение: '), '\n\n',
                welcome_message
        )
        answer = await message.answer(**content.as_kwargs())

    await message.delete()
    add_message_to_queue(answer)


@dp.my_chat_member(F.chat.type != 'channel')
async def chat_member_handler(chat_member: ChatMemberUpdated) -> None:
    status = chat_member.new_chat_member.status
    if status == ChatMemberStatus.MEMBER:
        await chat_member.answer(f"Отлично! Теперь назначьте боту права администратора, чтобы он мог иметь доступ к сообщениям и управлять чатом.")


@dp.chat_member(F.chat.type != 'channel')
async def join_handler(chat_member: ChatMemberUpdated) -> None:
    user = chat_member.new_chat_member.user
    welcome_message = get_welcome_message(chat_member.chat.id)
    if not welcome_message:
        return

    content = Text(
            TextLink(user.full_name, url=f"tg://user?id={user.id}"), ",\n\n",
            welcome_message
    )

    status = chat_member.new_chat_member.status
    if status == ChatMemberStatus.MEMBER:
        tg_channel = get_tg_channel(chat_member.chat.id)
        if not tg_channel:
            answer = await chat_member.answer(**content.as_kwargs())
            add_message_to_queue(answer)
            return

        subscriber = await bot.get_chat_member(tg_channel, user.id)
        if (subscriber.status in BAD_STATUSES) and (subscriber not in future_subscribers):
            future_subscribers.append(
                    FutureSubscriber(
                        user=user,
                        chat=chat_member.chat,
                        channel_id=tg_channel
                    )
            )


@dp.message(~F.chat.type.in_({'private', 'channel'}) & ~F.text.startswith('/'))
async def message_handler(message: Message) -> None:
    user = message.from_user
    tg_channel = get_tg_channel(message.chat.id)
    if not tg_channel:
        return

    subscriber = await bot.get_chat_member(tg_channel, user.id)
    if subscriber.status in BAD_STATUSES:
        content = Text(
                TextLink(user.full_name, url=f"tg://user?id={user.id}"), ", ",
                Bold("вам необходимо подписаться на канал, чтобы писать сообщения:")
        )

        buttons = [[InlineKeyboardButton(text='✅ Подписаться ✅', url=mention_to_url(tg_channel))]]
        keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)

        answer = await message.answer(**content.as_kwargs(), reply_markup=keyboard)
        await message.delete()
        add_message_to_queue(answer)


async def run_bot() -> None:
    await dp.start_polling(bot, handle_signals=False)


async def main() -> None:
    try:
        await asyncio.gather(
                run_bot(),
                clean_messages(),
                monitor_future_subscribers()
        )
    except asyncio.exceptions.CancelledError:
        pass


if __name__ == '__main__':
    logging.basicConfig(
            filename=os.path.join(os.environ['LOG_FILE_PATH'], time.strftime("subscribe_bot_%Y%m%d%H%M%S.log")),
            format='%(asctime)s.%(msecs)03d %(name)s %(levelname)s %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S',
            level=logging.INFO,
    )
    logging.getLogger().addHandler(logging.StreamHandler(sys.stdout))
    asyncio.run(main())
