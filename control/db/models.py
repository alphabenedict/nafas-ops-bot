import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean, Column, DateTime, ForeignKey, Integer, String, Text, BigInteger, UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, relationship


def _now():
    return datetime.now(timezone.utc)


def _uuid():
    return str(uuid.uuid4())


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=_uuid)
    email = Column(String(255), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    is_admin = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=_now, nullable=False)

    bots = relationship("Bot", back_populates="owner", cascade="all, delete-orphan")


class Bot(Base):
    __tablename__ = "bots"

    id = Column(String(36), primary_key=True, default=_uuid)
    owner_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=True)
    name = Column(String(255), nullable=False)
    telegram_token = Column(String(512), nullable=False, unique=True)
    role_description = Column(Text, default="", nullable=False)
    personality = Column(Text, default="", nullable=False)
    is_active = Column(Boolean, default=False, nullable=False)
    is_system = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=_now, nullable=False)
    updated_at = Column(DateTime, default=_now, onupdate=_now, nullable=False)

    owner = relationship("User", back_populates="bots")
    knowledge_chunks = relationship("KnowledgeChunk", back_populates="bot", cascade="all, delete-orphan")
    contacts = relationship("Contact", back_populates="bot", cascade="all, delete-orphan")


class KnowledgeChunk(Base):
    __tablename__ = "knowledge_chunks"

    id = Column(String(36), primary_key=True, default=_uuid)
    bot_id = Column(String(36), ForeignKey("bots.id", ondelete="CASCADE"), nullable=False)
    source_name = Column(String(255), nullable=False)
    chunk_text = Column(Text, nullable=False)
    chunk_index = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, default=_now, nullable=False)

    bot = relationship("Bot", back_populates="knowledge_chunks")


class Contact(Base):
    __tablename__ = "contacts"
    __table_args__ = (UniqueConstraint("bot_id", "telegram_id", name="uq_bot_contact"),)

    id = Column(String(36), primary_key=True, default=_uuid)
    bot_id = Column(String(36), ForeignKey("bots.id", ondelete="CASCADE"), nullable=False)
    telegram_id = Column(BigInteger, nullable=False)
    username = Column(String(255), nullable=True)
    first_name = Column(String(255), nullable=True)
    last_name = Column(String(255), nullable=True)
    first_seen_at = Column(DateTime, default=_now, nullable=False)
    last_seen_at = Column(DateTime, default=_now, nullable=False)

    bot = relationship("Bot", back_populates="contacts")
    messages = relationship("Message", back_populates="contact", cascade="all, delete-orphan")
    summaries = relationship(
        "ConversationSummary", back_populates="contact", cascade="all, delete-orphan"
    )


class Message(Base):
    __tablename__ = "messages"

    id = Column(String(36), primary_key=True, default=_uuid)
    contact_id = Column(String(36), ForeignKey("contacts.id", ondelete="CASCADE"), nullable=False)
    bot_id = Column(String(36), ForeignKey("bots.id", ondelete="CASCADE"), nullable=False)
    direction = Column(String(10), nullable=False)  # "inbound" | "outbound"
    text = Column(Text, nullable=False)
    created_at = Column(DateTime, default=_now, nullable=False)

    contact = relationship("Contact", back_populates="messages")


class ConversationSummary(Base):
    __tablename__ = "conversation_summaries"

    id = Column(String(36), primary_key=True, default=_uuid)
    contact_id = Column(String(36), ForeignKey("contacts.id", ondelete="CASCADE"), nullable=False)
    bot_id = Column(String(36), ForeignKey("bots.id", ondelete="CASCADE"), nullable=False)
    summary_text = Column(Text, nullable=False)
    generated_at = Column(DateTime, default=_now, nullable=False)
    message_count = Column(Integer, nullable=False, default=0)

    contact = relationship("Contact", back_populates="summaries")
