"""Codex Responses API incomplete / max_time_limit handling."""

from app.services.llm_router import is_failoverable_error
from app.services.openai_oauth import _parse_codex_sse


def test_parse_incomplete_max_time_limit():
    sse = (
        'data: {"type":"response.incomplete","response":{'
        '"id":"resp_1","status":"incomplete",'
        '"incomplete_details":{"reason":"max_time_limit"},"output":[]}}\n\n'
    )
    rid, text, tools, reason = _parse_codex_sse(sse)
    assert rid == "resp_1"
    assert reason == "max_time_limit"
    assert tools == []


def test_incomplete_with_partial_text_keeps_content():
    sse = (
        'data: {"type":"response.output_text.delta","delta":"Hi "}\n\n'
        'data: {"type":"response.incomplete","response":{'
        '"id":"resp_2","status":"incomplete",'
        '"incomplete_details":{"reason":"max_time_limit"},'
        '"output":[{"type":"message","content":[{"type":"output_text","text":"Hi there"}]}]'
        "}}\n\n"
    )
    _rid, text, _tools, reason = _parse_codex_sse(sse)
    assert reason == "max_time_limit"
    assert "Hi" in (text or "")


def test_max_time_limit_is_failoverable():
    assert is_failoverable_error(ValueError("Response incomplete: max_time_limit"))
