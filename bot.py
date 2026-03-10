import asyncio
import aiosqlite
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from config import BOT_TOKEN, ADMIN_ID

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
DB_PATH = "db.sqlite3"

# ────────────── ИНИЦИАЛИЗАЦИЯ БАЗЫ ──────────────
async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            username TEXT,
            start_param TEXT UNIQUE
        )
        """)
        await db.execute("""
        CREATE TABLE IF NOT EXISTS questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sender_id INTEGER,
            receiver_id INTEGER,
            message_type TEXT,
            content TEXT,
            message_id INTEGER
        )
        """)
        await db.commit()

# ────────────── ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ──────────────
user_targets = {}

async def store_target(sender_id, target_id):
    user_targets[sender_id] = target_id

async def get_target(sender_id):
    return user_targets.get(sender_id)

# ────────────── КНОПКИ ──────────────
def cancel_button(sender_id):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data=f"cancel_to_start_{sender_id}")]
    ])

def share_link_keyboard(user_id, bot_username):
    user_link = f"https://t.me/{bot_username}?start={user_id}"
    share_text = f"По этой ссылке можно прислать мне анонимное сообщение:\n👉 {user_link}"
    share_url = f"https://t.me/share/url?url={share_text}"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📤 Поделиться ссылкой", url=share_url)]
    ])

# ────────────── /start ──────────────
@dp.message(CommandStart())
async def cmd_start(message: types.Message, command: CommandStart):
    user_id = message.from_user.id
    bot_username = (await bot.get_me()).username
    start_param = command.args or str(user_id)

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT OR IGNORE INTO users (id, username, start_param)
            VALUES (?, ?, ?)
        """, (user_id, message.from_user.username, start_param))
        await db.commit()

    user_link = f"https://t.me/{bot_username}?start={user_id}"

    if command.args and command.args != str(user_id):
        # Пользователь пришёл по чужой ссылке — экран для анонимного сообщения
        target_id = int(command.args)
        await store_target(user_id, target_id)
        await message.answer(
            "🚀 Здесь можно отправить анонимное сообщение человеку, который опубликовал эту ссылку\n\n"
            "🖊 Напишите сюда всё, что хотите ему передать, и через несколько секунд он получит ваше сообщение, но не будет знать от кого\n\n"
            "Отправить можно фото, видео, 💬 текст, 🔊 голосовые, 📷 видеосообщения, а также ✨ стикеры",
            reply_markup=cancel_button(user_id)
        )
        return

    # Главный экран для владельца ссылки
    await message.answer(
        f"👋 Привет, {message.from_user.first_name}!\n\n"
        f"💬 Начните получать анонимные вопросы прямо сейчас!\n\n"
        f"Ваша ссылка:\n{user_link}\n\n"
        f"Разместите эту ссылку ☝️ в описании своего профиля Telegram, TikTok, Instagram (stories), чтобы вам могли написать 💬",
        reply_markup=share_link_keyboard(user_id, bot_username)
    )

# ────────────── Отправка анонимного сообщения владельцу и админу ──────────────
async def forward_to_receiver_and_admin(sender_id, target_id, message_type, content, media_message=None):
    # ────────────── 1️⃣ А получает уведомление без кнопки ──────────────
    try:
        msg = await bot.send_message(
            target_id,
            f"💬 У тебя новое сообщение!\n\n{content}\n\n↩️ Свайпни для ответа"
        )
    except:
        msg = None

    # ────────────── 2️⃣ Логирование админу ──────────────
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT username FROM users WHERE id=?", (target_id,)) as cur:
            target_user = await cur.fetchone()
            target_username = target_user[0] if target_user else "unknown"
        async with db.execute("SELECT username FROM users WHERE id=?", (sender_id,)) as cur:
            sender_user = await cur.fetchone()
            sender_username = sender_user[0] if sender_user else "unknown"

        log_text = (
            f"📝 Новое анонимное сообщение\n\n"
            f"Отправитель: @{sender_username} (ID: {sender_id})\n"
            f"Кому: @{target_username} (ID: {target_id})\n"
            f"Тип: {message_type}\n"
            f"Содержание: {content}"
        )
        await bot.send_message(ADMIN_ID, log_text)

        # ────────────── Сохраняем message_id для reply ──────────────
        await db.execute("""
            INSERT INTO questions (sender_id, receiver_id, message_type, content, message_id)
            VALUES (?, ?, ?, ?, ?)
        """, (sender_id, target_id, message_type, content, msg.message_id if msg else None))
        await db.commit()

    # ────────────── 3️⃣ Б получает уведомление ✅ ──────────────
    bot_username = (await bot.get_me()).username
    user_link = f"https://t.me/{bot_username}?start={sender_id}"

    # Сообщение об успешной отправке
    kb_again = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✍️ Написать ещё", callback_data="write_again")]
    ])
    await bot.send_message(sender_id, "✅ Сообщение отправлено, ожидайте ответ!", reply_markup=kb_again)

    # Ссылка для распространения
    share_text = (
        f"Начните получать анонимные вопросы прямо сейчас!\n\n"
        f"👉 {user_link}\n\n"
        "Разместите эту ссылку ☝️ в описании своего профиля Telegram, TikTok, Instagram (stories), чтобы вам могли написать 💬"
    )
    share_url = f"https://t.me/share/url?url={share_text}"
    kb_share = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📤 Поделиться ссылкой", url=share_url)]
    ])
    await bot.send_message(sender_id, share_text, reply_markup=kb_share)

