import os

# Берём токен бота из переменной окружения BOT_TOKEN
BOT_TOKEN = os.getenv("BOT_TOKEN")

# Берём ID админа из переменной окружения ADMIN_ID и преобразуем в int
ADMIN_ID = int(os.getenv("ADMIN_ID"))