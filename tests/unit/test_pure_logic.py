"""
Layer 1 — Pure logic tests: no mocks, no network, no fixtures.
All functions are deterministic Python — just import and assert.
"""

from agent_service.email_agent.services.grouping_service import (
    _clean_subject,
    _cosine_similarity,
    _days_since,
)
from agent_service.email_agent.tools.email_tools import _sender_domain


# ── _clean_subject ─────────────────────────────────────────────────────────────

class TestCleanSubject:
    def test_removes_single_re(self):
        assert _clean_subject("Re: Project Update") == "Project Update"

    def test_removes_multiple_re(self):
        assert _clean_subject("Re: Re: Re: Project Update") == "Project Update"

    def test_removes_fwd(self):
        assert _clean_subject("Fwd: Meeting notes") == "Meeting notes"

    def test_removes_bracket_prefix(self):
        assert _clean_subject("[EXTERNAL] Security Alert") == "Security Alert"

    def test_removes_re_and_bracket(self):
        assert _clean_subject("Re: [JIRA] Fix login bug") == "Fix login bug"

    def test_no_prefix_unchanged(self):
        assert _clean_subject("Project Update") == "Project Update"

    def test_empty_string_returns_untitled(self):
        assert _clean_subject("") == "Untitled"

    def test_strips_whitespace(self):
        assert _clean_subject("Re:   Lots of spaces") == "Lots of spaces"


# ── _cosine_similarity ─────────────────────────────────────────────────────────

class TestCosineSimilarity:
    def test_identical_vectors_return_one(self):
        v = [0.1, 0.2, 0.3]
        assert abs(_cosine_similarity(v, v) - 1.0) < 1e-6

    def test_orthogonal_vectors_return_zero(self):
        a = [1.0, 0.0]
        b = [0.0, 1.0]
        assert abs(_cosine_similarity(a, b)) < 1e-6

    def test_opposite_vectors_return_negative_one(self):
        a = [1.0, 0.0]
        b = [-1.0, 0.0]
        assert abs(_cosine_similarity(a, b) + 1.0) < 1e-6

    def test_zero_vector_returns_zero(self):
        assert _cosine_similarity([0.0, 0.0], [1.0, 0.0]) == 0.0

    def test_symmetry(self):
        a = [0.3, 0.4, 0.5]
        b = [0.1, 0.9, 0.2]
        assert abs(_cosine_similarity(a, b) - _cosine_similarity(b, a)) < 1e-9

    def test_result_bounded_between_minus_one_and_one(self):
        import random
        random.seed(42)
        a = [random.gauss(0, 1) for _ in range(50)]
        b = [random.gauss(0, 1) for _ in range(50)]
        sim = _cosine_similarity(a, b)
        assert -1.0 - 1e-6 <= sim <= 1.0 + 1e-6


# ── _sender_domain ─────────────────────────────────────────────────────────────

class TestSenderDomain:
    def test_extracts_domain_from_display_name(self):
        assert _sender_domain("Alice <alice@github.com>") == "github.com"

    def test_extracts_domain_from_plain_email(self):
        assert _sender_domain("billing@stripe.com") == "stripe.com"

    def test_lowercases_domain(self):
        assert _sender_domain("User <user@GitHub.COM>") == "github.com"

    def test_returns_unknown_for_invalid(self):
        assert _sender_domain("not-an-email") == "unknown"

    def test_returns_unknown_for_empty(self):
        assert _sender_domain("") == "unknown"

    def test_handles_subdomain(self):
        assert _sender_domain("no-reply@mail.company.io") == "mail.company.io"


# ── _days_since ────────────────────────────────────────────────────────────────

class TestDaysSince:
    def test_recent_datetime_returns_small_number(self):
        from datetime import datetime, timezone, timedelta
        recent = datetime.now(timezone.utc) - timedelta(days=3)
        days = _days_since(recent)
        assert 2.9 < days < 3.1

    def test_old_datetime_returns_large_number(self):
        from datetime import datetime, timezone
        old = datetime(2020, 1, 1, tzinfo=timezone.utc)
        days = _days_since(old)
        assert days > 365 * 2

    def test_none_returns_999_fallback(self):
        # None returns 999.0 — treated as "very old" for scoring purposes
        assert _days_since(None) == 999.0

    def test_naive_datetime_treated_as_utc(self):
        from datetime import datetime, timedelta
        naive = datetime.utcnow() - timedelta(days=5)
        days = _days_since(naive)
        assert 4.9 < days < 5.1
