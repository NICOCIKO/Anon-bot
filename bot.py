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


# ───────── ИНИЦИАЛИЗАЦИЯ БАЗЫ ─────────
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
        f"📨 <b>Новое сообщение</b>\n\n"
        f"👤 <b>Отправитель:</b> {sender.first_name} (@{sender.username or 'нет'})\n"
        f"💬 <b>Никнейм:</b> {sender.full_name}\n"
        f"<b>ID:</b> {sender.id}\n\n"
        f"🎯 <b>Получатель ID:</b> {target_id}\n\n"
        f"💬 {text}"
    )

    for admin in ADMINS:
        try:
            await bot.send_message(admin, log)
            await message.copy_to(admin)
        except:
            pass


# ───────── /START ─────────
@dp.message(CommandStart())
async def start(message: types.Message, command: CommandStart):
    user_id = message.from_user.id
    bot_username = (await bot.get_me()).username

    # Если зашли по чужой ссылке
    if command.args:
        try:
            target_id = int(command.args)
        except:
            return

        if target_id == user_id:
            return

        user_targets[user_id] = target_id

        await message.answer(
            "<b>🚀 Здесь можно отправить анонимное сообщение человеку, который опубликовал эту ссылку</b>\n\n"
            "<b>🖊 Напишите сюда всё, что хотите ему передать, и через несколько секунд он получит ваше сообщение, но не будет знать от кого</b>\n\n"
            "<b>Отправить можно фото, видео, 💬 текст, 🔊 голосовые, 📷 видеосообщения (кружки), а также ✨ стикеры</b>",
            reply_markup=cancel_btn()
        )
        return

    # Иначе обычный старт — показываем свою ссылку
    link = f"https://t.me/{bot_username}?start={user_id}"

    await message.answer(
        f"<b>Начните получать анонимные вопросы прямо сейчас!</b>\n\n"
        f"<b>Ваша ссылка:</b>\n{link}\n\n"
        "<b>Разместите эту ссылку ☝️ в описании своего профиля Telegram, TikTok, Instagram (stories), чтобы вам могли написать 💬</b>",
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
            "<b>❌ Сообщение не доставлено.</b>\n\n"
            "<b>Пользователь не активировал бота.</b>"
        )
        return

    # Сообщение для A — без кнопок
    await bot.send_message(target, "<b>💬 У тебя новое сообщение!</b>")

    # Лог для админов
    await send_admin_log(message, target)

    # Ответ Б
    await message.answer(
        "<b>✅ Сообщение отправлено!</b>",
        reply_markup=again_btn()
    )


# ───────── ОБРАБОТКА КНОПОК ─────────
@dp.callback_query(lambda c: c.data == "again")
async def again(call: types.CallbackQuery):
    await call.message.answer("<b>✍️ Напишите сообщение</b>")


@dp.callback_query(lambda c: c.data == "cancel")
async def cancel(call: types.CallbackQuery):
    bot_username = (await bot.get_me()).username
    link = f"https://t.me/{bot_username}?start={call.from_user.id}"
    await call.message.answer(
        f"<b>Начните получать анонимные вопросы прямо сейчас!</b>\n\n"
        f"<b>👉 {link}</b>",
        reply_markup=share_btn(link)
    )


# ───────── ЗАПУСК ─────────
async def main():
    await init_db()
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
