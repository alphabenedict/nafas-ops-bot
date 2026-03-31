# Nafas Ops Bot — Detailed Technical Documentation

> **Last updated:** 2026-03-31
> **Repo:** `nafas-ops-bot`
> **Entry point:** `main.py`

---

## Table of Contents

1. [Overview](#overview)
2. [Architecture at a Glance](#architecture-at-a-glance)
3. [Tech Stack](#tech-stack)
4. [Database Schema](#database-schema)
5. [Startup Flow](#startup-flow)
6. [Message Handling Flow](#message-handling-flow)
7. [Google Sheets Sync Flow](#google-sheets-sync-flow)
8. [RAG Pipeline (Knowledge Upload & Retrieval)](#rag-pipeline)
9. [Multi-Bot Tenant Flow](#multi-bot-tenant-flow)
10. [Web Dashboard Flow](#web-dashboard-flow)
11. [Conversation Summary Flow](#conversation-summary-flow)
12. [AI Prompt Construction](#ai-prompt-construction)
13. [Environment Variables](#environment-variables)
14. [Bot Commands (System Bot)](#bot-commands)
15. [Key File Reference](#key-file-reference)

---

## Overview

Nafas Ops Bot is a **multi-tenant Telegram bot platform** built as the internal operational assistant for Nafas — an air quality company. It bridges live **Google Sheets operational data** with a **natural language AI chat interface**, letting teams query service records, client history, and scheduling data through conversational Indonesian without needing spreadsheet access.

**Core capabilities:**
- Natural language Q&A over operational data (via OpenAI `gpt-4o-mini`)
- Live Google Sheets sync with 5-minute TTL cache
- Fuzzy client search with typo tolerance
- RAG (Retrieval-Augmented Generation) from uploaded knowledge bases (PDF, DOCX, TXT)
- Multi-tenant: run unlimited concurrent Telegram bots from a single platform
- Web dashboard (Mission Control) for bot management, contacts, analytics
- Conversation tracking and auto-generated summaries every 10 messages

---

## Architecture at a Glance

```
┌─────────────────────────────────────────────────────────────┐
│                          main.py                            │
│    asyncio.gather() runs these 3 concurrently:              │
│                                                             │
│   ┌──────────────┐  ┌──────────────┐  ┌────────────────┐   │
│   │  FastAPI     │  │  System Bot  │  │  Tenant Bots   │   │
│   │  (Uvicorn)   │  │  (agent.py)  │  │  (runner.py)   │   │
│   │  Port 8000   │  │  NafasOps    │  │  N bots async  │   │
│   └──────┬───────┘  └──────┬───────┘  └───────┬────────┘   │
│          │                 │                  │             │
└──────────┼─────────────────┼──────────────────┼────────────┘
           │                 │                  │
     Web Dashboard      Google Sheets       OpenAI API
     (Mission Control)  + OpenAI            + SQLite DB
     SQLite DB          + nafasmemory.json  + Telegram API
```

**Data stores:**
- `platform_data.db` — SQLite (users, bots, contacts, messages, knowledge, summaries)
- `nafasmemory.json` — local JSON flat-file cache of client records (synced from Sheets)
- In-memory cache — `_CACHE` dict in `sheet_helpers.py` (5-min TTL)

---

## Tech Stack

| Layer | Technology |
|---|---|
| Language | Python 3.10+ |
| Web framework | FastAPI + Uvicorn (ASGI) |
| Database ORM | SQLAlchemy 2.0 |
| Database engine | SQLite (`platform_data.db`) |
| Migrations | Alembic |
| Telegram | python-telegram-bot v20.3 (async) |
| AI | OpenAI API — `gpt-4o-mini` |
| Sheets | gspread + google-auth |
| Data processing | pandas |
| Document parsing | pypdf, python-docx |
| Auth | bcrypt, itsdangerous, Jinja2 |
| HTTP client | httpx |
| Async file I/O | aiofiles |
| Config | python-dotenv |

---

## Database Schema

```
User
├── id
├── email (unique)
├── password_hash
├── is_admin
└── created_at

Bot
├── id
├── owner_id → User.id
├── name
├── telegram_token (unique)
├── role_description
├── personality
├── is_active
├── is_system
├── created_at
└── updated_at

KnowledgeChunk
├── id
├── bot_id → Bot.id (cascade delete)
├── source_name
├── chunk_text
├── chunk_index
└── created_at

Contact
├── id
├── bot_id → Bot.id (cascade delete)
├── telegram_id
├── username
├── first_name
├── last_name
├── first_seen_at
└── last_seen_at
[UNIQUE: bot_id + telegram_id]

Message
├── id
├── contact_id → Contact.id (cascade delete)
├── bot_id → Bot.id
├── direction  ("inbound" | "outbound")
├── text
└── created_at

ConversationSummary
├── id
├── contact_id → Contact.id (cascade delete)
├── bot_id → Bot.id
├── summary_text
├── generated_at
└── message_count
```

All foreign key relationships cascade on delete.

---

## Startup Flow

**File:** `main.py`
**Entry:** `asyncio.run(main())`

```
asyncio.run(main())
│
├── 1. init_db()
│       └── Base.metadata.create_all(bind=engine)
│           Creates all tables if not exist
│
├── 2. _seed_nafasops_bot()
│       ├── Query: Bot WHERE is_system == True
│       └── If missing → INSERT system Bot record
│           (name, telegram_token, role_description, is_system=True)
│
├── 3. create_app()  [control/web/app.py]
│       ├── Mount /static
│       └── Register routers:
│           ├── auth_router       → /login, /logout, /register
│           ├── dashboard_router  → /dashboard
│           ├── bots_router       → /bots/*
│           ├── contacts_router   → /bots/{id}/contacts/*
│           └── knowledge_router  → /bots/{id}/knowledge/*
│
├── 4. config.Server(app, port=PORT or 8000)
│
└── 5. asyncio.gather()
        ├── server.serve()              → FastAPI web dashboard
        ├── start_nafas_bot()           → System bot (agent.py)
        └── start_all_tenant_bots()     → All active tenant bots
```

**`start_all_tenant_bots()`** (runner.py):
```
Query: Bot WHERE is_active == True
└── For each bot → start_tenant_bot_by_id(bot.id)  [concurrent tasks]
    If no bots → asyncio.Event().wait()  [sleep forever]
```

**`_run_bot_lifecycle(app, label)`** (runner.py):
```
app.initialize()
app.updater.start_polling(drop_pending_updates=True)
app.start()
asyncio.Event().wait()          ← runs forever
# on CancelledError:
app.updater.stop()
app.stop()
app.shutdown()
```

---

## Message Handling Flow

**Files:** `control/bots/handlers.py`, `ai_summarizer.py`, `control/bots/rag.py`

This is the end-to-end flow for every message sent to a **tenant bot**.

```
User sends Telegram message
│
▼
tenant_message_handler(update, context)     [handlers.py]
│
├── 1. Extract from context.bot_data:
│       bot_config      = Bot ORM record
│       session_factory = SQLAlchemy SessionLocal
│       api_key         = OPENAI_API_KEY
│
├── 2. _upsert_contact(db, bot_config.id, tg_user)
│       ├── Query: Contact WHERE bot_id + telegram_id
│       ├── If new  → INSERT Contact (telegram_id, username, first_name, last_name)
│       └── If exists → UPDATE last_seen_at
│
├── 3. _store_message(db, contact.id, bot_config.id, "inbound", user_text)
│       └── INSERT Message (direction="inbound")
│
├── 4. search_knowledge(db, bot_config.id, user_text)   [rag.py]
│       ├── Tokenize query → lowercase word tokens
│       ├── Query: all KnowledgeChunk WHERE bot_id
│       ├── Score each chunk (TF-IDF):
│       │       TF  = token_count / total_chunk_length
│       │       IDF = log(1 + 1/(TF + 1e-9))
│       │       score = Σ(TF × IDF) for query tokens
│       ├── Sort descending by score
│       ├── Filter out zero-relevance chunks
│       └── Return top 3 chunks joined by "\n\n"
│
├── 5. build_system_prompt(bot_config, knowledge_ctx)
│       └── Concatenate with "\n\n":
│           ├── bot_config.role_description
│           ├── bot_config.personality
│           ├── knowledge_ctx  (RAG results, if any)
│           └── "Jawab hanya berdasarkan informasi yang tersedia. Jangan mengarang data."
│
├── 6. _call_openai(system_prompt, user_text, api_key)
│       ├── AsyncOpenAI client
│       ├── model = "gpt-4o-mini"
│       ├── messages = [
│       │       {role: "system", content: system_prompt},
│       │       {role: "user",   content: user_text}
│       │   ]
│       ├── max_tokens = 1024
│       └── Returns response.choices[0].message.content
│
├── 7. _store_message(db, contact.id, bot_config.id, "outbound", reply_text)
│       └── INSERT Message (direction="outbound")
│
├── 8. update.message.reply_text(reply_text)
│       └── Send reply to Telegram user
│
└── 9. Background summary check (non-blocking)
        ├── Count all messages for contact
        └── If count % 10 == 0:
            └── asyncio.create_task(
                    _generate_summary_bg(contact_id, bot_id, api_key, msg_count)
                )
```

---

## Google Sheets Sync Flow

**File:** `sheet_helpers.py`

### Authentication

```
get_gspread_client()
├── Load SHEET_JSON (env var) as JSON string or file path
├── google.oauth2.service_account.Credentials with scopes:
│       ├── spreadsheets
│       └── drive.file
└── Returns gspread authorized client
```

### Data Fetch with Caching

```
fetch_sheet_dataframe(worksheet_name="Sheet1")
│
├── Check _CACHE dict:
│       If cached AND (now - cached_time) < 300 seconds → return cached DataFrame
│
└── Cache miss:
        ├── client.open_by_key(SHEET_ID).worksheet(worksheet_name)
        ├── ws.get_all_records()  → list of row dicts
        ├── pd.DataFrame(records)
        ├── Validate required columns: {Timestamp, Client Name, Service Type}
        ├── Store in _CACHE with timestamp
        └── Return DataFrame
```

### Data Aggregation

```
summarize_year_to_date()
├── fetch_sheet_dataframe()
├── date range: Jan 1 current year → now
├── _filter_by_date_range(df, start, end)
│       ├── pd.to_datetime(df["Timestamp"])
│       └── Filter rows where ParsedDate in [start, end]
└── _build_summary_lines(df_filtered, title)
        ├── Count total records
        ├── .value_counts() on Service Type
        ├── .value_counts() on on-time/late status
        ├── Latest service: sort ParsedDate desc → first row
        └── Return formatted string with bullet points

summarize_month(month_index, year)
└── Same flow with month-specific date range
```

### Memory Sync

```
sync_memory()
├── fetch_sheet_dataframe()
├── Filter: current year to now
└── _sync_memory_from_df(df_filtered)
        ├── Drop duplicates per Client Name (keep last)
        └── For each row → update_client_memory() [ai_helpers.py]
                └── Update nafasmemory.json with:
                    address, device, last_service, service_type,
                    technician, issue, solution, client_type, notes
```

---

## RAG Pipeline

**Files:** `control/services/knowledge_parser.py`, `control/bots/rag.py`, `control/web/routers/knowledge_router.py`

### Upload & Chunking

```
Constants:
  CHUNK_SIZE = 500 chars
  OVERLAP    = 50  chars
  STEP       = 500 - 50 = 450 chars

parse_upload(file_bytes, filename)
│
├── .pdf  → parse_pdf(file_bytes, source_name)
│               ├── PdfReader(BytesIO(file_bytes))
│               ├── Extract text from each page
│               ├── Join with "\n\n"
│               └── _chunk_text(text, source_name)
│
├── .docx → parse_docx(file_bytes, source_name)
│               ├── Document(BytesIO(file_bytes))
│               ├── Extract paragraph texts
│               ├── Join with "\n\n"
│               └── _chunk_text(text, source_name)
│
└── .txt  → parse_plain_text(text, source_name)
                └── _chunk_text(text, source_name)

_chunk_text(text, source_name)
├── Normalize: replace \n{3,} with \n\n
├── Sliding window loop:
│       start = 0
│       while start < len(text):
│           end = start + 500
│           chunk = text[start:end].strip()
│           yield (source_name, chunk, chunk_index)
│           start += 450        ← 50-char overlap
└── Returns list of (source_name, chunk_text, chunk_index) tuples
```

### Storage

```
POST /bots/{bot_id}/knowledge/text
├── parse_plain_text(content, source_name)
└── For each chunk → INSERT KnowledgeChunk(bot_id, source_name, chunk_text, chunk_index)

POST /bots/{bot_id}/knowledge/upload
├── Read file bytes from multipart upload
├── parse_upload(file_bytes, filename)
└── For each chunk → INSERT KnowledgeChunk(...)
```

### Retrieval

```
search_knowledge(db, bot_id, query, top_k=3)
│
├── Query: all KnowledgeChunk WHERE bot_id
├── _tokenize(query) → lowercase word tokens via \b\w+\b regex
│
├── For each chunk:
│       _score(chunk_tokens, query_tokens)
│           For each unique query token t:
│               TF  = count(t in chunk) / len(chunk_tokens)
│               IDF = log(1 + 1/(TF + 1e-9))
│               score += TF × IDF
│
├── Sort chunks descending by score
├── Filter: score > 0
├── Take top_k (default 3)
└── Return: "\n\n".join([chunk.chunk_text for chunk in top_chunks])
```

---

## Multi-Bot Tenant Flow

**Files:** `control/bots/runner.py`, `control/bots/factory.py`

### Internal State

```python
_running: dict[int, tuple[Application, asyncio.Task]] = {}
```

### Startup

```
start_all_tenant_bots()
├── db = SessionLocal()
├── Query: Bot WHERE is_active == True
├── For each bot:
│       asyncio.create_task(start_tenant_bot_by_id(bot.id))
└── asyncio.gather(*tasks)

start_tenant_bot_by_id(bot_id)
├── If bot_id in _running → return  (already running)
├── db = SessionLocal()
├── Query: Bot WHERE id == bot_id
├── build_tenant_application(bot_row)   [factory.py]
├── task = asyncio.create_task(_run_bot_lifecycle(app, label), name="bot_{bot_id}")
└── _running[bot_id] = (app, task)
```

### Bot Application Factory

```
build_tenant_application(bot_row)   [factory.py]
├── ApplicationBuilder().token(bot_row.telegram_token)
├── Inject into app.bot_data:
│       config           = bot_row          (full Bot ORM record)
│       db_session_factory = SessionLocal
│       openai_api_key   = OPENAI_API_KEY
├── Register MessageHandler:
│       filters = TEXT & ~COMMAND
│       callback = tenant_message_handler
└── Return configured Application
```

### Lifecycle

```
_run_bot_lifecycle(app, label)
├── await app.initialize()
├── await app.updater.start_polling(drop_pending_updates=True)
├── await app.start()
├── await asyncio.Event().wait()     ← runs until cancelled
│
└── on CancelledError:
        await app.updater.stop()
        await app.stop()
        await app.shutdown()

stop_tenant_bot_by_id(bot_id)
├── (app, task) = _running.pop(bot_id)
├── task.cancel()
└── await task  (suppresses CancelledError)
```

---

## Web Dashboard Flow

**Files:** `control/web/routers/`, `control/web/auth.py`

### Authentication Flow

```
POST /login
├── Query: User WHERE email == form.email
├── bcrypt.checkpw(form.password, user.password_hash)
├── If valid:
│       token = URLSafeTimedSerializer(SECRET_KEY).dumps(user.id)
│       Set httponly cookie "session" = token  (samesite=lax)
│       Redirect 302 → /dashboard
└── If invalid: render login.html with error

GET /register  (first-run only)
├── If db.query(User).count() > 0 → redirect /login
└── Render registration form

POST /register
├── Check user_count == 0 (safety gate)
├── hash_password(form.password) via bcrypt
├── INSERT User(email, password_hash, is_admin=True)
├── Set session cookie
└── Redirect → /dashboard

get_current_user(request, db)  (used as FastAPI dependency)
├── Extract "session" cookie
├── URLSafeTimedSerializer.loads(token, max_age=604800)   ← 7 days
└── Query: User WHERE id == decoded_user_id
```

### Bot Creation Flow

```
GET /bots/new
└── Render bot_create.html form

POST /bots/new
├── _validate_telegram_token(token)
│       GET https://api.telegram.org/bot{token}/getMe
│       Return bot_info if response["ok"] == true, else None
├── Check duplicate: Bot WHERE telegram_token == token
├── INSERT Bot(owner_id, name, telegram_token, role_description, personality, is_active=False)
└── Redirect → /bots/{bot_id}

GET /bots/{bot_id}
├── Query: Bot WHERE id == bot_id AND (owner_id == user.id OR is_system)
├── get_bot_stats(db, bot_id)
│       ├── COUNT(Contact WHERE bot_id)
│       └── COUNT(Message WHERE bot_id)
├── get_contact_list(db, bot_id, page=1, per_page=10)
├── Query: KnowledgeChunk WHERE bot_id
├── is_running(bot_id)  → bool from _running dict
└── Render bot_detail.html
```

### Bot Lifecycle Control

```
POST /bots/{bot_id}/activate
├── bot.is_active = True
├── db.commit()
└── asyncio.create_task(start_tenant_bot_by_id(bot_id))

POST /bots/{bot_id}/deactivate
├── bot.is_active = False
├── db.commit()
└── asyncio.create_task(stop_tenant_bot_by_id(bot_id))

POST /bots/{bot_id}/delete
├── If is_running(bot_id) → stop_tenant_bot_by_id(bot_id)
└── db.delete(bot)  → cascades to KnowledgeChunk, Contact, Message, ConversationSummary
```

---

## Conversation Summary Flow

**File:** `control/services/summarizer.py`
**Trigger:** Every 10 messages per contact (`SUMMARY_TRIGGER_EVERY = 10`)

```
Background trigger in handlers.py:
    msg_count = db.query(Message).filter(contact_id).count()
    if msg_count % 10 == 0:
        asyncio.create_task(_generate_summary_bg(...))

generate_contact_summary(db, contact_id, bot_id, api_key, msg_count)
│
├── Query: last 50 Messages WHERE contact_id
│           ORDER BY created_at ASC
│
├── Build conversation text:
│       For each message:
│           "User: {text}"  ← if direction == "inbound"
│           "Bot:  {text}"  ← if direction == "outbound"
│       Join with "\n"
│
├── OpenAI call:
│       model = "gpt-4o-mini"
│       system = "Buat ringkasan singkat dari percakapan berikut..."
│       user   = conversation_text
│       max_tokens = 512
│
└── Upsert ConversationSummary:
        Query: ConversationSummary WHERE contact_id AND bot_id ORDER BY generated_at DESC
        If exists → UPDATE summary_text, message_count, generated_at
        If new    → INSERT ConversationSummary(contact_id, bot_id, summary_text, message_count)
```

---

## AI Prompt Construction

**Files:** `ai_summarizer.py`, `control/bots/handlers.py`

### System Bot — Report Prompt (`SYSTEM_PROMPT`)

Used for `/summary` and related commands. Transforms raw structured data into conversational Indonesian.

```
Kamu adalah NafasOps Bot — asisten operasional internal Nafas yang ramah dan cerdas.
Nafas adalah perusahaan yang fokus pada kualitas udara.

Style guidance:
- Gunakan bahasa Indonesia santai tapi profesional
- Mulai dengan sapaan ringan tentang data
- Gunakan bullet points (•) untuk data/angka supaya mudah dibaca
- Berikan konteks/insight singkat
- Gunakan emoji secukupnya
- Akhiri dengan komentar penutup supportive/actionable
- Tetap ringkas, maksimal 2-3 paragraf
- JANGAN mengarang data, hanya gunakan data yang diberikan
```

### System Bot — Chat Prompt (`CHAT_SYSTEM_PROMPT`)

Used for free-text questions via `chat_with_data()`.

```
Kamu adalah NafasOps Bot — asisten operasional internal Nafas
Fokus: kualitas udara dan perawatan perangkat pemurni

Bisa menjawab:
- Ringkasan operasional (bulanan/tahunan)
- Info klien (alamat, device, riwayat service, teknisi)
- Data layanan (on time vs late, jenis service)
- Pertanyaan umum operasional

Style:
- Bahasa Indonesia santai tapi profesional
- Jawab langsung dan natural seperti teman kerja
- Gunakan bullet points untuk spesifikasi/riwayat
- Berikan insight langsung dari data (jangan suruh ketik perintah)
- Gunakan emoji secukupnya
- Ringkas dan to-the-point
- JANGAN mengarang data
- Ramah saat user sapaan

Hari ini: {today}
```

### System Bot — Prompt Variations

| Function | Purpose | User message template |
|---|---|---|
| `humanize_summary()` | Reformat raw summary | "Berikut data ringkasan operasional. Tolong sampaikan ulang dengan gaya santai..." |
| `humanize_client_info()` | Reformat client record | "Berikut data klien '{name}'. Tolong sampaikan ulang dengan gaya natural..." |
| `chat_with_data()` | Free-text Q&A | Injects YTD summary + client list as context, then appends user question |

**`chat_with_data()` injected user message:**
```
Berikut data operasional yang tersedia saat ini:

{data_context}

---

Pertanyaan/pesan dari user: {user_message}
```

### Tenant Bot — Dynamic Prompt

Built per-message in `build_system_prompt()` (`handlers.py`):

```
{bot_config.role_description}

{bot_config.personality}

{knowledge_ctx}           ← RAG top-3 chunks (if any)

Jawab hanya berdasarkan informasi yang tersedia. Jangan mengarang data.
```

Each bot has its own `role_description` and `personality` set at creation time.

---

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `TELEGRAM_TOKEN` | Yes | System bot token |
| `OPENAI_API_KEY` | Yes | OpenAI API key |
| `SHEET_ID` | Yes | Google Sheets document ID |
| `SHEET_JSON` | Yes | Service account JSON (inline string or file path) |
| `ALLOWED_USER_IDS` | No | Comma-separated Telegram IDs (empty = open) |
| `DATABASE_URL` | No | Default: `sqlite:///./platform_data.db` |
| `SECRET_KEY` | Yes | Session token signing key (change in production) |
| `PORT` | No | Web server port (default: `8000`) |

---

## Bot Commands

These apply to the **system NafasOps bot** (`agent.py`):

| Command | Description |
|---|---|
| `/start` | Welcome message with interactive inline menu |
| `/help` | Available commands and usage |
| `/ask <client>` | Look up specific client data from memory |
| `/summary` | Year-to-date service summary |
| `/summary_1` – `/summary_12` | Summary for a specific month (1 = Jan, 12 = Dec) |
| `/sync` | Force refresh: pull latest data from Google Sheets → memory |
| `/test_sheet` | Verify Google Sheets connection and print sample rows |
| Free text | Natural language Q&A — powered by `chat_with_data()` |

**Example natural language queries:**
- `Berapa total service tahun ini?`
- `Ada info klien Sari?`
- `Service apa yang paling banyak bulan ini?`

---

## Key File Reference

```
nafas-ops-bot/
│
├── main.py                          Orchestrator — boots DB, web, system bot, tenant bots
├── agent.py                         System NafasOps bot handlers + command routing
├── config.py                        Env var loading (tokens, IDs, DB URL)
├── sheet_helpers.py                 Sheets auth, fetch, TTL cache, aggregation
├── ai_helpers.py                    nafasmemory.json read/write, fuzzy client search
├── ai_summarizer.py                 OpenAI wrappers, prompt templates, humanization
│
├── control/
│   ├── db/
│   │   ├── models.py                ORM models: User, Bot, KnowledgeChunk, Contact, Message, ConversationSummary
│   │   └── database.py              Engine, SessionLocal, init_db()
│   │
│   ├── bots/
│   │   ├── runner.py                Async lifecycle manager, _running dict, start/stop helpers
│   │   ├── factory.py               build_tenant_application() — wires token + handlers
│   │   ├── handlers.py              tenant_message_handler(), build_system_prompt()
│   │   └── rag.py                   search_knowledge(), _tokenize(), _score() (TF-IDF)
│   │
│   ├── web/
│   │   ├── app.py                   FastAPI app factory, router registration
│   │   ├── auth.py                  Session tokens, bcrypt, get_current_user dependency
│   │   └── routers/
│   │       ├── auth_router.py       /login, /logout, /register
│   │       ├── dashboard_router.py  /dashboard
│   │       ├── bots_router.py       /bots/* — CRUD, activate/deactivate
│   │       ├── contacts_router.py   /bots/{id}/contacts — view history
│   │       └── knowledge_router.py  /bots/{id}/knowledge — upload text/files
│   │
│   └── services/
│       ├── analytics.py             get_bot_stats(), get_contact_list()
│       ├── knowledge_parser.py      _chunk_text(), parse_pdf/docx/plain
│       └── summarizer.py            generate_contact_summary()
│
├── templates/                       Jinja2 HTML templates for web dashboard
├── nafasmemory.json                 Flat-file client record cache (auto-updated by sync)
├── platform_data.db                 SQLite database
├── Procfile                         web: python main.py (Heroku/Render)
└── requirements.txt                 Python dependencies
```
