"""Rule-based intent router (A+B) — no LLM, pure classification."""

from haystack.dataclasses import ChatMessage

from app.services.intent_router import (
    DEFAULT_AGENT_GROUPS,
    TOOL_GROUPS,
    filter_tools,
    route_intent,
)


def _user(text: str):
    return [ChatMessage.from_user(text)]


def test_greeting_is_simple():
    d = route_intent(_user("Γεια σου! Ποια είσαι;"))
    assert d.mode == "simple"
    assert d.tool_names == []


def test_thanks_is_simple():
    d = route_intent(_user("Ευχαριστώ πολύ!"))
    assert d.mode == "simple"


def test_english_hello_simple():
    d = route_intent(_user("Hi, who are you?"))
    assert d.mode == "simple"


def test_time_only_gets_core_tool():
    d = route_intent(_user("Τι ώρα είναι στην Αθήνα;"))
    assert d.mode == "agent"
    assert d.groups == frozenset({"core"})
    assert d.tool_names == ["get_current_datetime"]


def test_knowledge_followup_filters_to_knowledge():
    d = route_intent(
        _user(
            "Χρησιμοποίησε search_knowledge και πες τη δομή του follow-up προτύπου."
        )
    )
    assert d.mode == "agent"
    assert "knowledge" in d.groups
    assert "core" in d.groups
    assert "search_knowledge" in d.tool_names
    # Should not drag firecrawl/gdpr unless asked
    assert "research_with_firecrawl" not in d.tool_names
    assert "gdpr_export_user_data" not in d.tool_names


def test_soft_template_request_knowledge():
    d = route_intent(
        _user("Ετοίμασε σύντομο follow-up email βάσει προτύπου μετά από συνάντηση.")
    )
    assert d.mode == "agent"
    assert "knowledge" in d.groups
    assert "search_knowledge" in d.tool_names


def test_calendar_propose_gets_cal_tools():
    d = route_intent(
        _user("Πρότεινε ραντεβού αύριο 11:00 στο Outlook calendar.")
    )
    assert d.mode == "agent"
    assert "cal_ms" in d.groups
    assert "ms_propose_create_event" in d.tool_names


def test_gmail_specific():
    d = route_intent(_user("Διάβασε τα τελευταία emails στο Gmail"))
    assert d.mode == "agent"
    assert "mail_google" in d.groups
    assert "google_list_emails" in d.tool_names


def test_web_scrape_group():
    d = route_intent(_user("Κάνε scrape το https://example.com με firecrawl"))
    assert d.mode == "agent"
    assert "web" in d.groups
    assert "firecrawl_scrape_website" in d.tool_names


def test_gdpr_export():
    d = route_intent(_user("Θέλω εξαγωγή δεδομένων GDPR"))
    assert d.mode == "agent"
    assert "gdpr" in d.groups


def test_router_disabled_exposes_all_groups():
    d = route_intent(_user("Γεια"), enabled=False)
    assert d.mode == "agent"
    assert d.groups == frozenset(TOOL_GROUPS.keys())


def test_filter_tools_by_name():
    class T:
        def __init__(self, name):
            self.tool_spec = {"name": name}

    tools = [T("a"), T("b"), T("c")]
    assert [t.tool_spec["name"] for t in filter_tools(tools, ["b", "c"])] == ["b", "c"]
    assert len(filter_tools(tools, None)) == 3


def test_default_pack_subset_of_all():
    assert DEFAULT_AGENT_GROUPS < frozenset(TOOL_GROUPS.keys())
    assert "web" not in DEFAULT_AGENT_GROUPS
    assert "gdpr" not in DEFAULT_AGENT_GROUPS
