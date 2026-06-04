"""
Postgres database connection for the web app layer.

The existing agent_service/email_agent/database.py (SQLite) is kept
for the action_log table used by the ADK agents. This module handles
the new web-app tables: User, OAuthToken, PendingAction.
"""
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://emailagent:emailagent@localhost:5432/emailagent"
)

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_pg_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_pg_db():
    from .models import User, OAuthToken, PendingAction  # noqa: F401
    Base.metadata.create_all(bind=engine)
