import asyncio
import aiosqlite
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from config import BOT_TOKEN, ADMINS

bot = Bot(token=BOT_TOKEN, parse_mode="HTML")
dp = Dispatcher()

DB = "db.sqlite3"
user_targets = {}
reply_wait = {}


# ───────── БАЗА ─────────
async def init_db():
    async with aiosqlite.connect(DB) as db:
        await db.execute("""
        CREATE TABLE IF NOT EXISTS questions(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        sender_id INTEGER,
        receiver_id INTEGER
        )
        """)
        await db.commit()


# ───────── КНОПКИ ─────────
def cancel_btn():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")]
        ]
    )


def again_btn():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✍️ Написать ещё", callback_data="again")]
        ]
    )


def reply_btn(sender_id):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text="✍️ Ответить",
                callback_data=f"replyto_{sender_id}"
            )]
        ]
    )


def share_btn(link):
    share = f"https://t.me/share/url?url=По этой ссылке можно прислать мне анонимное сообщение:%0A👉 {link}"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📤 Поделиться ссылкой", url=share)]
        ]
    )


# ───────── ЛОГ АДМИНАМ ─────────
async def send_admin_log(message, target_id):

    sender = message.from_user
    sender_id = sender.id

    text = message.text or message.caption or "медиа"

    log = (
        f"📨 Новое сообщение\n\n"
        f"👤 Отправитель: {sender.first_name} (@{sender.username or 'нет'})\n"
        f"ID: {sender_id}\n\n"
        f"🎯 Получатель ID: {target_id}\n\n"
        f"💬 {text}"
    )

    for admin in ADMINS:
        try:
            await bot.send_message(admin, log)
            await message.copy_to(admin)
        except:
            pass


# ───────── START ─────────
@dp.message(CommandStart())
async def start(message: types.Message, command: CommandStart):

    user_id = message.from_user.id
    bot_username = (await bot.get_me()).username
    link = f"https://t.me/{bot_username}?start={user_id}"

    if command.args:
        target = int(command.args)

        if target == user_id:
            return

        user_targets[user_id] = target

        await message.answer(
            "🚀 Напишите анонимное сообщение\n\n"
            "Можно отправлять текст и медиа",
            reply_markup=cancel_btn()
        )
        return

    await message.answer(
        f"Начните получать анонимные вопросы прямо сейчас!\n\n👉 {link}",
        reply_markup=share_btn(link)
    )


# ───────── ОТПРАВКА СООБЩЕНИЯ ─────────
@dp.message()
async def send_question(message: types.Message):

    sender_id = message.from_user.id

    if sender_id not in user_targets:
        return

    target = user_targets[sender_id]

    # защита от chat not found
    try:
        await message.copy_to(target)
    except:
        await message.answer(
            "❌ Сообщение не доставлено.\n\n"
            "Пользователь не активировал бота."
        )
        return

    # сообщение А
    await bot.send_message(
        target,
        "💬 У тебя новое сообщение!",
        reply_markup=reply_btn(sender_id)
    )

    async with aiosqlite.connect(DB) as db:
        await db.execute(
            "INSERT INTO questions(sender_id,receiver_id) VALUES(?,?)",
            (sender_id, target)
        )
        await db.commit()

    await send_admin_log(message, target)

    await message.answer(
        "✅ Сообщение отправлено, ожидайте ответ!",
        reply_markup=again_btn()
    )


# ───────── КНОПКА ОТВЕТИТЬ ─────────
@dp.callback_query(F.data.startswith("replyto_"))
async def start_reply(call: types.CallbackQuery):

    sender_id = int(call.data.split("_")[1])
    reply_wait[call.from_user.id] = sender_id

    await call.message.answer("✍️ Напишите ответ")


# ───────── ОТПРАВКА ОТВЕТА ─────────
@dp.message(F.text)
async def send_reply(message: types.Message):

    user_id = message.from_user.id

    if user_id not in reply_wait:
        return

    sender_id = reply_wait[user_id]

    try:
        await bot.send_message(
            sender_id,
            f"💬 Ответ:\n\n{message.text}",
            reply_markup=again_btn()
        )

        await message.answer("✅ Ответ успешно отправлен")

    except:
        await message.answer(
            "❌ Ответ не доставлен.\n\n"
            "Пользователь заблокировал бота или удалил чат."
        )

    del reply_wait[user_id]


# ───────── ДРУГИЕ КНОПКИ ─────────
@dp.callback_query(F.data == "again")
async def again(call: types.CallbackQuery):
    await call.message.answer("✍️ Напишите сообщение")


@dp.callback_query(F.data == "cancel")
async def cancel(call: types.CallbackQuery):

    bot_username = (await bot.get_me()).username
    link = f"https://t.me/{bot_username}?start={call.from_user.id}"

    await call.message.answer(
        f"Начните получать анонимные вопросы прямо сейчас!\n\n👉 {link}",
        reply_markup=share_btn(link)
    )


# ───────── ЗАПУСК ─────────
async def main():
    await init_db()
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
