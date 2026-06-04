"""
Long-term memory for the email agent.

Two operations:
  load_memory_context(pg_user_id)  → formatted string injected into agent prompt
  extract_and_save(pg_user_id, conversation_text)  → GPT-4o-mini extracts facts → Postgres
"""
import json
import logging
import os
from datetime import datetime

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

# Max number of memories to inject per type (keep prompt lean)
_MAX_PREFERENCES = 10
_MAX_SUMMARIES = 5
_MAX_ENTITIES = 20


# ── Read ──────────────────────────────────────────────────────────────────────

def load_memory_context(db: Session, pg_user_id: int) -> str:
    """Return a formatted memory block to prepend to the agent's system prompt.

    Returns an empty string if there are no memories yet.
    """
    from app.db.models import UserMemory

    rows = (
        db.query(UserMemory)
        .filter(UserMemory.user_id == pg_user_id)
        .order_by(UserMemory.updated_at.desc())
        .all()
    )
    if not rows:
        return ""

    prefs = [r for r in rows if r.memory_type == "preference"][:_MAX_PREFERENCES]
    summaries = [r for r in rows if r.memory_type == "summary"][:_MAX_SUMMARIES]
    entities = [r for r in rows if r.memory_type == "entity"][:_MAX_ENTITIES]

    parts = ["## User Memory (from past sessions)"]

    if prefs:
        parts.append("\n### Preferences")
        for r in prefs:
            parts.append(f"- {r.key}: {r.value}")

    if summaries:
        parts.append("\n### Recent Activity Summaries")
        for r in summaries:
            parts.append(f"- [{r.key}] {r.value}")

    if entities:
        parts.append("\n### Known Senders / Entities")
        for r in entities:
            parts.append(f"- {r.key}: {r.value}")

    parts.append("\n---")
    return "\n".join(parts)


# ── Write ─────────────────────────────────────────────────────────────────────

def extract_and_save(db: Session, pg_user_id: int, conversation_text: str) -> int:
    """Run GPT-4o-mini over the conversation to extract memory facts, save to Postgres.

    Returns the number of memories saved.
    """
    if not conversation_text.strip():
        return 0

    raw = _call_extractor(conversation_text)
    if not raw:
        return 0

    saved = 0
    for entry in raw:
        memory_type = entry.get("type")
        key = entry.get("key", "").strip()
        value = entry.get("value", "").strip()
        if not key or not value or memory_type not in ("preference", "summary", "entity", "conversation"):
            continue
        _upsert_memory(db, pg_user_id, memory_type, key, value)
        saved += 1

    if saved:
        db.commit()
        logger.info("Saved %d memory entries for user %s", saved, pg_user_id)
    return saved


def _upsert_memory(db: Session, user_id: int, memory_type: str, key: str, value: str):
    """Insert or update a single memory entry."""
    from app.db.models import UserMemory

    row = (
        db.query(UserMemory)
        .filter(
            UserMemory.user_id == user_id,
            UserMemory.memory_type == memory_type,
            UserMemory.key == key,
        )
        .first()
    )
    if row:
        row.value = value
        row.updated_at = datetime.utcnow()
    else:
        db.add(UserMemory(
            user_id=user_id,
            memory_type=memory_type,
            key=key,
            value=value,
        ))


def _call_extractor(conversation_text: str) -> list[dict]:
    """Call GPT-4o-mini to extract structured memory facts from a conversation."""
    from openai import OpenAI

    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

    system_prompt = """You are a memory extraction assistant for an AI email organizer.

Given a conversation between a user and the email agent, extract facts worth remembering long-term.

Output a JSON array of memory entries. Each entry has:
  "type": one of "preference" | "summary" | "entity" | "conversation"
  "key":  short identifier (e.g. "newsletter_handling", "2026-06-03", "sender:invoices@acme.com")
  "value": concise fact in plain text (1-2 sentences max)

Memory types:
- preference: user's explicit or inferred preferences about email handling
- summary: what happened in this session (emails processed, groups created)
- entity: known sender/domain and how to categorize them
- conversation: important decision or context the user shared

Rules:
- Only extract facts that are useful across future sessions
- Skip trivial chitchat
- Be concise — value should be under 100 characters
- Return [] if nothing worth remembering

Return ONLY valid JSON array, no other text."""

    user_prompt = f"Conversation:\n{conversation_text[-3000:]}"  # last 3000 chars

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0,
            max_tokens=800,
            response_format={"type": "json_object"},
        )
        text = response.choices[0].message.content
        parsed = json.loads(text)
        # handle both {"memories": [...]} and [...]
        if isinstance(parsed, dict):
            parsed = parsed.get("memories") or parsed.get("entries") or list(parsed.values())[0]
        return parsed if isinstance(parsed, list) else []
    except Exception as e:
        logger.warning("Memory extraction failed: %s", e)
        return []
