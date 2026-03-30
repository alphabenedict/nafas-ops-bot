# NafasOps Bot 🤖

A sophisticated, multi-tenant Telegram operational platform designed to serve as the "friendly neighborhood nerd" for Nafas internal teams. It seamlessly bridges Google Sheets data with a natural language AI chat interface, making operations and customer management a breeze.

## ✨ Features

- **🧠 AI-Powered Chat**: Ask open-ended questions! The bot uses OpenAI (`gpt-4o-mini`) to process complex data and return human-friendly, actionable insights instead of just spitting out raw numbers.
- **🏢 Multi-Tenant Platform**: Built on a robust **FastAPI** + **Uvicorn** dashboard and an SQLite/SQLAlchemy backend, this platform scales to run multiple dynamic Telegram bots concurrently.
- **📊 Google Sheets Sync**: Fetches live operational data (service summaries, schedules, client histories) from Google Sheets and caches it securely in local JSON memory.
- **🔍 Smart Client Search**: Fuzzy matching lets operators find client records instantly, even with typos.
- **🔒 Access Control**: Role-based access ensures only whitelisted Telegram accounts can query internal data.

## 🛠️ Tech Stack

- **Python 3.10+**
- **Web Framework:** FastAPI, Uvicorn
- **Database:** SQLAlchemy, SQLite (`platform_data.db`)
- **APIs:** python-telegram-bot (v20+), OpenAI API, Google Sheets (gspread)

## 📋 Commands

You can interact normally by chatting (e.g., *"Berapa total service tahun ini?"* atau *"Ada info klien Budi?"*), or use these quick commands:

| Command | Description |
|---------|-------------|
| `/start` | Show welcome message and quick-action buttons |
| `/help` | List all available commands & operations |
| `/ask <client>` | Look up client info (supports fuzzy matching) |
| `/summary` | Generate Year-To-Date operational summary |
| `/summary_1` … `12` | Generate monthly summary (Jan–Dec) |
| `/sync` | Force-sync Google Sheets data to local memory |
| `/test_sheet` | Test Google Sheets connection |

## 🚀 Setup & Installation

### 1. Prerequisites
- Python 3.10+ installed
- Telegram Bot Token (from [@BotFather](https://t.me/BotFather))
- Google Cloud Service Account with Sheets access (`.json` key)
- OpenAI API Key

### 2. Local Setup
```bash
# Clone the repository
git clone https://github.com/alphabenedict/nafas-ops-bot.git
cd nafas-ops-bot

# Create and activate virtual environment
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Configuration
Create a `.env` file in the root directory:

```env
TELEGRAM_TOKEN=your_telegram_bot_token
OPENAI_API_KEY=your_openai_api_key
SHEET_ID=your_google_sheet_id
SHEET_JSON={"type":"service_account",...}  # OR path to JSON file

# Optional:
ALLOWED_USER_IDS=123456789,987654321
PORT=8000
```

### 4. Running the Platform
To run the full multi-tenant FastAPI server and bots concurrently:
```bash
python main.py
```

*Alternatively, to run just the Telegram Bot worker (for standalone use):*
```bash
python agent.py
```

## 📁 Project Structure

```text
├── main.py              # Entry point: runs FastAPI & multi-tenant bots concurrently
├── agent.py             # Main single-bot Telegram handlers
├── ai_helpers.py        # Local client memory, fuzzy search, JSON DB logic
├── ai_summarizer.py     # OpenAI abstraction for natural chat & humanized data
├── sheet_helpers.py     # Google Sheets syncing & data processing
├── config.py            # Environment configuration
├── /control             # Database & FastAPI web server logic
├── /static              # Web static assets
└── requirements.txt     # Python dependencies
```

## 📄 License
Internal use — Nafas.
