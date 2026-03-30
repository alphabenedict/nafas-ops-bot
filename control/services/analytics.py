"""Analytics queries for the dashboard."""

from sqlalchemy import func
from sqlalchemy.orm import Session

from control.db.models import Bot, Contact, Message, ConversationSummary


def get_bot_stats(db: Session, bot_id: str) -> dict:
    unique_contacts = db.query(func.count(Contact.id)).filter(Contact.bot_id == bot_id).scalar() or 0
    total_messages = db.query(func.count(Message.id)).filter(Message.bot_id == bot_id).scalar() or 0
    return {"unique_contacts": unique_contacts, "total_messages": total_messages}


def get_all_bots_stats(db: Session, owner_id: str) -> list:
    from sqlalchemy import or_
    bots = (
        db.query(Bot)
        .filter(or_(Bot.owner_id == owner_id, Bot.is_system == True))
        .order_by(Bot.is_system.desc(), Bot.created_at.desc())
        .all()
    )
    result = []
    for bot in bots:
        stats = get_bot_stats(db, bot.id)
        result.append({"bot": bot, **stats})
    return result


def get_contact_list(db: Session, bot_id: str, page: int = 1, per_page: int = 20) -> dict:
    query = db.query(Contact).filter(Contact.bot_id == bot_id).order_by(Contact.last_seen_at.desc())
    total = query.count()
    contacts = query.offset((page - 1) * per_page).limit(per_page).all()

    enriched = []
    for contact in contacts:
        msg_count = (
            db.query(func.count(Message.id)).filter(Message.contact_id == contact.id).scalar() or 0
        )
        enriched.append({"contact": contact, "message_count": msg_count})

    return {"contacts": enriched, "total": total, "page": page, "per_page": per_page}


def get_latest_summary(db: Session, contact_id: str) -> ConversationSummary | None:
    return (
        db.query(ConversationSummary)
        .filter(ConversationSummary.contact_id == contact_id)
        .order_by(ConversationSummary.generated_at.desc())
        .first()
    )


def get_conversation(db: Session, contact_id: str, limit: int = 100) -> list:
    return (
        db.query(Message)
        .filter(Message.contact_id == contact_id)
        .order_by(Message.created_at.asc())
        .limit(limit)
        .all()
    )
