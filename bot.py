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


# ───────── БАЗА ─────────
async def init_db():
    async with aiosqlite.connect(DB) as db:
        await db.execute("""
        CREATE TABLE IF NOT EXISTS questions(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        sender_id INTEGER,
        receiver_id INTEGER,
        message_id INTEGER
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
async def send_admin_log(message, target_id, text):

    sender = message.from_user
    sender_id = sender.id
    username = sender.username or "нет"
    name = f"{sender.first_name or ''} {sender.last_name or ''}".strip()

    profile = f"tg://user?id={sender_id}"

    target = await bot.get_chat(target_id)

    t_username = target.username or "нет"
    t_name = f"{target.first_name or ''} {target.last_name or ''}".strip()

    log = (
        f"📨 <b>Новое сообщение</b>\n\n"

        f"👤 <b>ОТПРАВИТЕЛЬ</b>\n"
        f"Ник: {name}\n"
        f"Username: @{username}\n"
        f"ID: <code>{sender_id}</code>\n"
        f"<a href='{profile}'>Открыть профиль</a>\n\n"

        f"🎯 <b>ПОЛУЧАТЕЛЬ</b>\n"
        f"Ник: {t_name}\n"
        f"Username: @{t_username}\n"
        f"ID: <code>{target_id}</code>\n\n"

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
            "🚀 Здесь можно отправить анонимное сообщение человеку, который опубликовал эту ссылку\n\n"
            "🖊 Напишите сюда всё, что хотите ему передать\n\n"
            "Можно отправлять:\n"
            "💬 текст\n"
            "📷 фото\n"
            "🎥 видео\n"
            "🔊 голосовые\n"
            "📹 кружки\n"
            "✨ стикеры",
            reply_markup=cancel_btn()
        )

        return

    await message.answer(
        f"Начните получать анонимные вопросы прямо сейчас!\n\n"
        f"👉 {link}\n\n"
        f"Разместите эту ссылку ☝️ в описании своего профиля Telegram, TikTok, Instagram (stories), чтобы вам могли написать 💬",
        reply_markup=share_btn(link)
    )


# ───────── ОТПРАВКА СООБЩЕНИЯ ─────────
@dp.message()
async def send_question(message: types.Message):

    sender_id = message.from_user.id

    if sender_id not in user_targets:
        return

    target = user_targets[sender_id]

    text = message.text or message.caption or "медиа"

    sent = await message.copy_to(target)

    async with aiosqlite.connect(DB) as db:
        await db.execute(
            "INSERT INTO questions(sender_id,receiver_id,message_id) VALUES(?,?,?)",
            (sender_id, target, sent.message_id)
        )
        await db.commit()

    await send_admin_log(message, target, text)

    await message.answer(
        "✅ Сообщение отправлено, ожидайте ответ!",
        reply_markup=again_btn()
    )

    bot_username = (await bot.get_me()).username
    link = f"https://t.me/{bot_username}?start={sender_id}"

    await message.answer(
        f"Начните получать анонимные вопросы прямо сейчас!\n\n"
        f"👉 {link}\n\n"
        f"Разместите эту ссылку ☝️ в описании своего профиля Telegram, TikTok, Instagram (stories), чтобы вам могли написать 💬",
        reply_markup=share_btn(link)
    )


# ───────── ОТВЕТ ─────────
@dp.message(F.reply_to_message)
async def reply_answer(message: types.Message):

    msg_id = message.reply_to_message.message_id

    async with aiosqlite.connect(DB) as db:
        async with db.execute(
            "SELECT sender_id FROM questions WHERE message_id=?",
            (msg_id,)
        ) as cur:
            row = await cur.fetchone()

    if not row:
        return

    sender_id = row[0]

    if message.text:
        await bot.send_message(
            sender_id,
            f"💬 Ответ:\n\n{message.text}",
            reply_markup=again_btn()
        )
    else:
        await message.copy_to(sender_id)

    await message.answer("✅ Ответ успешно отправлен")


# ───────── КНОПКИ ─────────
@dp.callback_query(F.data == "again")
async def again(call: types.CallbackQuery):

    user_id = call.from_user.id

    if user_id not in user_targets:
        return

    await call.message.answer(
        "🚀 Напишите ещё одно сообщение\n\n"
        "Можно отправить текст или медиа"
    )


@dp.callback_query(F.data == "cancel")
async def cancel(call: types.CallbackQuery):

    bot_username = (await bot.get_me()).username
    user_id = call.from_user.id
    link = f"https://t.me/{bot_username}?start={user_id}"

    await call.message.answer(
        f"Начните получать анонимные вопросы прямо сейчас!\n\n"
        f"👉 {link}",
        reply_markup=share_btn(link)
    )


# ───────── ЗАПУСК ─────────
async def main():
    await init_db()
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
