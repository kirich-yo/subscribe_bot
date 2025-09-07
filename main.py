import asyncio
import logging
import sys
import os
import time
import signal
from collections import namedtuple

import redis

from aiogram import Bot, Dispatcher, Router, html, F
from aiogram.client.default import DefaultBotProperties
from aiogram.utils.formatting import Text, TextLink, Bold
from aiogram.types.inline_keyboard_markup import InlineKeyboardMarkup
from aiogram.types.inline_keyboard_button import InlineKeyboardButton
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart, Command, CommandObject
from aiogram.types import Message, ChatMemberUpdated
from aiogram.enums import ChatMemberStatus
from aiogram.methods import GetChatMember

from middleware import GroupMiddleware


AutoDeletingMessage = namedtuple('AutoDeletingMessage', ['message', 'deadline'])

to_monitor = redis.Redis(host='redis', port=6379, db=0)
message_queue = []

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


@dp.message(CommandStart())
async def command_start_handler(message: Message) -> None:
    await message.answer(f"Привет! Этот бот предназначен для управления чатом и проверки участников чата на предмет подписки на канал. Для того, чтобы бот мог функционировать, пригласите его в чат и назначьте права администратора. Чтобы привязать его к каналу, подписчики которого будут отслеживаться, напишите команду {html.code('/bind https://t.me/ссылка_на_канал')}. Аналогично, чтобы отвязать чат от канала, напишите команду {html.code('/unbind')}. Не забудьте также добавить бота в канал и назначить права администратора.")


@group_only.message(Command('bind')) 
async def bind_command_handler(message: Message, command: CommandObject) -> None:
    if not command.args:
        await message.answer(html.bold('⚠️ Укажите ссылку на канал, который вы хотите привязать к чату!'))
        return

    tg_channel = command.args.split(' ')[0]
    to_monitor.set(message.chat.id, tg_channel.replace('https://t.me/', '@'))

    answer = await message.answer(html.bold('✅ Канал успешно привязан!'))
    await message.delete()
    add_message_to_queue(answer)


@group_only.message(Command('unbind')) 
async def unbind_command_handler(message: Message, command: CommandObject) -> None:
    to_monitor.delete(message.chat.id)

    answer = await message.answer(html.bold('✅ Канал успешно отвязан!'))
    await message.delete()
    add_message_to_queue(answer)


@dp.my_chat_member(F.chat.type != 'channel')
async def chat_member_handler(chat_member: ChatMemberUpdated) -> None:
    await chat_member.answer(f"Отлично! Теперь назначьте боту права администратора, чтобы он мог иметь доступ к сообщениям и управлять чатом.")


@dp.message(~F.chat.type.in_({'private', 'channel'}) & ~F.text.startswith('/'))
async def message_handler(message: Message) -> None:
    user = message.from_user
    tg_channel = to_monitor.get(message.chat.id)
    if not tg_channel:
        return
    tg_channel = tg_channel.decode()

    bad_statuses = [
            ChatMemberStatus.RESTRICTED,
            ChatMemberStatus.LEFT,
            ChatMemberStatus.KICKED
    ]

    subscriber = await bot.get_chat_member(tg_channel, user.id)
    if subscriber.status in bad_statuses:
        content = Text(
                TextLink(user.full_name, url=f"tg://user?id={user.id}"), ", ",
                Bold("вам необходимо подписаться на канал, чтобы писать сообщения:")
        )

        buttons = [[InlineKeyboardButton(text='✅ Подписаться ✅', url=tg_channel.replace('@', 'https://t.me/'))]]
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
                clean_messages()
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
