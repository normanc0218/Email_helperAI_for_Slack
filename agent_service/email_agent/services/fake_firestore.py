"""
In-memory fake Firestore service for eval/testing.
Same interface as firestore_service.py — no real Firebase connection.
Activated when EVAL_MODE=true.
"""

import uuid
from copy import deepcopy
from datetime import datetime, timezone

# ── Pre-seeded fake groups (matching real Firestore schema) ──────────────────

_GROUPS: dict[str, dict] = {
    "g001": {
        "group_id": "g001",
        "name": "Work",
        "user_id": "user",
        "email_count": 3,
        "summary": "Work-related emails including meeting notes and project updates.",
        "description": "Team and project communications",
        "email_ids": ["fake004", "fake005", "fake008"],
        "source": "agent",
        "last_activity": "2026-05-04T10:30:00+00:00",
        "created_at": "2026-05-01T09:00:00+00:00",
    },
    "g002": {
        "group_id": "g002",
        "name": "Billing",
        "user_id": "user",
        "email_count": 1,
        "summary": "Invoice and payment notifications from SaaS services.",
        "description": "Invoices and payments",
        "email_ids": ["fake002"],
        "source": "agent",
        "last_activity": "2026-05-04T09:15:00+00:00",
        "created_at": "2026-05-01T09:00:00+00:00",
    },
    "g003": {
        "group_id": "g003",
        "name": "Promotions",
        "user_id": "user",
        "email_count": 2,
        "summary": "Promotional emails and flash sale notifications.",
        "description": "Marketing and promotions",
        "email_ids": ["fake001", "fake006"],
        "source": "agent",
        "last_activity": "2026-05-04T08:00:00+00:00",
        "created_at": "2026-05-01T09:00:00+00:00",
    },
    "g004": {
        "group_id": "g004",
        "name": "Security",
        "user_id": "user",
        "email_count": 1,
        "summary": "Security alerts and account login notifications.",
        "description": "Account security",
        "email_ids": ["fake007"],
        "source": "agent",
        "last_activity": "2026-05-04T06:45:00+00:00",
        "created_at": "2026-05-01T09:00:00+00:00",
    },
}

# ── Pre-seeded fake email summaries ──────────────────────────────────────────

_SUMMARIES: dict[str, dict] = {
    "fake001": {"email_id": "fake001", "summary": "50% discount offer from shop.com, limited time."},
    "fake002": {"email_id": "fake002", "summary": "Invoice #4821 for $299 due May 15."},
    "fake003": {"email_id": "fake003", "summary": "AI weekly newsletter covering GPT-5 and Gemini updates."},
    "fake004": {"email_id": "fake004", "summary": "Monday standup notes with action items."},
    "fake005": {"email_id": "fake005", "summary": "PR #42 merged into main by alice."},
    "fake006": {"email_id": "fake006", "summary": "Flash sale ending tonight, 70% off electronics."},
    "fake007": {"email_id": "fake007", "summary": "New login detected from Chrome on Mac in Toronto."},
    "fake008": {"email_id": "fake008", "summary": "Q2 OKR review due by EOD Friday."},
}

_PROCESSED: set[str] = {"fake001", "fake002", "fake003", "fake004", "fake005", "fake006", "fake007", "fake008"}

# ── Fake action log (for undo) ────────────────────────────────────────────────

_ACTION_LOG: list[dict] = [
    {
        "id": 1,
        "user_id": 1,
        "action": "archive",
        "description": "Archived promotional email from deals@shop.com",
        "email_id": "fake001",
        "reversible": True,
        "created_at": "2026-05-04T08:05:00+00:00",
    },
    {
        "id": 2,
        "user_id": 1,
        "action": "archive",
        "description": "Archived flash sale email from promo@retailer.com",
        "email_id": "fake006",
        "reversible": True,
        "created_at": "2026-05-04T08:06:00+00:00",
    },
]


# ── Interface matching firestore_service.py ───────────────────────────────────

def save_email_summary(doc: dict) -> str:
    email_id = doc.get("email_id", str(uuid.uuid4()))
    _SUMMARIES[email_id] = doc
    return email_id


def get_email_summary(email_id: str) -> dict | None:
    return deepcopy(_SUMMARIES.get(email_id))


def mark_email_processed(email_id: str, group_id: str = "", user_id: str = "user") -> None:
    _PROCESSED.add(email_id)


def list_group_details(user_id: str = "user") -> list[dict]:
    return [deepcopy(g) for g in _GROUPS.values() if g["user_id"] == user_id]


def get_processed_email_ids(email_ids: list[str]) -> set[str]:
    return _PROCESSED & set(email_ids)


def save_group(doc: dict, user_id: str = "user") -> str:
    group_id = doc.get("group_id") or uuid.uuid4().hex[:8]
    _GROUPS[group_id] = {**doc, "group_id": group_id, "user_id": user_id}
    return group_id


def get_group(group_id: str) -> dict | None:
    return deepcopy(_GROUPS.get(group_id))


def update_group(group_id: str, updates: dict) -> None:
    if group_id in _GROUPS:
        _GROUPS[group_id].update(updates)
        _GROUPS[group_id]["last_activity"] = datetime.now(tz=timezone.utc).isoformat()


def list_groups(user_id: str = "user") -> list[dict]:
    return [deepcopy(g) for g in _GROUPS.values() if g["user_id"] == user_id]


def find_group_by_thread_id(thread_id: str, user_id: str = "user") -> dict | None:
    return None  # no thread matching in fake


def find_nearest_group(embedding: list[float], user_id: str = "user", limit: int = 1) -> dict | None:
    groups = [g for g in _GROUPS.values() if g["user_id"] == user_id]
    if not groups:
        return None
    result = deepcopy(groups[0])
    result["similarity"] = 0.95
    return result


def find_nearest_group_top_k(embedding: list[float], user_id: str = "user", k: int = 5) -> list[dict]:
    groups = [g for g in _GROUPS.values() if g["user_id"] == user_id]
    results = []
    for i, g in enumerate(groups[:k]):
        item = deepcopy(g)
        item["similarity"] = round(0.95 - i * 0.05, 2)
        results.append(item)
    return results


def delete_all_groups() -> int:
    count = len(_GROUPS)
    _GROUPS.clear()
    return count


def delete_all_summaries() -> int:
    count = len(_SUMMARIES)
    _SUMMARIES.clear()
    return count


def get_emails_for_group(group_id: str) -> list[dict]:
    """Return fake email details for a group (mirrors firestore_service interface)."""
    group = _GROUPS.get(group_id)
    if not group:
        return []
    email_ids = group.get("email_ids", [])
    results = []
    for eid in email_ids:
        s = _SUMMARIES.get(eid, {})
        results.append({
            "subject": s.get("subject", f"(email {eid})"),
            "sender": s.get("sender", "fake@example.com"),
            "date": s.get("date", "2026-05-04"),
            "snippet": s.get("summary", ""),
        })
    return results


def get_action_log() -> list[dict]:
    return deepcopy(_ACTION_LOG)