# ────────────── Обработка текстовых сообщений от Б ──────────────
@dp.message(F.text & ~F.command)
async def handle_text(message: types.Message):
    sender_id = message.from_user.id
    target_id = await get_target(sender_id)
    if not target_id:
        return
    await forward_to_receiver_and_admin(sender_id, target_id, "Текст", message.text, media_message=message)

# ────────────── Обработка медиа ──────────────
@dp.message(F.content_type.in_({"photo", "video", "voice", "video_note", "sticker"}))
async def handle_media(message: types.Message):
    sender_id = message.from_user.id
    target_id = await get_target(sender_id)
    if not target_id:
        return

    content = message.caption or f"[{message.content_type}]"
    await forward_to_receiver_and_admin(sender_id, target_id, message.content_type, content, media_message=message)

    try:
        await message.copy_to(target_id)
    except:
        pass

# ────────────── Reply от А ──────────────
@dp.message(F.reply_to_message)
async def reply_from_a(message: types.Message):
    reply_msg_id = message.reply_to_message.message_id

    # Ищем sender_id (Б) по message_id в базе
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT sender_id FROM questions WHERE message_id=?", (reply_msg_id,)) as cur:
            row = await cur.fetchone()
            if row:
                target_id = row[0]

    if not row:
        await message.answer("⚠️ Не удалось определить получателя.")
        return

    # Отправка ответа Б
    kb_again = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✍️ Написать ещё", callback_data="write_again")]
    ])
    await bot.send_message(target_id, f"💬 Ответ от @{message.from_user.username}:\n\n{message.text}", reply_markup=kb_again)
    await message.answer("✅ Ответ успешно отправлен")

# ────────────── Кнопка "Написать ещё" ──────────────
@dp.callback_query(F.data == "write_again")
async def write_again(call: types.CallbackQuery):
    sender_id = call.from_user.id
    target_id = await get_target(sender_id)
    if not target_id:
        await call.message.answer("⚠️ Не удалось определить получателя.")
        return
    await call.message.answer(
        "🚀 Здесь можно отправить анонимное сообщение человеку, который опубликовал эту ссылку\n\n"
        "🖊 Напишите сюда всё, что хотите ему передать...",
        reply_markup=cancel_button(sender_id)
    )
    await call.message.delete()

# ────────────── Кнопка "Отмена" ──────────────
@dp.callback_query(F.data.startswith("cancel_to_start_"))
async def cancel_to_start(call: types.CallbackQuery):
    user_id = call.from_user.id
    bot_username = (await bot.get_me()).username
    kb_share = share_link_keyboard(user_id, bot_username)
    await call.message.answer(
        f"👋 Начните получать анонимные вопросы прямо сейчас!\n\n"
        f"👉 https://t.me/{bot_username}?start={user_id}\n\n"
        f"Разместите эту ссылку ☝️ в описании своего профиля Telegram, TikTok, Instagram (stories), чтобы вам могли написать 💬",
        reply_markup=kb_share
    )
    await call.message.delete()

# ────────────── Запуск бота ──────────────
async def main():
    await init_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
