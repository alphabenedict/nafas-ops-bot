"""
Generic Telegram message handlers for all tenant bots.

Each tenant bot shares these handlers; bot-specific config and DB session factory
are injected via context.bot_data at Application build time.
"""

import asyncio
import logging
from datetime import datetime, timezone

from telegram import Update
from telegram.ext import ContextTypes

from control.db.models import Contact, Message

logger = logging.getLogger(__name__)

SUMMARY_TRIGGER_EVERY = 10  # generate/refresh summary every N messages


def _now():
    return datetime.now(timezone.utc)


def _upsert_contact(db, bot_id: str, tg_user) -> Contact:
    contact = (
        db.query(Contact)
        .filter(Contact.bot_id == bot_id, Contact.telegram_id == tg_user.id)
        .first()
    )
    if not contact:
        contact = Contact(
            bot_id=bot_id,
            telegram_id=tg_user.id,
            username=tg_user.username,
            first_name=tg_user.first_name,
            last_name=tg_user.last_name,
        )
        db.add(contact)
        db.flush()
    else:
        contact.last_seen_at = _now()
        if tg_user.username:
            contact.username = tg_user.username
    db.commit()
    return contact


def _store_message(db, contact_id: str, bot_id: str, direction: str, text: str) -> Message:
    msg = Message(contact_id=contact_id, bot_id=bot_id, direction=direction, text=text)
    db.add(msg)
    db.commit()
    return msg


async def _call_openai(system_prompt: str, user_text: str, api_key: str) -> str:
    from openai import AsyncOpenAI
    client = AsyncOpenAI(api_key=api_key)
    response = await client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_text},
        ],
        max_tokens=1024,
    )
    return response.choices[0].message.content.strip()


async def tenant_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Main handler for all incoming text messages on a tenant bot."""
    if not update.message or not update.message.text:
        return

    bot_config = context.bot_data.get("config")
    session_factory = context.bot_data.get("db_session_factory")
    api_key = context.bot_data.get("openai_api_key")

    if not bot_config or not session_factory:
        logger.error("Bot config or session factory missing from bot_data")
        return

    db = session_factory()
    try:
        tg_user = update.effective_user
        user_text = update.message.text.strip()

        # 1. Upsert contact
        contact = _upsert_contact(db, bot_config.id, tg_user)

        # 2. Store inbound message
        _store_message(db, contact.id, bot_config.id, "inbound", user_text)

        # 3. RAG knowledge lookup
        from control.bots.rag import search_knowledge
        knowledge_ctx = search_knowledge(db, bot_config.id, user_text)

        # 4. Build system prompt
        system_prompt = build_system_prompt(bot_config, knowledge_ctx)

        # 5. Call OpenAI
        try:
            reply_text = await _call_openai(system_prompt, user_text, api_key)
        except Exception as e:
            logger.exception("OpenAI call failed for bot %s", bot_config.id)
            reply_text = "Maaf, terjadi kesalahan. Silakan coba lagi."

        # 6. Store outbound message
        _store_message(db, contact.id, bot_config.id, "outbound", reply_text)

        # 7. Send reply
        await update.message.reply_text(reply_text)

        # 8. Trigger summary generation in background (non-blocking)
        msg_count = db.query(Message).filter(Message.contact_id == contact.id).count()
        if msg_count % SUMMARY_TRIGGER_EVERY == 0:
            contact_id = contact.id
            asyncio.create_task(
                _generate_summary_bg(contact_id, bot_config.id, api_key, msg_count)
            )

    except Exception:
        logger.exception("Error in tenant_message_handler for bot %s", bot_config.id if bot_config else "?")
    finally:
        db.close()


def build_system_prompt(bot_config, knowledge_ctx: str) -> str:
    parts = []
    if bot_config.role_description:
        parts.append(bot_config.role_description)
    if bot_config.personality:
        parts.append(bot_config.personality)
    if knowledge_ctx:
        parts.append(f"\n\nKnowledge base yang tersedia:\n{knowledge_ctx}")
    parts.append("\nJawab hanya berdasarkan informasi yang tersedia. Jangan mengarang data.")
    return "\n\n".join(parts)


async def _generate_summary_bg(contact_id: str, bot_id: str, api_key: str, msg_count: int):
    """Background task: generate and store a conversation summary."""
    from control.services.summarizer import generate_contact_summary
    from control.db.database import SessionLocal
    db = SessionLocal()
    try:
        await generate_contact_summary(db, contact_id, bot_id, api_key, msg_count)
    except Exception:
        logger.exception("Background summary generation failed for contact %s", contact_id)
    finally:
        db.close()
