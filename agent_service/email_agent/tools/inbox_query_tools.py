"""
Inbox query tools — read-only views over Firestore for answering user questions
about their organised email (group counts, summaries, email lists, etc.).
"""
import logging
from google.adk.tools import ToolContext

logger = logging.getLogger(__name__)


def _get_user_id(tool_context=None) -> str:
    if tool_context is not None:
        pg_id = getattr(tool_context, "state", {}).get("pg_user_id")
        if pg_id is not None:
            return str(pg_id)
    return "cli"


def get_inbox_stats(tool_context: ToolContext = None) -> dict:
    """Return a full snapshot of the user's organised inbox from Firestore.

    Covers:
    - Total number of groups
    - Total processed emails
    - Per-group: name, email count, summary, last activity

    Returns:
        Dict with total_groups, total_emails, and a groups list.
    """
    from ..services.firestore_service import list_groups

    groups = list_groups(_get_user_id(tool_context))
    total_emails = sum(g.get("email_count", 0) for g in groups)

    return {
        "total_groups": len(groups),
        "total_emails": total_emails,
        "groups": [
            {
                "name": g.get("name", ""),
                "email_count": g.get("email_count", 0),
                "summary": g.get("summary", ""),
                "last_activity": g.get("last_activity", ""),
                "source": g.get("source", "agent"),
            }
            for g in sorted(groups, key=lambda x: x.get("email_count", 0), reverse=True)
        ],
    }


def get_group_emails(group_name: str, tool_context: ToolContext = None) -> dict:
    """Return emails belonging to a specific group, looked up by name.

    Args:
        group_name: The group name to look up (case-insensitive partial match).

    Returns:
        Dict with group info and list of emails (subject, sender, date, snippet).
    """
    from ..services.firestore_service import list_groups, get_emails_for_group

    groups = list_groups(_get_user_id(tool_context))
    name_lower = group_name.lower()
    matched = [g for g in groups if name_lower in g.get("name", "").lower()]

    if not matched:
        return {"error": f"No group found matching '{group_name}'", "groups_available": [g["name"] for g in groups]}

    group = matched[0]
    emails = get_emails_for_group(group["group_id"])

    return {
        "group_name": group.get("name"),
        "email_count": len(emails),
        "summary": group.get("summary", ""),
        "emails": emails,
    }
