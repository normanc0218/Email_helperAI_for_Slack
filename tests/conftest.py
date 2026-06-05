import os
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Use fake email provider globally — no real Gmail API calls in tests
os.environ["EMAIL_PROVIDER"] = "fake"

# ── SQLite in-memory DB for agent's ActionLog (agent_service ORM) ─────────────

from agent_service.email_agent.database import Base as AgentBase
from agent_service.email_agent.models.action_log import ActionLog  # registers model


@pytest.fixture
def db_session():
    """SQLite in-memory session for ActionLog tests — real ORM, no file."""
    engine = create_engine("sqlite:///:memory:")
    AgentBase.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()
    AgentBase.metadata.drop_all(engine)


# ── Canonical fake email dicts ─────────────────────────────────────────────────

@pytest.fixture
def fake_email():
    return {
        "id": "fake001",
        "thread_id": "thread-work-1",
        "subject": "Meeting notes from Monday standup",
        "from": "alice@company.com",
        "snippet": "Action items assigned to you.",
        "label_ids": [],
        "list_id": "",
        "precedence": "",
        "list_unsubscribe": "",
    }


@pytest.fixture
def fake_email_newsletter():
    return {
        "id": "fake003",
        "thread_id": "thread-newsletter-1",
        "subject": "Weekly newsletter: AI trends",
        "from": "editor@aiweekly.com",
        "snippet": "Top 5 AI stories this week.",
        "label_ids": [],
        "list_id": "<weekly.aiweekly.com>",
        "precedence": "list",
        "list_unsubscribe": "<mailto:unsub@aiweekly.com>",
    }


@pytest.fixture
def fake_email_promo():
    return {
        "id": "fake001",
        "thread_id": "thread-promo-1",
        "subject": "50% off your next order!",
        "from": "deals@shop.com",
        "snippet": "Limited time offer just for you.",
        "label_ids": ["CATEGORY_PROMOTIONS"],
        "list_id": "",
        "precedence": "",
        "list_unsubscribe": "",
    }


# ── Fake Firestore group lists ────────────────────────────────────────────────

@pytest.fixture
def fake_groups():
    return [
        {
            "group_id": "g1",
            "name": "Work",
            "email_count": 10,
            "summary": "Team updates and project discussions.",
            "last_activity": "2026-06-01",
            "source": "agent",
        },
        {
            "group_id": "g2",
            "name": "Billing",
            "email_count": 3,
            "summary": "Invoices and payment receipts.",
            "last_activity": "2026-05-30",
            "source": "agent",
        },
    ]


# ── ADK ToolContext substitute ─────────────────────────────────────────────────
# Uses instance variables so each test gets its own state dict.

@pytest.fixture
def fake_tool_context():
    class FakeCtx:
        def __init__(self):
            self.state = {
                "pg_user_id": 1,
                "user_id": "testuser",
                "dry_run": True,
            }
    return FakeCtx()


@pytest.fixture
def fake_tool_context_with_emails():
    class FakeCtx:
        def __init__(self):
            self.state = {
                "pg_user_id": 1,
                "user_id": "testuser",
                "dry_run": True,
                "emails_to_cluster": [
                    {
                        "id": "fake001",
                        "subject": "Meeting notes from standup",
                        "from": "alice@company.com",
                        "snippet": "Action items: review PR by Wednesday.",
                        "label_ids": [],
                    },
                    {
                        "id": "fake002",
                        "subject": "Invoice #4821 is ready",
                        "from": "billing@saas.io",
                        "snippet": "Please pay by May 15.",
                        "label_ids": [],
                    },
                ],
            }
    return FakeCtx()
