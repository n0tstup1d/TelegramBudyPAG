from dotenv import load_dotenv
import os

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")
TEAM_CHAT_ID = int(os.getenv("TEAM_CHAT_ID"))
SUPPORT_URL = os.getenv("SUPPORT_URL")
PARTNERSHIP_URL = os.getenv("PARTNERSHIP_URL")
CONTENT_URL = os.getenv("CONTENT_URL")
USERS_CHAT_ID = int(os.getenv("USERS_CHAT_ID"))

# Рабочая супергруппа команды с включёнными темами (Forum Topics).
# Пользователь пишет в личку боту, а бот создаёт отдельную тему для каждого обращения.
# Если SUPPORT_DIALOG_CHAT_ID не указан, используется TEAM_CHAT_ID.
SUPPORT_DIALOG_CHAT_ID = int(os.getenv("SUPPORT_DIALOG_CHAT_ID") or TEAM_CHAT_ID)

# Закрытое тестирование: доступ выдаётся вручную через админку.
# Пользователь всё равно проходит соглашение и экран подписки на старте.
