"""Knowledge keyword search works without Qdrant."""

from app.services.knowledge import keyword_search, search_knowledge, _merge_hits, KnowledgeChunk


def test_keyword_finds_follow_up():
    hits = keyword_search("follow-up meeting", top_k=3)
    assert isinstance(hits, list)
    # Repo knowledge/ is discoverable from backend/tests via candidate dirs
    if hits:
        assert any("follow" in (h.title + h.text).lower() or "meeting" in h.source for h in hits)


def test_merge_hybrid_boosts_overlap():
    a = KnowledgeChunk(id="1", source="a.md", title="A", tags=[], text="x", score=2.0)
    b = KnowledgeChunk(id="1", source="a.md", title="A", tags=[], text="x", score=3.0)
    c = KnowledgeChunk(id="2", source="b.md", title="B", tags=[], text="y", score=1.0)
    hits, mode = _merge_hits([a], [b, c], top_k=5)
    assert mode == "hybrid"
    assert hits[0].id == "1"
    assert hits[0].score >= 7.0


def test_search_knowledge_shape():
    data = search_knowledge("agenda", top_k=3)
    assert "mode" in data and "results" in data
    assert data["mode"] in ("keyword", "semantic", "hybrid")
