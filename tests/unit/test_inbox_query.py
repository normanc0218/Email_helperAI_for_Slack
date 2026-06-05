"""
Layer 2 — inbox_query_tools tests.
Mocks Firestore list_groups; tests aggregation and sorting logic.
"""

import pytest


class TestGetInboxStats:
    def test_total_counts_are_correct(self, monkeypatch, fake_groups):
        monkeypatch.setattr(
            "agent_service.email_agent.services.firestore_service.list_groups",
            lambda user_id: fake_groups,
        )
        from agent_service.email_agent.tools.inbox_query_tools import get_inbox_stats

        result = get_inbox_stats()

        assert result["total_groups"] == 2
        assert result["total_emails"] == 13  # 10 + 3

    def test_groups_sorted_by_email_count_descending(self, monkeypatch, fake_groups):
        monkeypatch.setattr(
            "agent_service.email_agent.services.firestore_service.list_groups",
            lambda user_id: fake_groups,
        )
        from agent_service.email_agent.tools.inbox_query_tools import get_inbox_stats

        result = get_inbox_stats()

        counts = [g["email_count"] for g in result["groups"]]
        assert counts == sorted(counts, reverse=True)

    def test_empty_inbox_returns_zeros(self, monkeypatch):
        monkeypatch.setattr(
            "agent_service.email_agent.services.firestore_service.list_groups",
            lambda user_id: [],
        )
        from agent_service.email_agent.tools.inbox_query_tools import get_inbox_stats

        result = get_inbox_stats()

        assert result["total_groups"] == 0
        assert result["total_emails"] == 0
        assert result["groups"] == []

    def test_group_fields_present(self, monkeypatch, fake_groups):
        monkeypatch.setattr(
            "agent_service.email_agent.services.firestore_service.list_groups",
            lambda user_id: fake_groups,
        )
        from agent_service.email_agent.tools.inbox_query_tools import get_inbox_stats

        for group in get_inbox_stats()["groups"]:
            assert "name" in group
            assert "email_count" in group
            assert "summary" in group
            assert "last_activity" in group


class TestGetGroupEmails:
    def test_returns_error_when_group_not_found(self, monkeypatch, fake_groups):
        monkeypatch.setattr(
            "agent_service.email_agent.services.firestore_service.list_groups",
            lambda user_id: fake_groups,
        )
        from agent_service.email_agent.tools.inbox_query_tools import get_group_emails

        result = get_group_emails("NonExistentGroup")

        assert "error" in result
        assert "groups_available" in result
        assert "Work" in result["groups_available"]

    def _patch_db(self, monkeypatch, docs):
        """_db is lazy-imported inside get_group_emails → patch at source module."""
        fake_docs = [
            type("Doc", (), {"to_dict": lambda self, d=d: d})()
            for d in docs
        ]
        mock_db = type("DB", (), {
            "collection": lambda self, name: type("Col", (), {
                "where": lambda self, filter: type("Q", (), {
                    "stream": lambda self: iter(fake_docs)
                })()
            })()
        })()
        monkeypatch.setattr(
            "agent_service.email_agent.services.firestore_service._db",
            lambda: mock_db,
        )
        monkeypatch.setattr(
            "google.cloud.firestore_v1.base_query.FieldFilter",
            lambda field, op, value: None,
        )

    def test_partial_name_match_finds_group(self, monkeypatch, fake_groups):
        self._patch_db(monkeypatch, [
            {"subject": "Invoice Q1", "sender": "billing@stripe.com",
             "date": "2026-06-01", "snippet": "Your invoice is ready.", "group_id": "g2"},
        ])
        monkeypatch.setattr(
            "agent_service.email_agent.services.firestore_service.list_groups",
            lambda user_id: fake_groups,
        )

        from agent_service.email_agent.tools.inbox_query_tools import get_group_emails

        result = get_group_emails("bill")  # partial match → "Billing"

        assert result["group_name"] == "Billing"
        assert "emails" in result
        assert result["email_count"] == 1

    def test_case_insensitive_match(self, monkeypatch, fake_groups):
        self._patch_db(monkeypatch, [])
        monkeypatch.setattr(
            "agent_service.email_agent.services.firestore_service.list_groups",
            lambda user_id: fake_groups,
        )

        from agent_service.email_agent.tools.inbox_query_tools import get_group_emails

        result = get_group_emails("WORK")  # uppercase → should match "Work"

        assert result["group_name"] == "Work"
        assert "error" not in result
