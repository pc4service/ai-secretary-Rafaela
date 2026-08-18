"""Incremental indexing: embed only what changed (embeddings cost per call)."""

from app.services import knowledge as k
from app.services.knowledge import KnowledgeChunk


def _chunk(text="body", title="Title", cid="a-0"):
    return KnowledgeChunk(id=cid, source="a.md", title=title, tags=[], text=text)


def test_hash_is_stable_for_identical_content():
    assert k._chunk_hash(_chunk()) == k._chunk_hash(_chunk())


def test_hash_changes_when_text_changes():
    assert k._chunk_hash(_chunk(text="one")) != k._chunk_hash(_chunk(text="two"))


def test_hash_changes_when_title_changes():
    assert k._chunk_hash(_chunk(title="A")) != k._chunk_hash(_chunk(title="B"))


def test_hash_ignores_fields_that_are_not_embedded():
    """Only title+text are embedded, so tags/score must not churn the index."""
    a = KnowledgeChunk(id="x", source="a.md", title="T", tags=["one"], text="b", score=1.0)
    b = KnowledgeChunk(id="x", source="a.md", title="T", tags=["two"], text="b", score=9.0)
    assert k._chunk_hash(a) == k._chunk_hash(b)


def test_point_id_is_deterministic_and_uuid_shaped():
    pid = k._point_id("email-follow-up-0")
    assert pid == k._point_id("email-follow-up-0")
    assert len(pid) == 36 and pid.count("-") == 4


def test_point_ids_differ_per_chunk():
    assert k._point_id("doc-0") != k._point_id("doc-1")


def test_indexing_is_skipped_without_qdrant(monkeypatch):
    monkeypatch.setattr(k.settings, "QDRANT_URL", None)
    result = k.index_knowledge_to_qdrant()
    assert result["status"] == "skipped"
    # Keyword search must remain usable — that is the whole fallback story.
    assert k.keyword_search("follow-up") is not None


def test_stored_hashes_survives_a_broken_client():
    class Broken:
        def scroll(self, **kwargs):
            raise RuntimeError("qdrant down")

    # Falling back to {} means "re-embed everything", never a crash.
    assert k._stored_hashes(Broken()) == {}
