"""
FastAPI server entry point.

Start with:  uvicorn app.server:api --reload --port 8000
"""
import logging
import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from agent_service.email_agent.database import init_db
from .routers.gmail_push import router as gmail_push_router
from .util import router as util_router
from .auth.oauth import router as auth_router
from .api.chat import router as chat_router
from .api.actions import router as actions_router

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(name)s  %(message)s")
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # SQLite ActionLog (used by ADK agents)
    init_db()
    logger.info("SQLite action_logs initialised.")

    # Postgres tables (User, OAuthToken, PendingAction)
    try:
        from app.db.database import init_pg_db
        init_pg_db()
        logger.info("Postgres tables initialised.")
    except Exception as exc:
        logger.warning("Postgres init skipped (DATABASE_URL not set or unavailable): %s", exc)

    # Gmail Pub/Sub watch renewal
    try:
        from agent_service.email_agent.services.gmail_watch_service import renew_if_needed
        renew_if_needed()
    except Exception as exc:
        logger.warning("Gmail watch registration skipped: %s", exc)

    yield


api = FastAPI(title="Email Agent", version="0.4.0", lifespan=lifespan)

# ── CORS ──────────────────────────────────────────────────────────────────────
# Allow the Chrome extension (chrome-extension://*) and any localhost dev origins.
# In production, set CORS_ALLOWED_ORIGINS to your specific extension ID.
_raw_origins = os.getenv(
    "CORS_ALLOWED_ORIGINS",
    "http://localhost:5173,http://localhost:3000"
)
_origins = [o.strip() for o in _raw_origins.split(",") if o.strip()]

api.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_origin_regex=r"chrome-extension://.*",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────────────────────────
api.include_router(auth_router)        # /auth/* (new multi-user OAuth)
api.include_router(chat_router)        # /api/chat, /api/me, /api/emails/stats
api.include_router(actions_router)     # /api/actions/*
api.include_router(gmail_push_router)  # /gmail/push
api.include_router(util_router)        # /health, /logs, /groups, /metrics

# Slack router is optional — only loaded when SLACK_BOT_TOKEN is set
if os.getenv("SLACK_BOT_TOKEN"):
    from .routers.slack import router as slack_router
    api.include_router(slack_router)
    logger.info("Slack integration enabled.")
