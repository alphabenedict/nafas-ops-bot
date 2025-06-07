# config.py
from dotenv import load_dotenv
import os

# Load .env into environment
load_dotenv()

# Fetch values
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
SHEET_JSON = os.getenv("SHEET_JSON")
SHEET_ID = os.getenv("SHEET_ID")

# (Optional) Basic sanity check:
if not TELEGRAM_TOKEN:
    raise ValueError("Missing TELEGRAM_TOKEN in .env")
if not OPENAI_API_KEY:
    raise ValueError("Missing OPENAI_API_KEY in .env")
if not SHEET_JSON:
    raise ValueError("Missing SHEET_JSON in .env")
if not SHEET_ID:
    raise ValueError("Missing SHEET_ID in .env")
