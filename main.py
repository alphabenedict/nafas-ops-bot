"""
NafasOps Platform — main entry point.

Runs concurrently:
  1. FastAPI web dashboard (Uvicorn)
  2. NafasOps Telegram bot (existing agent.py)
  3. All active tenant bots from the database
"""

import asyncio
import logging
import os

import uvicorn

from control.db.database import init_db
from control.bots.runner import start_nafas_bot, start_all_tenant_bots
from control.web.app import create_app

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


def _seed_nafasops_bot():
    """Register the NafasOps system bot in the platform DB if not already present."""
    from control.db.database import SessionLocal
    from control.db.models import Bot
    from config import TELEGRAM_TOKEN, SHEET_ID
    from datetime import datetime, timezone

    if not TELEGRAM_TOKEN:
        return

    db = SessionLocal()
    try:
        exists = db.query(Bot).filter(Bot.is_system == True).first()
        if not exists:
            born = datetime(2025, 6, 7, 13, 30, 1, tzinfo=timezone.utc)  # first commit date
            bot = Bot(
                owner_id=None,
                name="NafasOps Bot",
                telegram_token=TELEGRAM_TOKEN,
                role_description=(
                    "Bot operasional internal Nafas. Menjawab pertanyaan tentang data "
                    "layanan pelanggan, ringkasan operasional, dan informasi klien dari Google Sheets."
                ),
                personality="Profesional, ringkas, dan ramah. Menjawab dalam Bahasa Indonesia.",
                is_active=True,
                is_system=True,
                created_at=born,
                updated_at=born,
            )
            db.add(bot)
            db.commit()
            logger.info("NafasOps system bot seeded into platform DB")
    finally:
        db.close()


async def main():
    # Initialize database tables
    init_db()
    logger.info("Database initialized")
    try:
        _seed_nafasops_bot()
    except Exception as e:
        logger.warning("Seed failed (non-fatal, will retry next deploy): %s", e)

    web_app = create_app()

    port = int(os.getenv("PORT", "8000"))
    config = uvicorn.Config(web_app, host="0.0.0.0", port=port, log_level="info")
    server = uvicorn.Server(config)

    await asyncio.gather(
        server.serve(),
        start_nafas_bot(),
        start_all_tenant_bots(),
        return_exceptions=True,
    )


if __name__ == "__main__":
    asyncio.run(main())
