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