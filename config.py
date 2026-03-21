import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
SHEET_ID = os.getenv("SHEET_ID")
SHEET_JSON = os.getenv("SHEET_JSON")

# Access control: comma-separated Telegram user IDs allowed to use the bot
_allowed = os.getenv("ALLOWED_USER_IDS", "")
ALLOWED_USER_IDS = [
    int(uid.strip()) for uid in _allowed.split(",") if uid.strip().isdigit()
]
