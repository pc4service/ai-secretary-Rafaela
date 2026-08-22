"""
Fast rule-based intent router for Rafaela.

Goals (latency A+B):
- **simple**: one LLM call, no tools (greetings, identity, pure chit-chat)
- **agent**: full Haystack agent with a *filtered* tool subset

No extra model call — classification is regex/keyword only so routing cost ≈ 0.
When unsure, prefer agent with a broad-but-not-maximal tool set (safe default).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import FrozenSet, Iterable, List, Optional, Sequence, Set

# --- Tool groups (names must match Haystack tool_spec.name) ---

TOOL_GROUPS: dict[str, tuple[str, ...]] = {
    "core": ("get_current_datetime",),
    "memory": ("search_conversation_memory",),
    "knowledge": ("search_knowledge", "knowledge_base_status"),
    "mail_ms": ("ms_list_emails",),
    "cal_ms": ("ms_list_calendar", "ms_propose_create_event"),
    "mail_google": ("google_list_emails",),
    "cal_google": ("google_list_calendar", "google_propose_create_event"),
    "web": (
        "research_with_firecrawl",
        "firecrawl_scrape_website",
        "firecrawl_propose_save_to_knowledge",
    ),
    "gdpr": ("gdpr_export_user_data", "gdpr_delete_user_data"),
}

# Default agent pack when we know we need tools but not which domain.
DEFAULT_AGENT_GROUPS: FrozenSet[str] = frozenset(
    {"core", "memory", "knowledge", "mail_ms", "cal_ms", "mail_google", "cal_google"}
)

# --- Patterns (EL + EN). Keep conservative: false "agent" is OK; false "simple" is not. ---

# Note: avoid trailing \b after Greek stems — letters like ώ keep the word open
# ("ευχαριστ" + "ώ" would fail \b). Use stem + optional Greek/Latin word chars.
_SIMPLE_OK = re.compile(
    r"(?i)(?:^|\s|[\(\[\{\"\"'«»])("
    r"γεια(?:\s*σου)?|καλημ[εέ]ρα|καλησπ[εέ]ρα|καλην[υύ]χτα|"
    r"hello|hi|hey|good\s*morning|good\s*evening|"
    r"ευχαριστ\w*|thanks|thank\s*you|παρακαλ\w*|please|"
    r"εντ[αά]ξει|ok|okay|μια\s*χαρ[αά]|τ[εέ]λεια|"
    r"ποια\s*ε[ιί]σαι|ποιος\s*ε[ιί]σαι|who\s*are\s*you|what\s*are\s*you|"
    r"παρουσι[αά]σου|introduce\s*yourself|τι\s*κ[αά]νεις|how\s*are\s*you|"
    r"dry[\s\-]?run|τι\s*μπορε[ιί]ς|what\s*can\s*you\s*do"
    r")(?:$|\s|[\)\]\}\.,;:!?]|'|\")"
)

_FORCE_AGENT = re.compile(
    r"(?i)("
    # explicit tools / data
    r"\b(search_knowledge|search_conversation_memory|ms_|google_|firecrawl|tool)\b|"
    r"\b(email|emails|inbox|mail|gmail|outlook|μην[υύ]ματ|αλληλογραφ)\w*|"
    r"\b(calendar|event|ραντεβ|ημερολ[οό]γ|συν[αά]ντησ|meeting|agenda)\w*|"
    r"\b(πρ[οό]τυπ|template|follow[\s\-]?up|tone\s*of\s*voice|playbook|knowledge|γν[ωώ]σ)\w*|"
    r"\b(research|scrap|ιστ[οό]σελ|website|https?://|www\.)\w*|"
    r"\b(gdpr|εξαγωγ|διαγραφ|export|delete\s*my\s*data|δικα[ιί]ωμα)\w*|"
    r"\b(πρ[οό]τειν|propose|δημιο[υύ]ργησ|create\s*event|schedule|κλε[ιί]σ)\w*|"
    r"\b(θυμ[αά]σ|συνομιλ|χθες|προχθ[εέ]ς|yesterday|last\s*chat|previous\s*(chat|conversation)|ιστορικ)\w*|"
    # daily briefing / secretary work even when prefixed with a greeting
    r"ανασκ[οό]πησ\w*|σ[υύ]νοψ\w*|briefing|daily\s*review|end\s*of\s*day|"
    r"εκκρεμ\w*|προτεραι\w*|task\w*|to\-?do|εργασ[ιί]\w*|"
    r"τι\s*(έχω|έγινε|προγραμμ)\w*|what('s|\s+is)\s+(on\s+)?(my\s+)?(today|calendar)|"
    r"\b(δι[αά]βασ|list|δε[ιί]ξ|show|check|//[εέ]λεγξ)\w*.{0,40}\b(mail|email|calendar|ραντεβ|inbox)"
    r")"
)

_GROUP_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    (
        "memory",
        re.compile(
            r"(?i)("
            r"search_conversation_memory|"
            r"θυμ[αά]σ\w*|συνομιλ\w*|"
            r"χθες|προχθ[εέ]ς|yesterday|"
            r"last\s*(week|night|time|chat|conversation)|"
            r"previous\s*(chat|conversation|thread)|"
            r"προηγο[υύ]μεν\w*\s*(συνομιλ|chat|thread)|"
            r"τι\s*(είπαμε|συζητ[ηή]σαμε|είπες)|"
            r"what\s*(did\s*we|we)\s*(discuss|say|talk)|"
            r"ιστορικ[οό]\s*συνομιλ|conversation\s*history|chat\s*memory"
            r")"
        ),
    ),
    # Day briefing pulls calendar + mail (+ memory); handled via DEFAULT when only this hits
    (
        "day_brief",
        re.compile(
            r"(?i)("
            r"ανασκ[οό]πησ\w*|σ[υύ]νοψ\w*\s*(ημ[εέ]ρ|day|today)|"
            r"daily\s*(review|brief|summary|digest)|end\s*of\s*day|"
            r"briefing|wrap\-?up|"
            r"τι\s*(έχω|έγινε)\s*(σ[ηή]μερα|today)|"
            r"what('s|\s+is)\s+on\s+(for\s+)?today|today'?s\s+(agenda|schedule|overview)"
            r")"
        ),
    ),
    (
        "knowledge",
        re.compile(
            r"(?i)("
            r"search_knowledge|knowledge_base|πρ[οό]τυπ|template|follow[\s\-]?up|"
            r"tone\s*of\s*voice|playbook|γν[ωώ]σ|βάση\s*γν[ωώ]|"
            r"draft|πρ[οό]χειρ|email\s*follow|ατζ[εέ]ντ|agenda\s*template|"
            r"out\s*of\s*office|ooo|υπενθ[υύ]μ"
            r")"
        ),
    ),
    (
        "mail_ms",
        re.compile(
            r"(?i)("
            r"\b(outlook|ms365|microsoft\s*365|ms_list_emails)\b|"
            r"\b(email|emails|inbox|mail|μην[υύ]ματ|αλληλογραφ)\w*"
            r")"
        ),
    ),
    (
        "mail_google",
        re.compile(r"(?i)\b(gmail|google\s*mail|google_list_emails)\b"),
    ),
    (
        "cal_ms",
        re.compile(
            r"(?i)("
            r"\b(outlook\s*calendar|ms_list_calendar|ms_propose)\b|"
            r"\b(calendar|event|ραντεβ|ημερολ[οό]γ|συν[αά]ντησ|meeting|schedule)\w*"
            r")"
        ),
    ),
    (
        "cal_google",
        re.compile(r"(?i)\b(google\s*calendar|google_list_calendar|google_propose)\b"),
    ),
    (
        "web",
        re.compile(
            r"(?i)("
            r"firecrawl|research_with|scrap|"
            r"https?://|www\.|"
            r"ιστ[οό]σελ|website|crawl|έρευν\w*\s+στο\s+web|search\s+the\s+web|"
            # Generic "find me info about X" without a known URL — the most
            # common real phrasing, and previously not matched at all, so it
            # silently fell back to DEFAULT_AGENT_GROUPS (no web tools).
            r"(φ[εέ]ρε|βρ[εέ]ς|ψ[αά]ξε|μ[αά]θε)\w*\s*(μου\s*)?πληροφορ|"
            r"πληροφορ\w*\s+για\s+(την\s+)?εταιρ|"
            r"\b(find|search|look\s*up|get)\b.{0,20}\binformation\b|"
            r"\binformation\s+(about|on)\b"
            r")"
        ),
    ),
    (
        "gdpr",
        re.compile(
            r"(?i)("
            r"\bgdpr\b|εξαγωγ[ηή]\s*δεδομ|διαγραφ[ηή]\s*δεδομ|"
            r"export\s*(my\s*)?data|delete\s*(my\s*)?data|right\s*to\s*erasure|"
            r"gdpr_export|gdpr_delete"
            r")"
        ),
    ),
    (
        "core",
        re.compile(
            r"(?i)("
            r"\b(τι\s*[ωώ]ρα|what\s*time|ημερομην|date\s*today|timezone|"
            r"get_current_datetime|Europe/Athens)\b"
            r")"
        ),
    ),
]

# Any http(s) / www / bare domain → always attach Firecrawl tools.
_URL_RE = re.compile(
    r"(?i)("
    r"https?://[^\s<>\]'\"\)]+"
    r"|www\.[^\s<>\]'\"\)]+"
    r"|(?<![@\w])(?:[a-z0-9](?:[a-z0-9\-]{0,61}[a-z0-9])?\.)+"
    r"(?:gr|com|net|org|eu|io|app|dev|co|uk|info)(?:/[^\s]*)?"
    r")"
)

# Pure time questions can stay on a tiny tool set without full agent pack.
_TIME_ONLY = re.compile(
    r"(?i)^\s*("
    r"(τι\s*[ωώ]ρα\s*(ε[ιί]ναι)?(\s*στ[ηη]ν?\s*αθ[ηή]να)?|"
    r"what\s*time\s*is\s*it(\s*in\s*athens)?|"
    r"ποια\s*ε[ιί]ναι\s*η\s*ημερομην[ιί]α|"
    r"what('s|\s+is)\s+the\s+date)"
    r")[\s;.!]*$"
)


@dataclass(frozen=True)
class RouteDecision:
    mode: str  # "simple" | "agent"
    groups: FrozenSet[str] = field(default_factory=frozenset)
    reason: str = ""

    @property
    def tool_names(self) -> List[str]:
        names: List[str] = []
        seen: Set[str] = set()
        for g in sorted(self.groups):
            for n in TOOL_GROUPS.get(g, ()):
                if n not in seen:
                    seen.add(n)
                    names.append(n)
        return names


def _last_user_text(messages: Sequence) -> str:
    """Extract last user utterance from Haystack ChatMessages or plain strings."""
    for m in reversed(list(messages or [])):
        if isinstance(m, str):
            return m.strip()
        role = getattr(getattr(m, "role", None), "value", None) or getattr(m, "role", None)
        if str(role).lower() in ("user", "chatrole.user"):
            text = getattr(m, "text", None)
            if text is None and hasattr(m, "texts"):
                try:
                    text = "\n".join(m.texts or [])
                except Exception:
                    text = str(m)
            return (text or "").strip()
    # Fallback: last message content
    if not messages:
        return ""
    m = messages[-1]
    if isinstance(m, str):
        return m.strip()
    return (getattr(m, "text", None) or str(m)).strip()


def detect_groups(text: str) -> Set[str]:
    found: Set[str] = set()
    for name, pat in _GROUP_PATTERNS:
        if pat.search(text):
            found.add(name)
    return found


def route_intent(
    messages: Sequence,
    *,
    enabled: bool = True,
) -> RouteDecision:
    """
    Decide simple vs agent and which tool groups to attach.

    ``enabled=False`` → legacy behaviour (all default agent groups + web + gdpr).
    """
    text = _last_user_text(messages)
    if not enabled:
        return RouteDecision(
            mode="agent",
            groups=frozenset(TOOL_GROUPS.keys()),
            reason="router_disabled",
        )
    if not text:
        return RouteDecision(mode="simple", groups=frozenset(), reason="empty")

    # Tiny specialized path: time/date only → core tool, still agent (1 tool).
    if _TIME_ONLY.match(text.strip()):
        return RouteDecision(
            mode="agent",
            groups=frozenset({"core"}),
            reason="time_only",
        )

    groups = detect_groups(text)
    force = bool(_FORCE_AGENT.search(text))
    simple_hit = bool(_SIMPLE_OK.search(text))
    words = re.findall(r"\w+", text, flags=re.UNICODE)
    has_url = bool(_URL_RE.search(text))

    # Pasted URLs / company sites → Firecrawl. Never claim "no browsing".
    if has_url:
        groups.add("web")
        groups.add("core")
        force = True

    # day_brief is a virtual group → expand to mail+cal+memory+core
    if "day_brief" in groups:
        groups.discard("day_brief")
        groups.update({"core", "memory", "mail_ms", "cal_ms", "mail_google", "cal_google"})
        force = True

    # Greeting + real task ("Καλησπέρα, κάνε ανασκόπηση…") must NOT go simple.
    # Only pure chit-chat: after stripping greeting-like tokens, little remains.
    residual = _SIMPLE_OK.sub(" ", text)
    residual_words = re.findall(r"\w+", residual, flags=re.UNICODE)
    pure_chitchat = (
        simple_hit
        and not force
        and not groups
        and not has_url
        and len(residual_words) <= 2
    )

    if pure_chitchat:
        return RouteDecision(mode="simple", groups=frozenset(), reason="chitchat")

    if (
        not force
        and not groups
        and not has_url
        and len(words) <= 6
        and simple_hit
        and len(residual_words) <= 2
    ):
        return RouteDecision(mode="simple", groups=frozenset(), reason="short_chitchat")

    if not groups:
        # Unclear secretary task — broad default pack, still skip web/gdpr noise.
        return RouteDecision(
            mode="agent",
            groups=DEFAULT_AGENT_GROUPS,
            reason="default_agent_pack" if force or len(words) > 4 else "default_short",
        )

    # Always allow clock alongside domain tools (cheap, often useful).
    groups.add("core")
    # Gmail-specific vs generic mail: generic mail keywords add both providers.
    if "mail_ms" in groups and "mail_google" not in groups:
        if re.search(r"(?i)\b(gmail|google\s*mail)\b", text):
            groups.add("mail_google")
        elif not re.search(r"(?i)\b(outlook|ms365|microsoft)\b", text):
            groups.add("mail_google")
    if "cal_ms" in groups and "cal_google" not in groups:
        if re.search(r"(?i)\b(google\s*calendar)\b", text):
            groups.add("cal_google")
        elif not re.search(r"(?i)\b(outlook|ms365|microsoft)\b", text):
            groups.add("cal_google")

    return RouteDecision(
        mode="agent",
        groups=frozenset(groups),
        reason="domain_tools",
    )


def filter_tools(all_tools: Iterable, names: Optional[Sequence[str]]) -> list:
    """Keep tools whose tool_spec.name is in ``names``. ``names is None`` → all."""
    tools = list(all_tools)
    if names is None:
        return tools
    allow = set(names)
    out = []
    for t in tools:
        spec = getattr(t, "tool_spec", None) or {}
        n = spec.get("name") if isinstance(spec, dict) else getattr(t, "name", None)
        if n in allow:
            out.append(t)
    return out
