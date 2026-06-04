"""
POST /api/chat — SSE streaming chat endpoint.
Authenticated users send a message; the ADK agent streams back events.
"""
import os
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.auth.session import get_current_user
from app.db.database import get_pg_db
from app.db.models import User

router = APIRouter(prefix="/api", tags=["chat"])


class ChatRequest(BaseModel):
    message: str
    job_type: str = "CASUAL"         # "ORGANIZE" | "DIGEST" | "UNDO" | "QUERY" | "PROJECT_CHAT" | "CASUAL"
    project_name: str | None = None  # set by frontend when user opens a project panel


@router.post("/chat")
async def chat(
    req: ChatRequest,
    current_user: User = Depends(get_current_user),
):
    """Stream ADK agent responses for the authenticated user."""
    from app.agent.runner import run_agent_stream

    dry_run = os.getenv("DRY_RUN", "true").lower() == "true"
    user_id = str(current_user.id)

    return StreamingResponse(
        run_agent_stream(
            user_id, req.message,
            dry_run=dry_run, pg_user_id=current_user.id,
            job_type=req.job_type, project_name=req.project_name,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/me")
def get_me(current_user: User = Depends(get_current_user)):
    """Return the authenticated user's profile."""
    return {
        "user": {
            "id": current_user.id,
            "email": current_user.email,
            "name": current_user.name,
        }
    }


@router.get("/emails/stats")
def get_email_stats(current_user: User = Depends(get_current_user)):
    """Return inbox stats for the authenticated user (read-only)."""
    from agent_service.email_agent.tools.inbox_query_tools import get_inbox_stats
    return get_inbox_stats()


@router.get("/memories")
def get_memories(
    current_user: User = Depends(get_current_user),
    db=Depends(get_pg_db),
):
    """Return the current user's long-term memories."""
    from app.db.models import UserMemory
    rows = (
        db.query(UserMemory)
        .filter(UserMemory.user_id == current_user.id)
        .order_by(UserMemory.updated_at.desc())
        .all()
    )
    return [
        {
            "id": r.id,
            "type": r.memory_type,
            "key": r.key,
            "value": r.value,
            "updated_at": r.updated_at.isoformat(),
        }
        for r in rows
    ]


@router.delete("/memories/{memory_id}")
def delete_memory(
    memory_id: int,
    current_user: User = Depends(get_current_user),
    db=Depends(get_pg_db),
):
    """Delete a specific memory entry."""
    from app.db.models import UserMemory
    from fastapi import HTTPException
    row = db.query(UserMemory).filter(
        UserMemory.id == memory_id,
        UserMemory.user_id == current_user.id,
    ).first()
    if not row:
        raise HTTPException(status_code=404, detail="Memory not found")
    db.delete(row)
    db.commit()
    return {"status": "deleted", "id": memory_id}
