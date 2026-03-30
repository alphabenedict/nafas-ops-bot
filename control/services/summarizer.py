"""Per-contact AI conversation summarizer."""

import logging

from sqlalchemy.orm import Session

from control.db.models import Message, ConversationSummary

logger = logging.getLogger(__name__)

SUMMARY_PROMPT = (
    "Buat ringkasan singkat dari percakapan berikut antara user dan bot. "
    "Sebutkan topik utama yang dibahas, pertanyaan utama user, dan solusi atau "
    "informasi yang diberikan bot. Maksimal 3 paragraf singkat. Gunakan Bahasa Indonesia."
)


async def generate_contact_summary(
    db: Session, contact_id: str, bot_id: str, api_key: str, msg_count: int
):
    messages = (
        db.query(Message)
        .filter(Message.contact_id == contact_id)
        .order_by(Message.created_at.asc())
        .limit(50)
        .all()
    )
    if not messages:
        return

    conversation_text = "\n".join(
        f"{'User' if m.direction == 'inbound' else 'Bot'}: {m.text}" for m in messages
    )

    try:
        from openai import AsyncOpenAI
        client = AsyncOpenAI(api_key=api_key)
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": SUMMARY_PROMPT},
                {"role": "user", "content": conversation_text},
            ],
            max_tokens=512,
        )
        summary_text = response.choices[0].message.content.strip()
    except Exception:
        logger.exception("Failed to generate summary for contact %s", contact_id)
        return

    existing = (
        db.query(ConversationSummary)
        .filter(
            ConversationSummary.contact_id == contact_id,
            ConversationSummary.bot_id == bot_id,
        )
        .order_by(ConversationSummary.generated_at.desc())
        .first()
    )

    if existing:
        existing.summary_text = summary_text
        existing.message_count = msg_count
        from datetime import datetime, timezone
        existing.generated_at = datetime.now(timezone.utc)
    else:
        summary = ConversationSummary(
            contact_id=contact_id,
            bot_id=bot_id,
            summary_text=summary_text,
            message_count=msg_count,
        )
        db.add(summary)

    db.commit()
    logger.info("Summary generated for contact %s", contact_id)
