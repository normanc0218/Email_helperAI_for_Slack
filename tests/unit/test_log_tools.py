"""
Layer 3 — log_tools tests using SQLite in-memory database.
Real ORM + real query logic, no real Postgres connection.
"""

import pytest
from datetime import datetime

from agent_service.email_agent.models.action_log import ActionLog


def _make_log(db, **kwargs):
    """Helper: insert one ActionLog row and return it."""
    defaults = {
        "user": "testuser",
        "action": "archive",
        "email_id": "e1",
        "email_subject": "Meeting notes",
        "status": "success",
        "undo_status": None,
        "timestamp": datetime.utcnow(),
    }
    defaults.update(kwargs)
    row = ActionLog(**defaults)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


class TestPreviewUndo:
    def _patch_session(self, monkeypatch, db_session):
        monkeypatch.setattr(
            "agent_service.email_agent.database.SessionLocal",
            lambda: db_session,
        )

    def test_scores_invoice_keyword_highest(self, monkeypatch, db_session):
        self._patch_session(monkeypatch, db_session)
        _make_log(db_session, email_id="e1", email_subject="Invoice from Stripe", action="archive")
        _make_log(db_session, email_id="e2", email_subject="Team standup notes", action="archive")

        from agent_service.email_agent.tools.log_tools import preview_undo
        result = preview_undo("the invoice archive")

        candidates = result["candidates"]
        assert len(candidates) >= 1
        assert candidates[0]["email_subject"] == "Invoice from Stripe"

    def test_returns_empty_when_no_match(self, monkeypatch, db_session):
        self._patch_session(monkeypatch, db_session)
        _make_log(db_session, email_subject="Team meeting")

        from agent_service.email_agent.tools.log_tools import preview_undo
        result = preview_undo("something completely unrelated xyz")

        assert result["candidates"] == []

    def test_excludes_dry_run_entries(self, monkeypatch, db_session):
        self._patch_session(monkeypatch, db_session)
        _make_log(db_session, email_subject="Invoice dry-run", status="dry_run")
        _make_log(db_session, email_subject="Invoice real", status="success")

        from agent_service.email_agent.tools.log_tools import preview_undo
        result = preview_undo("invoice")

        subjects = [c["email_subject"] for c in result["candidates"]]
        assert "Invoice dry-run" not in subjects
        assert "Invoice real" in subjects

    def test_excludes_already_undone_entries(self, monkeypatch, db_session):
        self._patch_session(monkeypatch, db_session)
        _make_log(db_session, email_subject="Invoice already undone", undo_status="undone")
        _make_log(db_session, email_subject="Invoice fresh", undo_status=None)

        from agent_service.email_agent.tools.log_tools import preview_undo
        result = preview_undo("invoice")

        subjects = [c["email_subject"] for c in result["candidates"]]
        assert "Invoice already undone" not in subjects
        assert "Invoice fresh" in subjects

    def test_returns_at_most_5_candidates(self, monkeypatch, db_session):
        self._patch_session(monkeypatch, db_session)
        for i in range(10):
            _make_log(db_session, email_id=f"e{i}", email_subject=f"Invoice #{i}")

        from agent_service.email_agent.tools.log_tools import preview_undo
        result = preview_undo("invoice")

        assert len(result["candidates"]) <= 5

    def test_result_has_instruction_field(self, monkeypatch, db_session):
        self._patch_session(monkeypatch, db_session)

        from agent_service.email_agent.tools.log_tools import preview_undo
        result = preview_undo("anything")

        assert "instruction" in result
        assert "candidates" in result


class TestGetActionLog:
    def _patch_session(self, monkeypatch, db_session):
        monkeypatch.setattr(
            "agent_service.email_agent.database.SessionLocal",
            lambda: db_session,
        )

    def test_returns_list(self, monkeypatch, db_session):
        self._patch_session(monkeypatch, db_session)
        _make_log(db_session)

        from agent_service.email_agent.tools.log_tools import get_action_log
        result = get_action_log()

        assert isinstance(result, list)

    def test_respects_limit(self, monkeypatch, db_session):
        self._patch_session(monkeypatch, db_session)
        for i in range(10):
            _make_log(db_session, email_id=f"e{i}")

        from agent_service.email_agent.tools.log_tools import get_action_log
        result = get_action_log(limit=3)

        assert len(result) <= 3

    def test_entries_have_expected_fields(self, monkeypatch, db_session):
        self._patch_session(monkeypatch, db_session)
        _make_log(db_session)

        from agent_service.email_agent.tools.log_tools import get_action_log
        entries = get_action_log()

        assert len(entries) > 0
        entry = entries[0]
        assert "log_id" in entry or "id" in entry
        assert "action" in entry
