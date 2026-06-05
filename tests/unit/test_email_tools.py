"""
Layer 3 — finalize_email_processing tests.
Mocks: Firestore (find_or_create_group, mark_email_processed, list_groups, update_group),
       Postgres SessionLocal (SQLite in-memory), OpenAI (summary generation).
EMAIL_PROVIDER=fake (set in conftest) so FakeProvider handles label/archive no-ops.
"""

import pytest
from unittest.mock import MagicMock


def _patch_finalize_deps(monkeypatch, db_session, created_groups=None):
    """Patch all external calls needed by finalize_email_processing."""

    # All deps are lazy-imported inside finalize_email_processing —
    # patch at the source module, not at email_tools.

    # Firestore: find_or_create_group
    group_counter = {"n": 0}
    def fake_find_or_create(project_name, email_ids, description="", sender="",
                             thread_id="", embedding=None, user_id="cli"):
        group_counter["n"] += 1
        return {"group_id": f"g-{group_counter['n']}", "name": project_name,
                "email_count": len(email_ids), "action": "created"}
    monkeypatch.setattr(
        "agent_service.email_agent.services.grouping_service.find_or_create_group",
        fake_find_or_create,
    )

    # Firestore: mark_email_processed, list_groups, update_group
    monkeypatch.setattr(
        "agent_service.email_agent.services.firestore_service.mark_email_processed",
        lambda **kwargs: None,
    )
    monkeypatch.setattr(
        "agent_service.email_agent.services.firestore_service.list_groups",
        lambda user_id: [],
    )
    monkeypatch.setattr(
        "agent_service.email_agent.services.firestore_service.update_group",
        lambda group_id, data: None,
    )

    # Postgres: use SQLite in-memory session
    monkeypatch.setattr(
        "agent_service.email_agent.database.SessionLocal",
        lambda: db_session,
    )

    # OpenAI: return a fixed summary string
    mock_resp = MagicMock()
    mock_resp.choices[0].message.content = "Test summary."
    monkeypatch.setattr(
        "openai.OpenAI",
        lambda: MagicMock(chat=MagicMock(completions=MagicMock(
            create=lambda **kw: mock_resp
        ))),
    )

    # metrics: no-op
    monkeypatch.setattr(
        "agent_service.email_agent.services.metrics_service.metrics",
        MagicMock(record_finalize=lambda **kw: None),
    )


def _build_tool_context(dry_run=True, emails=None, pre_cls=None):
    class FakeCtx:
        def __init__(self):
            self.state = {
                "pg_user_id": 1,
                "user_id": "testuser",
                "dry_run": dry_run,
                "_all_emails": emails or [],
                "email_pre_cls": pre_cls or {},
                "grouping_assignments": {},
                "_total_scanned": len(emails or []),
                "_already_processed": 0,
            }
    return FakeCtx()


class TestFinalizeEmailProcessing:
    def test_returns_early_when_no_emails(self):
        from agent_service.email_agent.tools.email_tools import finalize_email_processing

        ctx = _build_tool_context(emails=[])
        result = finalize_email_processing(tool_context=ctx)

        assert result["processed"] == 0
        assert "No emails" in result["message"]

    def test_archives_should_archive_emails_in_dry_run(self, monkeypatch, db_session):
        _patch_finalize_deps(monkeypatch, db_session)

        emails = [
            {"id": "e1", "subject": "Old newsletter", "from": "n@news.com",
             "snippet": "Weekly digest", "thread_id": "t1", "date": ""},
            {"id": "e2", "subject": "Important update", "from": "ceo@co.com",
             "snippet": "Please review", "thread_id": "t2", "date": ""},
        ]
        pre_cls = {
            "e1": {"group_name": "Newsletters", "should_archive": True, "archive_reason": "newsletter",
                   "needs_attention": False, "attention_reason": ""},
            "e2": {"group_name": "Work", "should_archive": False, "archive_reason": "",
                   "needs_attention": False, "attention_reason": ""},
        }
        ctx = _build_tool_context(dry_run=True, emails=emails, pre_cls=pre_cls)

        from agent_service.email_agent.tools.email_tools import finalize_email_processing
        result = finalize_email_processing(tool_context=ctx)

        archived_subjects = [a["subject"] for a in result["archived_emails"]]
        assert "Old newsletter" in archived_subjects
        assert "Important update" not in archived_subjects

    def test_needs_attention_emails_collected(self, monkeypatch, db_session):
        _patch_finalize_deps(monkeypatch, db_session)

        emails = [
            {"id": "e1", "subject": "Contract expiry", "from": "legal@co.com",
             "snippet": "Please sign", "thread_id": "t1", "date": ""},
        ]
        pre_cls = {
            "e1": {"group_name": "Legal", "should_archive": False, "archive_reason": "",
                   "needs_attention": True, "attention_reason": "contract requires signature"},
        }
        ctx = _build_tool_context(dry_run=True, emails=emails, pre_cls=pre_cls)

        from agent_service.email_agent.tools.email_tools import finalize_email_processing
        result = finalize_email_processing(tool_context=ctx)

        assert len(result["needs_attention"]) == 1
        assert result["needs_attention"][0]["subject"] == "Contract expiry"

    def test_uncategorized_email_gets_fallback_group(self, monkeypatch, db_session):
        _patch_finalize_deps(monkeypatch, db_session)

        emails = [
            {"id": "e1", "subject": "Random email", "from": "anon@nowhere.com",
             "snippet": "...", "thread_id": "t1", "date": ""},
        ]
        # email_pre_cls is empty — no classification → should fall into "Uncategorized"
        ctx = _build_tool_context(dry_run=True, emails=emails, pre_cls={})

        from agent_service.email_agent.tools.email_tools import finalize_email_processing
        result = finalize_email_processing(tool_context=ctx)

        group_names = list(result["groups"].keys())
        assert "Uncategorized" in group_names

    def test_processed_count_matches_email_count(self, monkeypatch, db_session):
        _patch_finalize_deps(monkeypatch, db_session)

        emails = [
            {"id": f"e{i}", "subject": f"Email {i}", "from": "x@co.com",
             "snippet": "text", "thread_id": f"t{i}", "date": ""}
            for i in range(4)
        ]
        pre_cls = {
            f"e{i}": {"group_name": "Work", "should_archive": False, "archive_reason": "",
                      "needs_attention": False, "attention_reason": ""}
            for i in range(4)
        }
        ctx = _build_tool_context(dry_run=True, emails=emails, pre_cls=pre_cls)

        from agent_service.email_agent.tools.email_tools import finalize_email_processing
        result = finalize_email_processing(tool_context=ctx)

        assert result["processed"] == 4
