"""
Postgres-backed ADK SessionService.

Replaces InMemorySessionService so agent sessions survive server restarts.
Session state (user_id, dry_run, interaction_history, etc.) is serialised
as JSON and stored in the agent_sessions table.
"""
import json
import logging
import uuid
from typing import Any, Optional

from google.adk.sessions import BaseSessionService, Session
from google.adk.sessions.base_session_service import ListSessionsResponse
from google.adk.events import Event

logger = logging.getLogger(__name__)


class PostgresSessionService(BaseSessionService):
    """ADK SessionService backed by Postgres agent_sessions table."""

    # ── Create ────────────────────────────────────────────────────────────────

    async def create_session(
        self,
        *,
        app_name: str,
        user_id: str,
        state: Optional[dict[str, Any]] = None,
        session_id: Optional[str] = None,
    ) -> Session:
        from app.db.database import SessionLocal
        from app.db.models import AgentSession

        sid = session_id or str(uuid.uuid4())
        db = SessionLocal()
        try:
            row = AgentSession(
                id=sid,
                user_id=int(user_id),
                app_name=app_name,
                state=json.dumps(state or {}),
            )
            db.add(row)
            db.commit()
        finally:
            db.close()

        return Session(
            id=sid,
            app_name=app_name,
            user_id=user_id,
            state=state or {},
            events=[],
        )

    # ── Get ───────────────────────────────────────────────────────────────────

    async def get_session(
        self,
        *,
        app_name: str,
        user_id: str,
        session_id: str,
        config=None,
    ) -> Optional[Session]:
        from app.db.database import SessionLocal
        from app.db.models import AgentSession

        db = SessionLocal()
        try:
            row = db.query(AgentSession).filter(
                AgentSession.id == session_id,
                AgentSession.app_name == app_name,
            ).first()
        finally:
            db.close()

        if row is None:
            return None

        return Session(
            id=row.id,
            app_name=row.app_name,
            user_id=str(row.user_id),
            state=json.loads(row.state or "{}"),
            events=[],
        )

    # ── List ──────────────────────────────────────────────────────────────────

    async def list_sessions(
        self,
        *,
        app_name: str,
        user_id: Optional[str] = None,
    ) -> ListSessionsResponse:
        from app.db.database import SessionLocal
        from app.db.models import AgentSession

        db = SessionLocal()
        try:
            q = db.query(AgentSession).filter(AgentSession.app_name == app_name)
            if user_id is not None:
                q = q.filter(AgentSession.user_id == int(user_id))
            rows = q.order_by(AgentSession.updated_at.desc()).all()
        finally:
            db.close()

        sessions = [
            Session(
                id=r.id,
                app_name=r.app_name,
                user_id=str(r.user_id),
                state=json.loads(r.state or "{}"),
                events=[],
            )
            for r in rows
        ]
        return ListSessionsResponse(sessions=sessions)

    # ── Update (state patch before run) ──────────────────────────────────────

    async def update_session(self, session: Session) -> None:
        """Persist the current in-memory session state to Postgres immediately."""
        self._persist_state(session)

    # ── Delete ────────────────────────────────────────────────────────────────

    async def delete_session(
        self, *, app_name: str, user_id: str, session_id: str
    ) -> None:
        from app.db.database import SessionLocal
        from app.db.models import AgentSession

        db = SessionLocal()
        try:
            db.query(AgentSession).filter(AgentSession.id == session_id).delete()
            db.commit()
        finally:
            db.close()

    # ── Append event (persist state delta) ───────────────────────────────────

    async def append_event(self, session: Session, event: Event) -> Event:
        """Persist state changes after each agent event."""
        event = await super().append_event(session, event)

        # Only persist if this event carried a state change
        if event.actions and event.actions.state_delta:
            self._persist_state(session)

        return event

    def _persist_state(self, session: Session) -> None:
        from app.db.database import SessionLocal
        from app.db.models import AgentSession

        db = SessionLocal()
        try:
            row = db.query(AgentSession).filter(AgentSession.id == session.id).first()
            if row:
                row.state = json.dumps(session.state)
                db.commit()
        except Exception as e:
            logger.warning("Failed to persist session state: %s", e)
        finally:
            db.close()
