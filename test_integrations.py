import asyncio
import os
from config import TELEGRAM_TOKEN, OPENAI_API_KEY
from sheet_helpers import fetch_sheet_dataframe
import openai
from telegram import Bot

async def test_all():
    print("Testing integrations...")
    
    # 1. Test Google Sheets
    print("\n--- 1. Testing Google Sheets ---")
    try:
        df = fetch_sheet_dataframe("Sheet1")
        print(f"✅ Success! Fetched {len(df)} rows from Google Sheets.")
    except Exception as e:
        print(f"❌ Failed to fetch from Google Sheets: {e}")

    # 2. Test OpenAI API
    print("\n--- 2. Testing OpenAI API ---")
    try:
        openai.api_key = OPENAI_API_KEY
        response = openai.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": "Say hello world"}]
        )
        print(f"✅ Success! OpenAI responded: {response.choices[0].message.content}")
    except Exception as e:
        print(f"❌ Failed to call OpenAI: {e}")

    # 3. Test Telegram Bot
    print("\n--- 3. Testing Telegram Bot ---")
    try:
        bot = Bot(token=TELEGRAM_TOKEN)
        bot_info = await bot.get_me()
        print(f"✅ Success! Telegram Bot Name: {bot_info.first_name} (@{bot_info.username})")
    except Exception as e:
        print(f"❌ Failed to connect to Telegram Bot: {e}")

if __name__ == "__main__":
    asyncio.run(test_all())
