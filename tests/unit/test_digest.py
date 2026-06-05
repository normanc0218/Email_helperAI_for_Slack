"""
Layer 2 — daily_digest tests.
Mocks Firestore list_groups; tests formatting and aggregation logic.
"""

import pytest


class TestDailyDigest:
    def test_returns_dict(self, monkeypatch, fake_groups):
        monkeypatch.setattr(
            "agent_service.email_agent.tools.digest_tools.list_groups",
            lambda user_id: fake_groups,
        )
        from agent_service.email_agent.tools.digest_tools import daily_digest

        result = daily_digest()
        assert isinstance(result, dict)

    def test_includes_all_groups(self, monkeypatch, fake_groups):
        monkeypatch.setattr(
            "agent_service.email_agent.tools.digest_tools.list_groups",
            lambda user_id: fake_groups,
        )
        from agent_service.email_agent.tools.digest_tools import daily_digest

        result = daily_digest()
        assert result["group_count"] == 2
        assert result["total_emails"] == 13

    def test_empty_groups_returns_zero_counts(self, monkeypatch):
        monkeypatch.setattr(
            "agent_service.email_agent.tools.digest_tools.list_groups",
            lambda user_id: [],
        )
        from agent_service.email_agent.tools.digest_tools import daily_digest

        result = daily_digest()
        assert result["group_count"] == 0

    def test_groups_in_result(self, monkeypatch, fake_groups):
        monkeypatch.setattr(
            "agent_service.email_agent.tools.digest_tools.list_groups",
            lambda user_id: fake_groups,
        )
        from agent_service.email_agent.tools.digest_tools import daily_digest

        result = daily_digest()
        group_names = [g["name"] for g in result.get("groups", [])]
        assert "Work" in group_names
        assert "Billing" in group_names
