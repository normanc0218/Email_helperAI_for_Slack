"""
Layer 2 — grouping_tools tests.
Uses FakeToolContext with pre-populated state. No external calls.
"""

import pytest


class TestGetEmailsForGrouping:
    def test_enriches_emails_with_domain(self, fake_tool_context_with_emails):
        from agent_service.email_agent.tools.grouping_tools import get_emails_for_grouping

        result = get_emails_for_grouping(tool_context=fake_tool_context_with_emails)

        assert result["count"] == 2
        domains = {e["domain"] for e in result["emails"]}
        assert "company.com" in domains
        assert "saas.io" in domains

    def test_truncates_snippet_to_200_chars(self, fake_tool_context_with_emails):
        # Add an email with a very long snippet
        fake_tool_context_with_emails.state["emails_to_cluster"].append({
            "id": "fake999",
            "subject": "Long email",
            "from": "sender@example.com",
            "snippet": "x" * 500,
            "label_ids": [],
        })
        from agent_service.email_agent.tools.grouping_tools import get_emails_for_grouping

        result = get_emails_for_grouping(tool_context=fake_tool_context_with_emails)

        long_email = next(e for e in result["emails"] if e["id"] == "fake999")
        assert len(long_email["snippet"]) <= 200

    def test_empty_state_returns_zero(self, fake_tool_context):
        from agent_service.email_agent.tools.grouping_tools import get_emails_for_grouping

        result = get_emails_for_grouping(tool_context=fake_tool_context)

        assert result["count"] == 0
        assert result["emails"] == []


class TestSaveGroupingDecisions:
    def test_writes_decisions_to_state(self, fake_tool_context_with_emails):
        from agent_service.email_agent.tools.grouping_tools import save_grouping_decisions

        decisions = [
            {"email_id": "fake001", "group_name": "Work", "should_archive": False,
             "archive_reason": "", "needs_attention": False, "attention_reason": ""},
            {"email_id": "fake002", "group_name": "Billing", "should_archive": True,
             "archive_reason": "automated invoice", "needs_attention": False, "attention_reason": ""},
        ]
        result = save_grouping_decisions(decisions, tool_context=fake_tool_context_with_emails)

        assert result["saved"] == 2
        assignments = fake_tool_context_with_emails.state["grouping_assignments"]
        assert assignments["fake001"]["group_name"] == "Work"
        assert assignments["fake002"]["should_archive"] is True

    def test_missing_emails_tracked(self, fake_tool_context_with_emails):
        from agent_service.email_agent.tools.grouping_tools import save_grouping_decisions

        # Only provide decision for one of the two emails
        decisions = [
            {"email_id": "fake001", "group_name": "Work", "should_archive": False,
             "archive_reason": "", "needs_attention": False, "attention_reason": ""},
        ]
        result = save_grouping_decisions(decisions, tool_context=fake_tool_context_with_emails)

        assert result["missing_count"] == 1
        assert "fake002" in result["missing_ids"]

    def test_no_tool_context_returns_error(self):
        from agent_service.email_agent.tools.grouping_tools import save_grouping_decisions

        result = save_grouping_decisions([], tool_context=None)
        assert "error" in result
