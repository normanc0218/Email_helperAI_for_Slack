"""
Per-user ADK agent runner with SSE streaming output, long-term memory, and
Postgres-persisted sessions.

Memory architecture:
  Short-term: PostgresSessionService  → session state survives restarts
  Long-term:  UserMemory (Postgres)   → preferences, summaries, entities
              injected into the agent prompt at the start of each run,
              extracted and saved at the end of each run.
"""
import asyncio
import json
import logging
import os
from typing import AsyncGenerator

from google.adk.runners import Runner
from google.genai import types

from app.agent.pg_session_service import PostgresSessionService

logger = logging.getLogger(__name__)

APP_NAME = "email_agent_web"

# One session service shared across all requests
_session_service = PostgresSessionService()

_runner: Runner | None = None


def _get_runner() -> Runner:
    global _runner
    if _runner is None:
        from agent_service.email_agent import root_agent
        _runner = Runner(
            agent=root_agent,
            app_name=APP_NAME,
            session_service=_session_service,
        )
    return _runner


def _make_initial_state(user_id: str, dry_run: bool, pg_user_id: int | None = None) -> dict:
    return {
        "user_id": user_id,
        "user_name": "",
        "dry_run": dry_run,
        "pg_user_id": pg_user_id,
        "interaction_history": [],
        "last_sync_time": None,
        "emails_processed_total": 0,
    }


async def _get_or_create_session(
    user_id: str, dry_run: bool, pg_user_id: int | None = None
) -> str:
    existing = await _session_service.list_sessions(
        app_name=APP_NAME, user_id=user_id
    )
    if existing and existing.sessions:
        return existing.sessions[0].id

    session = await _session_service.create_session(
        app_name=APP_NAME,
        user_id=user_id,
        state=_make_initial_state(user_id, dry_run, pg_user_id),
    )
    return session.id


async def _fetch_project_md(project_name: str, pg_user_id: int | None) -> str:
    """Return a short markdown summary for the named project group from Firestore."""
    try:
        from agent_service.email_agent.services.firestore_service import list_groups
        user_id_str = str(pg_user_id) if pg_user_id is not None else "cli"
        groups = list_groups(user_id_str)
        name_lower = project_name.lower()
        match = next((g for g in groups if name_lower in g.get("name", "").lower()), None)
        if not match:
            return f"Project: {project_name}"
        summary = match.get("summary", "No summary yet.")
        count = match.get("email_count", 0)
        return f"**{match['name']}** ({count} emails)\n{summary}"
    except Exception:
        return f"Project: {project_name}"


async def run_agent_stream(
    user_id: str,
    message: str,
    dry_run: bool = False,
    pg_user_id: int | None = None,
    job_type: str = "CASUAL",
    project_name: str | None = None,
) -> AsyncGenerator[str, None]:
    """
    Run the ADK agent for a given user and yield SSE-formatted event strings.

    Flow:
      1. Load long-term memories from Postgres → prepend to message
      2. Run ADK agent, stream events
      3. Collect full conversation text
      4. Extract and save new memories (async, non-blocking)
    """
    runner = _get_runner()
    session_id = await _get_or_create_session(user_id, dry_run, pg_user_id)

    # ── 0. Patch session state with routing context ───────────────────────────
    session = await _session_service.get_session(
        app_name=APP_NAME, user_id=user_id, session_id=session_id
    )
    if session:
        session.state["job_type"] = job_type
        if project_name:
            session.state["project_md"] = await _fetch_project_md(project_name, pg_user_id)
        elif "project_md" in session.state and job_type != "PROJECT_CHAT":
            # Clear stale project context when leaving project chat
            session.state.pop("project_md", None)
        await _session_service.update_session(session)

    # ── 1. Load long-term memory and inject into prompt ───────────────────────
    memory_prefix = ""
    if pg_user_id is not None:
        try:
            from app.db.database import SessionLocal
            from app.agent.memory import load_memory_context
            db = SessionLocal()
            try:
                memory_prefix = load_memory_context(db, pg_user_id)
            finally:
                db.close()
        except Exception as e:
            logger.warning("Failed to load memories: %s", e)

    augmented_message = f"{memory_prefix}\n\n{message}" if memory_prefix else message

    def _sse(payload: dict) -> str:
        return f"data: {json.dumps(payload)}\n\n"

    # ── 2. Run agent, collect conversation for memory extraction ──────────────
    conversation_parts: list[str] = [f"User: {message}"]

    try:
        async for event in runner.run_async(
            user_id=user_id,
            session_id=session_id,
            new_message=types.Content(
                role="user",
                parts=[types.Part(text=augmented_message)],
            ),
        ):
            if not event.content or not event.content.parts:
                continue

            for part in event.content.parts:
                if hasattr(part, "function_call") and part.function_call:
                    yield _sse({
                        "type": "tool_call",
                        "name": part.function_call.name,
                        "args": dict(part.function_call.args or {}),
                    })
                elif hasattr(part, "function_response") and part.function_response:
                    preview = str(part.function_response.response or "")[:300]
                    yield _sse({
                        "type": "tool_result",
                        "name": part.function_response.name,
                        "preview": preview,
                    })
                elif hasattr(part, "text") and part.text and event.is_final_response():
                    yield _sse({"type": "text", "content": part.text})
                    conversation_parts.append(f"Agent: {part.text}")

        yield _sse({"type": "done"})

    except asyncio.CancelledError:
        yield _sse({"type": "done"})
        return
    except Exception as exc:
        logger.exception("Agent error for user %s: %s", user_id, exc)
        yield _sse({"type": "error", "message": str(exc)})
        yield _sse({"type": "done"})
        return

    # ── 3. Extract and save memories (fire-and-forget, won't block SSE) ───────
    if pg_user_id is not None and len(conversation_parts) > 1:
        conversation_text = "\n".join(conversation_parts)
        asyncio.create_task(_save_memories(pg_user_id, conversation_text))


async def _save_memories(pg_user_id: int, conversation_text: str) -> None:
    """Background task: extract facts from conversation and store in Postgres."""
    try:
        from app.db.database import SessionLocal
        from app.agent.memory import extract_and_save
        db = SessionLocal()
        try:
            n = extract_and_save(db, pg_user_id, conversation_text)
            if n:
                logger.info("Saved %d memories for user %s", n, pg_user_id)
        finally:
            db.close()
    except Exception as e:
        logger.warning("Background memory save failed: %s", e)
