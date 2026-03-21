# NafasOps Bot 🤖

A Telegram bot for managing Nafas operational data — service summaries, client memory management, and Google Sheets integration.

## Features

- **📊 Year-to-date & monthly summaries** from Google Sheets data
- **📋 Client memory** with service history tracking
- **🔍 Fuzzy search** for client name lookups
- **🔄 Manual sync** from Google Sheets to local memory
- **🔒 Access control** via allowed Telegram user IDs

## Commands

| Command | Description |
|---------|-------------|
| `/start` | Show welcome message |
| `/help` | List all commands |
| `/test_sheet` | Test Google Sheets connection |
| `/summary` | Year-to-date summary |
| `/summary_1` … `/summary_12` | Monthly summary (Jan–Dec) |
| `/ask <client name>` | Look up client info (supports fuzzy matching) |
| `/sync` | Sync Sheet data to local memory |

## Setup

### Prerequisites

- Python 3.10+
- A Telegram Bot token (from [@BotFather](https://t.me/BotFather))
- A Google Cloud service account with Sheets API access

### Installation

```bash
# Clone the repository
git clone https://github.com/alphabenedict/nafas-ops-bot.git
cd nafas-ops-bot

# Create virtual environment
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### Configuration

Create a `.env` file in the project root:

```env
TELEGRAM_TOKEN=your_telegram_bot_token
SHEET_ID=your_google_sheet_id
SHEET_JSON={"type":"service_account",...}  # or path to JSON key file

# Optional: restrict access to specific Telegram user IDs (comma-separated)
ALLOWED_USER_IDS=123456789,987654321
```

> **Note:** You can set `SHEET_JSON` to either the full JSON content (for Heroku/cloud) or a file path (for local development).

### Running

```bash
python agent.py
```

### Deployment (Heroku)

The included `Procfile` runs the bot as a worker process:

```
worker: python agent.py
```

Set all `.env` variables as Heroku config vars.

## Project Structure

```
├── agent.py            # Main bot entry point & Telegram handlers
├── ai_helpers.py       # Client memory management & fuzzy search
├── config.py           # Environment configuration
├── sheet_helpers.py    # Google Sheets integration & summaries
├── test_integrations.py # Integration tests
├── requirements.txt    # Pinned Python dependencies
├── Procfile            # Heroku deployment config
└── .gitignore
```

## License

Internal use — Nafas.
