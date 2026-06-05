"""
Patches all Firestore calls with in-memory fakes for eval/testing.

Called automatically when EVAL_MODE=true. Import this module BEFORE the agent
is constructed so module-level imports in tools get the patched versions.

OpenAI (embedding + chat) is NOT patched — real API calls are used so that
the agent's reasoning and routing are evaluated authentically.
"""

import logging
from .services import firestore_service as _fs
from .services import fake_firestore as _fake

logger = logging.getLogger(__name__)


def install():
    """Monkey-patch firestore_service with fake in-memory implementations."""

    _fs.save_email_summary = _fake.save_email_summary
    _fs.get_email_summary = _fake.get_email_summary
    _fs.mark_email_processed = _fake.mark_email_processed
    _fs.list_group_details = _fake.list_group_details
    _fs.get_processed_email_ids = _fake.get_processed_email_ids
    _fs.save_group = _fake.save_group
    _fs.get_group = _fake.get_group
    _fs.update_group = _fake.update_group
    _fs.list_groups = _fake.list_groups
    _fs.find_group_by_thread_id = _fake.find_group_by_thread_id
    _fs.find_nearest_group = _fake.find_nearest_group
    _fs.find_nearest_group_top_k = _fake.find_nearest_group_top_k
    _fs.delete_all_groups = _fake.delete_all_groups
    _fs.delete_all_summaries = _fake.delete_all_summaries
    _fs.get_emails_for_group = _fake.get_emails_for_group

    # Disable the raw Firestore client so any forgotten direct _db() call
    # fails loudly instead of silently connecting to the real database.
    def _blocked(*args, **kwargs):
        raise RuntimeError(
            "EVAL_MODE: direct _db() call blocked. Use firestore_service functions instead."
        )
    _fs._db = _blocked

    logger.info("EVAL_MODE: Firestore patched with fake in-memory service")
