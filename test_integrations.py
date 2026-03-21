import asyncio
import logging
from config import TELEGRAM_TOKEN
from sheet_helpers import fetch_sheet_dataframe
from telegram import Bot

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


async def test_all():
    logger.info("Testing integrations...")

    # 1. Test Google Sheets
    logger.info("--- 1. Testing Google Sheets ---")
    try:
        df = fetch_sheet_dataframe("Sheet1")
        logger.info("✅ Success! Fetched %d rows from Google Sheets.", len(df))
    except Exception as e:
        logger.error("❌ Failed to fetch from Google Sheets: %s", e)

    # 2. Test Telegram Bot
    logger.info("--- 2. Testing Telegram Bot ---")
    try:
        bot = Bot(token=TELEGRAM_TOKEN)
        bot_info = await bot.get_me()
        logger.info(
            "✅ Success! Telegram Bot Name: %s (@%s)",
            bot_info.first_name,
            bot_info.username,
        )
    except Exception as e:
        logger.error("❌ Failed to connect to Telegram Bot: %s", e)


if __name__ == "__main__":
    asyncio.run(test_all())
