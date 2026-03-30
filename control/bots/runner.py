"""
Multi-bot async runner.

Uses PTB v20's async context manager API to run multiple Telegram bots
concurrently within one asyncio event loop — avoiding run_polling() which
calls asyncio.run() internally.
"""

import asyncio
import logging
from typing import Dict, Tuple

from telegram.ext import Application

logger = logging.getLogger(__name__)

# bot_id (str) -> (Application, asyncio.Task)
_running: Dict[str, Tuple[Application, asyncio.Task]] = {}


async def _run_bot_lifecycle(app: Application, label: str = "bot"):
    """Run a PTB Application using the async lifecycle API."""
    async with app:
        await app.initialize()
        await app.updater.start_polling(drop_pending_updates=True)
        await app.start()
        logger.info("[%s] polling started", label)
        try:
            await asyncio.Event().wait()  # yield forever
        finally:
            logger.info("[%s] shutting down", label)
            await app.updater.stop()
            await app.stop()
            await app.shutdown()


async def start_nafas_bot():
    """Start the existing NafasOps bot as an async task."""
    from agent import build_application
    app = build_application()
    await _run_bot_lifecycle(app, label="NafasOps")


async def start_all_tenant_bots():
    """Load all active bots from DB and start them."""
    from control.db.database import SessionLocal
    from control.db.models import Bot

    db = SessionLocal()
    try:
        active_bots = db.query(Bot).filter(Bot.is_active == True).all()
    finally:
        db.close()

    tasks = [start_tenant_bot_by_id(bot.id) for bot in active_bots]
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)
    else:
        # Nothing active yet — just stay alive waiting for new bots via the dashboard
        await asyncio.Event().wait()


async def start_tenant_bot_by_id(bot_id: str):
    """Start a single tenant bot and register its task."""
    if bot_id in _running:
        logger.warning("Bot %s is already running", bot_id)
        return

    from control.db.database import SessionLocal
    from control.db.models import Bot
    from control.bots.factory import build_tenant_application

    db = SessionLocal()
    try:
        bot_row = db.query(Bot).filter(Bot.id == bot_id).first()
        if not bot_row:
            logger.error("Bot %s not found in DB", bot_id)
            return
        app = build_tenant_application(bot_row)
    finally:
        db.close()

    task = asyncio.create_task(
        _run_bot_lifecycle(app, label=f"tenant:{bot_row.name}"),
        name=f"bot_{bot_id}",
    )
    _running[bot_id] = (app, task)
    logger.info("Started tenant bot %s (%s)", bot_id, bot_row.name)


async def stop_tenant_bot_by_id(bot_id: str):
    """Stop a running tenant bot."""
    entry = _running.pop(bot_id, None)
    if not entry:
        logger.warning("Bot %s is not running", bot_id)
        return
    _app, task = entry
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    logger.info("Stopped tenant bot %s", bot_id)


def is_running(bot_id: str) -> bool:
    return bot_id in _running
