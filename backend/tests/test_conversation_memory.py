"""Conversation memory search + intent routing for past chats."""

from app.services.conversation import format_memory_for_agent
from app.services.intent_router import route_intent
from haystack.dataclasses import ChatMessage


def test_yesterday_question_routes_to_memory():
    d = route_intent(
        [ChatMessage.from_user("Τι εκκρεμεί από τη χθεσινή συνομιλία;")]
    )
    assert d.mode == "agent"
    assert "memory" in d.groups
    assert "search_conversation_memory" in d.tool_names


def test_remember_routes_to_memory_not_only_mail():
    d = route_intent([ChatMessage.from_user("Θυμάσαι τι μου είπες χθες;")])
    assert "memory" in d.groups
    assert "search_conversation_memory" in d.tool_names


def test_format_memory_empty():
    text = format_memory_for_agent([], query="invoice")
    assert "No matching" in text
    assert "chat memory" in text.lower() or "conversation" in text.lower()


def test_format_memory_hits():
    text = format_memory_for_agent(
        [
            {
                "created_at": "2026-08-20T10:00:00+00:00",
                "conversation_title": "Pilot",
                "role": "user",
                "content": "Να θυμηθούμε το follow-up στον πελάτη",
            }
        ],
        query="follow-up",
    )
    assert "follow-up" in text or "Pilot" in text
    assert "Pilot" in text
    assert "email" not in text.lower() or "NOT" in text or "not" in text
