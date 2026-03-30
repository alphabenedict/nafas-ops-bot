"""
Builds a PTB Application for a tenant bot from its DB configuration.
"""

import logging
import os

from telegram.ext import ApplicationBuilder, MessageHandler, filters

from control.bots.handlers import tenant_message_handler
from control.db.database import SessionLocal

logger = logging.getLogger(__name__)


def build_tenant_application(bot_row):
    """Build a configured Application for a tenant bot row."""
    app = ApplicationBuilder().token(bot_row.telegram_token).build()

    # Inject config and dependencies into bot_data (shared across all handlers)
    app.bot_data["config"] = bot_row
    app.bot_data["db_session_factory"] = SessionLocal
    app.bot_data["openai_api_key"] = os.getenv("OPENAI_API_KEY", "")

    # Register generic text handler
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, tenant_message_handler))

    logger.info("Built application for bot: %s (%s)", bot_row.name, bot_row.id)
    return app
