import logging
import re

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    CallbackQueryHandler,
    filters,
)

from ai_helpers import get_client_memory, search_clients, load_memory
from ai_summarizer import humanize_summary, humanize_client_info, chat_with_data
from config import TELEGRAM_TOKEN, ALLOWED_USER_IDS
from sheet_helpers import (
    fetch_sheet_dataframe,
    summarize_year_to_date,
    summarize_month,
    sync_memory,
)

# ── Logging ──────────────────────────────────────────────────────────

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


# ── Access control ───────────────────────────────────────────────────

def is_authorized(user_id: int) -> bool:
    """Check if a Telegram user is allowed to use this bot.
    If ALLOWED_USER_IDS is empty, all users are allowed (open mode).
    """
    if not ALLOWED_USER_IDS:
        return True
    return user_id in ALLOWED_USER_IDS


async def check_auth(update: Update) -> bool:
    """Returns True if authorized, otherwise sends a rejection message."""
    if is_authorized(update.effective_user.id):
        return True
    await update.message.reply_text("⛔ Maaf, Anda tidak memiliki akses ke bot ini.")
    logger.warning(
        "Unauthorized access attempt by user %s (%s)",
        update.effective_user.id,
        update.effective_user.username,
    )
    return False


# ── Handlers ─────────────────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_auth(update):
        return
    welcome_text = (
        "Halo! Saya NafasOps‐Bot. 👋\n\n"
        "Kamu bisa langsung chat pakai bahasa biasa, misalnya:\n"
        "• \"Gimana ringkasan bulan ini?\"\n"
        "• \"Ada info soal klien Sari?\"\n"
        "• \"Berapa total service tahun ini?\"\n\n"
        "Atau pakai perintah:\n"
        "/summary — Ringkasan tahun berjalan.\n"
        "/summary_1 … /summary_12 — Ringkasan per bulan.\n"
        "/ask <nama client> — Info klien.\n"
        "/sync — Sinkronisasi data dari Sheet.\n"
    )

    keyboard = [
        [
            InlineKeyboardButton("📊 Ringkasan Tahun Ini", callback_data="summary"),
            InlineKeyboardButton("📅 Ringkasan Bulan Ini", callback_data="summary_month")
        ],
        [
            InlineKeyboardButton("🔄 Sync Data Sheet", callback_data="sync")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(welcome_text, reply_markup=reply_markup)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_auth(update):
        return
    help_text = (
        "💬 Chat aja langsung pakai bahasa biasa!\n\n"
        "Atau pakai perintah:\n"
        "/summary — Ringkasan tahun berjalan.\n"
        "/summary_1 … /summary_12 — Ringkasan per bulan.\n"
        "/ask <nama client> — Info klien (fuzzy search).\n"
        "/sync — Sinkronisasi data dari Sheet.\n"
        "/test_sheet — Test koneksi Sheet.\n"
    )
    await update.message.reply_text(help_text)


async def test_sheet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_auth(update):
        return
    try:
        df = fetch_sheet_dataframe(worksheet_name="Sheet1")
        row_count = len(df)
        cols = df.columns.tolist()
        reply = f"✅ Sukses menarik data dari Google Sheet!\nJumlah baris: {row_count}\nKolom: {cols}"
    except Exception as e:
        logger.exception("Failed to fetch sheet data")
        reply = f"⚠️ Gagal menarik data dari Sheet:\n{e}"
    await update.message.reply_text(reply)


async def summary_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_auth(update):
        return
    try:
        raw_summary = summarize_year_to_date()
        reply = humanize_summary(raw_summary)
        await update.message.reply_text(reply)
    except Exception as e:
        logger.exception("Error generating year-to-date summary")
        await update.message.reply_text(f"⚠️ Terjadi kesalahan saat membuat ringkasan:\n{e}")


async def monthly_summary_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_auth(update):
        return

    cmd = update.message.text
    match = re.match(r"/summary_(\d+)", cmd)
    if not match:
        await update.message.reply_text("Format salah. Gunakan /summary_<angka_bulan> (1–12).")
        return

    month_idx = int(match.group(1))
    if month_idx < 1 or month_idx > 12:
        await update.message.reply_text("Angka bulan harus antara 1 sampai 12.")
        return

    try:
        raw_summary = summarize_month(month_idx)
        reply = humanize_summary(raw_summary)
        await update.message.reply_text(reply)
    except Exception as e:
        logger.exception("Error generating monthly summary for month %d", month_idx)
        await update.message.reply_text(f"⚠️ Gagal membuat ringkasan bulan {month_idx}:\n{e}")


async def sync_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Explicitly sync Sheet data into local client memory."""
    if not await check_auth(update):
        return
    try:
        result = sync_memory()
        await update.message.reply_text(result)
    except Exception as e:
        logger.exception("Error syncing memory")
        await update.message.reply_text(f"⚠️ Gagal sinkronisasi:\n{e}")


def format_history(history_list, limit=3):
    """Format the last `limit` history entries as a readable string."""
    if not history_list:
        return "Tidak ada riwayat tersedia."

    recent = history_list[-limit:]
    lines = []
    for item in recent:
        date = item.get("date", "–")
        svc_type = item.get("type", "–")
        tech = item.get("tech", "–")
        issue = item.get("issue", "–")
        solu = item.get("solution", "–")
        lines.append(f"- {date} | {svc_type} | {tech} | {issue} → {solu}")
    return "\n".join(lines)


async def ask_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_auth(update):
        return

    text = update.message.text.strip()
    parts = text.split(" ", 1)
    if len(parts) < 2 or not parts[1].strip():
        await update.message.reply_text("Format salah. Gunakan: /ask <nama client>")
        return

    client_name = parts[1].strip()
    data = get_client_memory(client_name)

    if data:
        lines = [f"Memori untuk {client_name}:"]
        lines.append(f"• Address: {data.get('address', '–')}")
        lines.append(f"• Device: {data.get('device', '–')}")
        lines.append(f"• Last Service: {data.get('last_service', '–')}")
        lines.append(f"• Service Type: {data.get('service_type', '–')}")
        lines.append(f"• Technician: {data.get('technician', '–')}")
        hist = format_history(data.get("history", []), limit=3)
        lines.append("\nRiwayat Terakhir:")
        lines.append(hist)
        raw_info = "\n".join(lines)
        reply = humanize_client_info(client_name, raw_info)
        await update.message.reply_text(reply)
    else:
        # Fuzzy search for suggestions
        suggestions = search_clients(client_name, limit=5)
        if suggestions:
            suggestion_lines = "\n".join(f"  • {s}" for s in suggestions)
            await update.message.reply_text(
                f"❌ Nama klien '{client_name}' tidak ditemukan.\n\n"
                f"🔍 Mungkin yang Anda maksud:\n{suggestion_lines}\n\n"
                f"Coba /ask <salah satu nama di atas>"
            )
        else:
            await update.message.reply_text(
                f"❌ Nama klien '{client_name}' tidak ditemukan dan tidak ada yang mirip."
            )


def _build_data_context():
    """Build a data context string from available summaries and client memory."""
    parts = []

    # YTD summary
    try:
        ytd = summarize_year_to_date()
        parts.append("== RINGKASAN TAHUN BERJALAN ==")
        parts.append(ytd)
    except Exception as e:
        logger.warning("Could not fetch YTD summary for chat context: %s", e)

    # Client list from memory
    try:
        mem = load_memory()
        clients = mem.get("clients", {})
        if clients:
            parts.append("\n== DAFTAR KLIEN (dari memori) ==")
            for name, info in list(clients.items())[:50]:  # cap at 50
                addr = info.get("address", "-")
                device = info.get("device", "-")
                last_svc = info.get("last_service", "-")
                svc_type = info.get("service_type", "-")
                tech = info.get("technician", "-")
                parts.append(
                    f"- {name}: alamat={addr}, device={device}, "
                    f"last_service={last_svc}, type={svc_type}, tech={tech}"
                )
    except Exception as e:
        logger.warning("Could not load client memory for chat context: %s", e)

    return "\n".join(parts) if parts else "Tidak ada data operasional yang tersedia saat ini."


async def chat_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle free-text messages using AI with operational data context."""
    if not await check_auth(update):
        return

    user_message = update.message.text.strip()
    if not user_message:
        return

    logger.info("Chat message from %s: %s", update.effective_user.username, user_message)

    data_context = _build_data_context()
    reply = chat_with_data(user_message, data_context)
    await update.message.reply_text(reply)


async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle interactive button clicks."""
    query = update.callback_query
    await query.answer()

    if not await check_auth(update):
        return

    data = query.data
    logger.info("Button clicked: %s by %s", data, update.effective_user.username)

    if data == "summary":
        try:
            raw_summary = summarize_year_to_date()
            reply = humanize_summary(raw_summary)
            await query.message.reply_text(reply)
        except Exception as e:
            logger.exception("Error generating year-to-date summary via button")
            await query.message.reply_text(f"⚠️ Terjadi kesalahan saat membuat ringkasan:\n{e}")
    elif data == "summary_month":
        from datetime import datetime
        month_idx = datetime.now().month
        try:
            raw_summary = summarize_month(month_idx)
            reply = humanize_summary(raw_summary)
            await query.message.reply_text(reply)
        except Exception as e:
            logger.exception("Error generating monthly summary via button")
            await query.message.reply_text(f"⚠️ Gagal membuat ringkasan bulan {month_idx}:\n{e}")
    elif data == "sync":
        try:
            result = sync_memory()
            await query.message.reply_text(result)
        except Exception as e:
            logger.exception("Error syncing memory via button")
            await query.message.reply_text(f"⚠️ Gagal sinkronisasi:\n{e}")


# ── Main ─────────────────────────────────────────────────────────────

def main():
    application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("test_sheet", test_sheet))
    application.add_handler(CommandHandler("summary", summary_handler))
    application.add_handler(CommandHandler("sync", sync_handler))

    for i in range(1, 13):
        application.add_handler(CommandHandler(f"summary_{i}", monthly_summary_handler))

    application.add_handler(CommandHandler("ask", ask_handler))

    # Button click handler
    application.add_handler(CallbackQueryHandler(button_callback))

    # Free-text chat handler (must be last — catches everything not matched above)
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chat_handler))

    logger.info("NafasOps Bot starting...")
    application.run_polling()


if __name__ == "__main__":
    main()
