"""
Layer 3 — find_or_create_group decision logic tests.
All external calls (Firestore, OpenAI embedding) are mocked.
Tests verify the similarity-threshold and structural-scoring decisions.
"""

import pytest

# Deterministic 1536-dim vectors for similarity testing
VEC_A = [0.1] * 1536   # "query" vector
VEC_B = [0.1] * 1536   # identical to A → similarity = 1.0  (triggers merge)
VEC_C = [-0.1] * 1536  # opposite to A → similarity = -1.0  (triggers new group)


def _patch_embedding(monkeypatch, vector=VEC_A):
    monkeypatch.setattr(
        "agent_service.email_agent.services.grouping_service.get_embedding",
        lambda text: vector,
    )


def _patch_no_thread_match(monkeypatch):
    monkeypatch.setattr(
        "agent_service.email_agent.services.grouping_service.firestore_service.find_group_by_thread_id",
        lambda thread_id, user_id: None,
    )


class TestFindOrCreateGroup:
    def test_creates_new_group_when_no_candidate(self, monkeypatch):
        _patch_no_thread_match(monkeypatch)
        _patch_embedding(monkeypatch)
        monkeypatch.setattr(
            "agent_service.email_agent.services.grouping_service.firestore_service.find_nearest_group",
            lambda emb, user_id, limit: None,
        )
        created = {}
        def fake_create(name, email_ids, desc, emb, sender, thread_id, user_id):
            created["name"] = name
            return {"group_id": "new-g1", "name": name, "email_count": 1, "action": "created"}
        monkeypatch.setattr(
            "agent_service.email_agent.services.grouping_service._create_group",
            fake_create,
        )

        from agent_service.email_agent.services.grouping_service import find_or_create_group
        result = find_or_create_group("Website Redesign", ["e1"], user_id="1")

        assert result["action"] == "created"
        assert created["name"] == "Website Redesign"

    def test_creates_new_group_when_similarity_below_threshold(self, monkeypatch):
        _patch_no_thread_match(monkeypatch)
        _patch_embedding(monkeypatch, VEC_A)
        # Return a candidate with similarity < 0.70 → must create new
        monkeypatch.setattr(
            "agent_service.email_agent.services.grouping_service.firestore_service.find_nearest_group",
            lambda emb, user_id, limit: {
                "group_id": "g-other", "name": "Unrelated", "email_count": 2,
                "embedding": VEC_C, "senders": [], "thread_ids": [],
                "last_activity": None, "similarity": 0.3,
            },
        )
        created = {}
        monkeypatch.setattr(
            "agent_service.email_agent.services.grouping_service._create_group",
            lambda name, email_ids, desc, emb, sender, thread_id, user_id: (
                created.update({"name": name}) or
                {"group_id": "new-g2", "name": name, "email_count": 1, "action": "created"}
            ),
        )

        from agent_service.email_agent.services.grouping_service import find_or_create_group
        result = find_or_create_group("New Topic", ["e2"], user_id="1")

        assert result["action"] == "created"

    def test_merges_on_similarity_above_095(self, monkeypatch):
        _patch_no_thread_match(monkeypatch)
        _patch_embedding(monkeypatch, VEC_A)
        existing = {
            "group_id": "g-existing", "name": "Website Project", "email_count": 5,
            "embedding": VEC_B, "senders": [], "thread_ids": [],
            "last_activity": None, "similarity": 0.99,
        }
        monkeypatch.setattr(
            "agent_service.email_agent.services.grouping_service.firestore_service.find_nearest_group",
            lambda emb, user_id, limit: existing,
        )
        merged = {}
        def fake_merge(candidate, email_ids, sender, thread_id):
            merged["group_id"] = candidate["group_id"]
            return {**candidate, "action": "merged"}
        monkeypatch.setattr(
            "agent_service.email_agent.services.grouping_service._merge_into_group",
            fake_merge,
        )

        from agent_service.email_agent.services.grouping_service import find_or_create_group
        result = find_or_create_group("Website Redesign", ["e3"], user_id="1")

        assert result["action"] == "merged"
        assert merged["group_id"] == "g-existing"

    def test_thread_match_always_merges_regardless_of_similarity(self, monkeypatch):
        # Thread short-circuit: even with unrelated embeddings, same thread → merge
        thread_group = {
            "group_id": "g-thread", "name": "Project Alpha", "email_count": 3,
            "embedding": VEC_C,  # very different vector
            "senders": ["alice@co.com"], "thread_ids": ["t-123"],
            "last_activity": None,
        }
        monkeypatch.setattr(
            "agent_service.email_agent.services.grouping_service.firestore_service.find_group_by_thread_id",
            lambda thread_id, user_id: thread_group,
        )
        merged = {}
        def fake_merge(candidate, email_ids, sender, thread_id):
            merged["group_id"] = candidate["group_id"]
            return {**candidate, "action": "merged"}
        monkeypatch.setattr(
            "agent_service.email_agent.services.grouping_service._merge_into_group",
            fake_merge,
        )

        from agent_service.email_agent.services.grouping_service import find_or_create_group
        result = find_or_create_group(
            "Project Alpha Reply", ["e4"], thread_id="t-123", user_id="1"
        )

        assert result["action"] == "merged"
        assert merged["group_id"] == "g-thread"

    def test_vector_search_failure_creates_new_group(self, monkeypatch):
        _patch_no_thread_match(monkeypatch)
        _patch_embedding(monkeypatch)
        # Simulate Firestore index not ready (raises exception)
        monkeypatch.setattr(
            "agent_service.email_agent.services.grouping_service.firestore_service.find_nearest_group",
            lambda emb, user_id, limit: (_ for _ in ()).throw(RuntimeError("index not ready")),
        )
        created = {}
        monkeypatch.setattr(
            "agent_service.email_agent.services.grouping_service._create_group",
            lambda name, email_ids, desc, emb, sender, thread_id, user_id: (
                created.update({"name": name}) or
                {"group_id": "fallback-g", "name": name, "email_count": 1, "action": "created"}
            ),
        )

        from agent_service.email_agent.services.grouping_service import find_or_create_group
        result = find_or_create_group("Fallback Group", ["e5"], user_id="1")

        assert result["action"] == "created"
