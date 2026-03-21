import logging
import json
import openai
import re
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
)
from ai_helpers import load_memory, get_client_memory
from config import TELEGRAM_TOKEN, OPENAI_API_KEY
from sheet_helpers import (
    fetch_sheet_dataframe,
    summarize_year_to_date,
    summarize_month
)

# Inisialisasi OpenAI
openai.api_key = OPENAI_API_KEY

# Setup logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_text = (
        "Halo! Saya NafasOps‐Bot. 👋\n\n"
        "Perintah yang tersedia:\n"
        "/start — Tampilkan pesan ini.\n"
        "/help — Daftar perintah.\n"
        "/test_sheet — Uji koneksi ke Google Sheet.\n"
        "/summary — Ringkasan Tahun 2026 s.d. sekarang.\n"
        "/summary_1 … /summary_12 — Ringkasan per bulan.\n"
        "/ask <nama client> — Tampilkan informasi klien.\n"
    )
    await update.message.reply_text(welcome_text)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = (
        "/start — Tampilkan pesan sambutan.\n"
        "/help — Tampilkan daftar perintah.\n"
        "/test_sheet — Uji koneksi ke Google Sheet.\n"
        "/summary — Ringkasan Tahun 2026 s.d. sekarang.\n"
        "/summary_1 … /summary_12 — Ringkasan per bulan Januari-Desember.\n"
        "/ask <nama client> — Tampilkan informasi klien.\n"
    )
    await update.message.reply_text(help_text)


async def test_sheet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        df = fetch_sheet_dataframe(worksheet_name="Sheet1")
        row_count = len(df)
        cols = df.columns.tolist()
        reply = f"✅ Sukses menarik data dari Google Sheet!\nJumlah baris: {row_count}\nKolom: {cols}"
    except Exception as e:
        reply = f"⚠️ Gagal menarik data dari Sheet:\n{e}"
    await update.message.reply_text(reply)


async def summary_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        summary_text = summarize_year_to_date()
        await update.message.reply_text(summary_text)
    except Exception as e:
        await update.message.reply_text(f"⚠️ Terjadi kesalahan saat membuat ringkasan:\n{e}")


async def monthly_summary_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
        summary_text = summarize_month(month_idx, year=2026)
        await update.message.reply_text(summary_text)
    except Exception as e:
        await update.message.reply_text(f"⚠️ Gagal membuat ringkasan bulan {month_idx}:\n{e}")


def format_history(history_list, limit=3):
    """
    Format maksimal `limit` entry terakhir dari history menjadi string.
    """
    if not history_list:
        return "Tidak ada riwayat tersedia."

    recent = history_list[-limit:]
    lines = []
    for item in recent:
        date     = item.get("date", "–")
        svc_type = item.get("type", "–")
        tech     = item.get("tech", "–")
        issue    = item.get("issue", "–")
        solu     = item.get("solution", "–")
        lines.append(f"- {date} | {svc_type} | {tech} | {issue} → {solu}")
    return "\n".join(lines)


async def ask_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    parts = text.split(" ", 1)
    if len(parts) < 2 or not parts[1].strip():
        await update.message.reply_text("Format salah. Gunakan: /ask <nama client>")
        return

    client_name = parts[1].strip()
    data = get_client_memory(client_name)
    if data:
        lines = [f"📋 *Memori untuk {client_name}:*"]
        lines.append(f"• Address      : {data.get('address', '–')}")
        lines.append(f"• Device       : {data.get('device', '–')}")
        lines.append(f"• Last Service : {data.get('last_service', '–')}")
        lines.append(f"• Service Type : {data.get('service_type', '–')}")
        lines.append(f"• Technician   : {data.get('technician', '–')}")
        # Sertakan 3 history terakhir
        hist = format_history(data.get("history", []), limit=3)
        lines.append("\n📜 *Riwayat Terakhir:*")
        lines.append(hist)
        reply = "\n".join(lines)
        await update.message.reply_text(reply, parse_mode="Markdown")
    else:
        await update.message.reply_text(
            f"❌ Nama klien '{client_name}' tidak ditemukan. Mungkin ada typo? Coba cek lagi."
        )


def main():
    application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("test_sheet", test_sheet))
    application.add_handler(CommandHandler("summary", summary_handler))

    for i in range(1, 13):
        application.add_handler(CommandHandler(f"summary_{i}", monthly_summary_handler))

    application.add_handler(CommandHandler("ask", ask_handler))

    application.run_polling()


if __name__ == "__main__":
    main()
