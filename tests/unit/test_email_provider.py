"""
Layer 2 — FakeProvider and get_fast_group tests.
No network calls. FakeProvider is already a production class, not a mock.
"""

import pytest

from agent_service.email_agent.services.email_provider import FakeProvider


class TestFakeProviderFetchEmails:
    def test_returns_list_of_dicts(self):
        p = FakeProvider()
        emails = p.fetch_emails(max_results=5)
        assert isinstance(emails, list)
        assert len(emails) == 5

    def test_each_email_has_required_keys(self):
        p = FakeProvider()
        for email in p.fetch_emails():
            assert "id" in email
            assert "subject" in email
            assert "from" in email
            assert "snippet" in email

    def test_respects_max_results(self):
        p = FakeProvider()
        assert len(p.fetch_emails(max_results=2)) == 2

    def test_fetch_emails_page_returns_tuple(self):
        p = FakeProvider()
        emails, next_token = p.fetch_emails_page(page_size=3)
        assert len(emails) == 3
        assert next_token is None  # FakeProvider has no pagination


class TestFakeProviderBody:
    def test_returns_body_for_known_id(self):
        p = FakeProvider()
        body = p.get_email_body("fake001")
        assert isinstance(body, str)
        assert len(body) > 0

    def test_returns_fallback_for_unknown_id(self):
        p = FakeProvider()
        body = p.get_email_body("nonexistent-id")
        assert "no body" in body.lower()


class TestFakeProviderWriteOps:
    def test_archive_returns_true(self):
        assert FakeProvider().archive_email("fake001") is True

    def test_unarchive_returns_true(self):
        assert FakeProvider().unarchive_email("fake001") is True

    def test_label_returns_true(self):
        assert FakeProvider().label_email("fake001", "Work") is True

    def test_remove_label_returns_true(self):
        assert FakeProvider().remove_label("fake001", "Work") is True

    def test_list_user_labels_returns_list(self):
        labels = FakeProvider().list_user_labels()
        assert isinstance(labels, list)
        assert all("id" in l and "name" in l for l in labels)


class TestGetFastGroup:
    """Tests the deterministic fast-path grouping logic (no LLM)."""

    def test_promotions_label_maps_to_group(self, fake_email_promo):
        p = FakeProvider()
        assert p.get_fast_group(fake_email_promo) == "Promotions"

    def test_list_id_header_creates_mailing_list_group(self, fake_email_newsletter):
        p = FakeProvider()
        result = p.get_fast_group(fake_email_newsletter)
        assert result is not None
        assert "Mailing List" in result or "Newsletter" in result or "list" in result.lower()

    def test_bulk_precedence_creates_newsletter_group(self):
        p = FakeProvider()
        email = {
            "label_ids": [],
            "list_id": "",
            "precedence": "bulk",
            "list_unsubscribe": "",
            "subject": "Some bulk mail",
        }
        assert p.get_fast_group(email) == "Newsletters"

    def test_normal_email_returns_none(self, fake_email):
        p = FakeProvider()
        assert p.get_fast_group(fake_email) is None

    def test_ticket_pattern_in_subject_creates_tickets_group(self):
        p = FakeProvider()
        email = {
            "label_ids": [],
            "list_id": "",
            "precedence": "",
            "list_unsubscribe": "",
            "subject": "[JIRA-123] Fix login bug",
        }
        result = p.get_fast_group(email)
        assert result is not None
        assert "Ticket" in result or "JIRA" in result
