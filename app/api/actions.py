"""
Pending action approval/rejection endpoints.

Phase 4: write operations (archive, label) are staged as PendingAction rows.
The user approves or rejects them here; only on approval is the Gmail API called.
"""
import datetime
import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth.session import get_current_user
from app.db.database import get_pg_db
from app.db.models import PendingAction, User

router = APIRouter(prefix="/api/actions", tags=["actions"])
logger = logging.getLogger(__name__)


@router.get("/pending")
def list_pending(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_pg_db),
):
    """Return all pending actions awaiting user approval."""
    actions = (
        db.query(PendingAction)
        .filter(
            PendingAction.user_id == current_user.id,
            PendingAction.status == "pending",
        )
        .order_by(PendingAction.created_at.asc())
        .all()
    )
    return [_serialize(a) for a in actions]


@router.post("/{action_id}/approve")
def approve_action(
    action_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_pg_db),
):
    """Approve a pending action: execute the Gmail API call and record in ActionLog."""
    action = _get_action(action_id, current_user, db)

    try:
        _execute_action(action, current_user, db)
    except Exception as exc:
        logger.error("Failed to execute action %s: %s", action_id, exc)
        raise HTTPException(status_code=502, detail=f"Gmail API error: {exc}")

    action.status = "approved"
    action.resolved_at = datetime.datetime.utcnow()
    db.commit()
    return {"status": "approved", "action_id": action_id}


@router.post("/{action_id}/reject")
def reject_action(
    action_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_pg_db),
):
    """Reject a pending action without touching Gmail."""
    action = _get_action(action_id, current_user, db)
    action.status = "rejected"
    action.resolved_at = datetime.datetime.utcnow()
    db.commit()
    return {"status": "rejected", "action_id": action_id}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_action(action_id: int, user: User, db: Session) -> PendingAction:
    action = (
        db.query(PendingAction)
        .filter(PendingAction.id == action_id, PendingAction.user_id == user.id)
        .first()
    )
    if action is None:
        raise HTTPException(status_code=404, detail="Action not found")
    if action.status != "pending":
        raise HTTPException(status_code=409, detail=f"Action already {action.status}")
    return action


def _execute_action(action: PendingAction, user: User, db: Session):
    """Call the Gmail API to carry out the approved action."""
    from agent_service.email_agent.services.email_provider import get_provider
    from agent_service.email_agent.models.action_log import ActionLog
    from agent_service.email_agent.database import SessionLocal as SqliteSession

    provider = get_provider()

    if action.action_type == "archive":
        ok = provider.archive_email(action.email_id)
        log_action = "archive"
    elif action.action_type == "label":
        ok = provider.label_email(action.email_id, action.label or "Inbox")
        log_action = "label"
    else:
        raise ValueError(f"Unknown action_type: {action.action_type}")

    if not ok:
        raise RuntimeError("Gmail API returned failure")

    # Write to the SQLite ActionLog so undo still works
    sqlite_db = SqliteSession()
    try:
        log_entry = ActionLog(
            user=user.email,
            action=log_action,
            email_id=action.email_id,
            email_subject=action.email_subject,
            label=action.label,
            status="done",
        )
        sqlite_db.add(log_entry)
        sqlite_db.commit()
    finally:
        sqlite_db.close()


def _serialize(a: PendingAction) -> dict:
    return {
        "id": a.id,
        "action_type": a.action_type,
        "email_id": a.email_id,
        "email_subject": a.email_subject,
        "email_from": a.email_from,
        "label": a.label,
        "status": a.status,
        "created_at": a.created_at.isoformat(),
    }
