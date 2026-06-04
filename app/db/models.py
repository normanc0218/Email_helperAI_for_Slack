"""
SQLAlchemy models for the web app layer (Postgres).
"""
import datetime
from sqlalchemy import (
    Column, Integer, String, Text, DateTime, ForeignKey, Enum
)
from sqlalchemy.orm import relationship
from .database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    google_sub = Column(String(128), unique=True, nullable=False, index=True)
    email = Column(String(256), nullable=False)
    name = Column(String(256), nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)

    tokens = relationship("OAuthToken", back_populates="user", uselist=False)
    pending_actions = relationship("PendingAction", back_populates="user")
    memories = relationship("UserMemory", back_populates="user")
    agent_sessions = relationship("AgentSession", back_populates="user")


class OAuthToken(Base):
    __tablename__ = "oauth_tokens"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, unique=True)
    # Stored encrypted with Fernet (see app/auth/token_store.py)
    access_token_enc = Column(Text, nullable=False)
    refresh_token_enc = Column(Text, nullable=True)
    token_uri = Column(String(512), nullable=False)
    client_id = Column(String(256), nullable=False)
    client_secret_enc = Column(Text, nullable=False)
    scopes = Column(Text, nullable=False)          # space-separated
    expires_at = Column(DateTime, nullable=True)
    updated_at = Column(
        DateTime,
        default=datetime.datetime.utcnow,
        onupdate=datetime.datetime.utcnow,
        nullable=False,
    )

    user = relationship("User", back_populates="tokens")


class PendingAction(Base):
    __tablename__ = "pending_actions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    action_type = Column(
        Enum("archive", "label", "unarchive", name="action_type_enum"),
        nullable=False,
    )
    email_id = Column(String(256), nullable=False)
    email_subject = Column(String(512), nullable=True)
    email_from = Column(String(256), nullable=True)
    label = Column(String(256), nullable=True)    # for label actions
    status = Column(
        Enum("pending", "approved", "rejected", name="pending_status_enum"),
        default="pending",
        nullable=False,
        index=True,
    )
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    resolved_at = Column(DateTime, nullable=True)

    user = relationship("User", back_populates="pending_actions")


class UserMemory(Base):
    """Long-term memory entries for each user — persists across sessions."""
    __tablename__ = "user_memories"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    memory_type = Column(
        Enum("preference", "summary", "entity", "conversation", name="memory_type_enum"),
        nullable=False,
        index=True,
    )
    key = Column(String(256), nullable=False)      # e.g. "newsletter_handling", "2026-06-03"
    value = Column(Text, nullable=False)            # free-form text or JSON string
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime,
        default=datetime.datetime.utcnow,
        onupdate=datetime.datetime.utcnow,
        nullable=False,
    )

    user = relationship("User", back_populates="memories")


class AgentSession(Base):
    """Persisted ADK session state — survives server restarts."""
    __tablename__ = "agent_sessions"

    id = Column(String(64), primary_key=True)       # ADK session_id
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    app_name = Column(String(128), nullable=False)
    state = Column(Text, nullable=False, default="{}")  # JSON-serialised state dict
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime,
        default=datetime.datetime.utcnow,
        onupdate=datetime.datetime.utcnow,
        nullable=False,
    )

    user = relationship("User", back_populates="agent_sessions")
