"""
Multi-provider LLM router with automatic failover.

Solves single-provider outages (credits exhausted, rate limits, 5xx) by
trying a chain of OpenAI-compatible endpoints until one succeeds.

Configuration (either works):

1) Explicit chain (recommended for production):
   LLM_FAILOVER_CHAIN=opencode|kimi-k3|https://opencode.ai/zen/go/v1|OPENAI_API_KEY;xai|grok-3-mini|https://api.x.ai/v1|XAI_API_KEY;openai|gpt-4o-mini||OPENAI_FALLBACK_API_KEY

   Format per hop:  name|model|base_url|ENV_VAR_FOR_KEY
   - base_url empty  → official OpenAI API
   - hops separated by ';'

2) Auto chain from filled env slots (when LLM_FAILOVER_CHAIN is empty):
   OPENAI_API_KEY (+ optional OPENAI_BASE_URL / LLM_MODEL)  → primary
   XAI_API_KEY    (+ optional XAI_MODEL)                   → xAI Grok
   GEMINI_API_KEY (+ optional GEMINI_MODEL)                → Google Gemini
   OPENAI_FALLBACK_API_KEY (+ optional OPENAI_FALLBACK_MODEL) → plain OpenAI
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional, Tuple

import structlog
from haystack.components.generators.chat import OpenAIChatGenerator
from haystack.dataclasses import ChatMessage
from haystack.utils import Secret

from app.core.config import settings

logger = structlog.get_logger()


class CodexOAuthChatGenerator:
    """In-process ChatGPT/Codex generator (avoids self-HTTP deadlock on uvicorn)."""

    def __init__(self, access_token: str, model: str):
        self.access_token = access_token
        self.model = model
        self.streaming_callback = None
        self.tools = None

    def warm_up(self) -> None:
        return None

    def run(
        self,
        messages,
        streaming_callback=None,
        generation_kwargs=None,
        *,
        tools=None,
        tools_strict=None,
    ):
        import asyncio
        import json as _json
        from haystack.dataclasses import ToolCall
        from app.services.openai_oauth import codex_chat_completion

        if isinstance(messages, str):
            messages = [ChatMessage.from_user(messages)]

        oai_messages = []
        for m in messages or []:
            if hasattr(m, "to_openai_dict_format"):
                try:
                    oai_messages.append(m.to_openai_dict_format())
                    continue
                except Exception:
                    pass
            role = getattr(getattr(m, "role", None), "value", None) or getattr(m, "role", None) or "user"
            text = getattr(m, "text", None)
            if text is None and hasattr(m, "texts"):
                try:
                    text = "\n".join(m.texts or [])
                except Exception:
                    text = str(m)
            oai_messages.append({"role": str(role), "content": text or ""})

        # Convert Haystack tools → OpenAI chat.completions tools schema
        openai_tools = None
        active_tools = tools if tools is not None else self.tools
        if active_tools:
            openai_tools = []
            try:
                from haystack.tools.utils import flatten_tools_or_toolsets

                flat = flatten_tools_or_toolsets(active_tools)
            except Exception:
                flat = list(active_tools) if not isinstance(active_tools, list) else active_tools
            for t in flat or []:
                spec = getattr(t, "tool_spec", None)
                if isinstance(spec, dict) and spec.get("name"):
                    openai_tools.append({"type": "function", "function": {**spec}})
                elif isinstance(t, dict):
                    openai_tools.append(t)

        async def _call():
            return await codex_chat_completion(
                self.access_token,
                oai_messages,
                model=self.model,
                tools=openai_tools,
            )

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        timeout = max(float(settings.LLM_TIMEOUT_SECONDS or 20), 120.0) + 30.0
        if loop and loop.is_running():
            # Haystack Agent.run is sync; bridge from a running loop via a worker thread.
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                payload = pool.submit(lambda: asyncio.run(_call())).result(timeout=timeout)
        else:
            payload = asyncio.run(_call())

        msg = {}
        try:
            msg = payload["choices"][0]["message"] or {}
        except Exception:
            msg = {}

        text = msg.get("content") or ""
        raw_calls = msg.get("tool_calls") or []
        tool_calls = []
        for tc in raw_calls:
            if not isinstance(tc, dict):
                continue
            fn = tc.get("function") or {}
            name = fn.get("name") or ""
            if not name:
                continue
            args_raw = fn.get("arguments") or "{}"
            try:
                args = _json.loads(args_raw) if isinstance(args_raw, str) else (args_raw or {})
            except Exception:
                args = {"_raw": args_raw}
            if not isinstance(args, dict):
                args = {"value": args}
            tool_calls.append(
                ToolCall(tool_name=name, arguments=args, id=tc.get("id"))
            )

        if tool_calls:
            reply = ChatMessage.from_assistant(
                text=text or None,
                tool_calls=tool_calls,
            )
        else:
            reply = ChatMessage.from_assistant(text or " ")
        return {"replies": [reply]}

# Sticky: prefer last successful provider until it fails again.
_preferred_name: Optional[str] = None


@dataclass(frozen=True)
class LLMEndpoint:
    name: str
    model: str
    base_url: Optional[str]
    api_key: str
    source: str = "env"  # chain | auto

    def public_dict(self) -> Dict[str, Any]:
        """Safe for /settings — never expose the key."""
        configured = bool(self.api_key) or self.source == "oauth"
        if self.source == "oauth":
            hint = "chatgpt-oauth"
        else:
            hint = _key_hint(self.api_key)
        return {
            "name": self.name,
            "model": self.model,
            "base_url": self.base_url or "https://api.openai.com/v1",
            "configured": configured,
            "key_hint": hint,
        }


def _key_hint(key: str) -> str:
    if not key or len(key) < 8:
        return "(empty)"
    return f"{key[:4]}…{key[-4:]}"


def _key_ok(value: Optional[str]) -> bool:
    if not value:
        return False
    return value not in ("sk-...", "sk-ant-...", "fc-...", "xai-...", "change-me")


def _resolve_env_key(env_name: str) -> str:
    """Read key from process env first, then Settings attributes."""
    if not env_name:
        return ""
    val = os.environ.get(env_name)
    if val and _key_ok(val):
        return val
    # Fallback: settings field with same name
    attr = getattr(settings, env_name, None)
    if isinstance(attr, str) and _key_ok(attr):
        return attr
    return val or ""


def parse_failover_chain(raw: str) -> List[LLMEndpoint]:
    """Parse LLM_FAILOVER_CHAIN into endpoints (skips hops without a real key)."""
    endpoints: List[LLMEndpoint] = []
    if not raw or not raw.strip():
        return endpoints
    for hop in re.split(r"[;\n]+", raw.strip()):
        hop = hop.strip()
        if not hop or hop.startswith("#"):
            continue
        parts = [p.strip() for p in hop.split("|")]
        if len(parts) < 4:
            logger.warning("llm_chain_skip_malformed", hop=hop)
            continue
        name, model, base_url, env_name = parts[0], parts[1], parts[2], parts[3]
        key = _resolve_env_key(env_name)
        if not _key_ok(key):
            logger.info("llm_chain_skip_no_key", name=name, env=env_name)
            continue
        endpoints.append(
            LLMEndpoint(
                name=name or env_name,
                model=model or settings.LLM_MODEL,
                base_url=base_url or None,
                api_key=key,
                source="chain",
            )
        )
    return endpoints


def auto_endpoints() -> List[LLMEndpoint]:
    """Build chain from individual env slots when no explicit chain is set."""
    out: List[LLMEndpoint] = []

    if _key_ok(settings.OPENAI_API_KEY):
        out.append(
            LLMEndpoint(
                name="openai" if not settings.OPENAI_BASE_URL else "primary",
                model=settings.LLM_MODEL,
                base_url=settings.OPENAI_BASE_URL,
                api_key=settings.OPENAI_API_KEY or "",
                source="auto",
            )
        )

    if _key_ok(settings.OPENCODE_API_KEY):
        out.append(
            LLMEndpoint(
                name="opencode",
                model=settings.OPENCODE_MODEL or "kimi-k3",
                base_url=settings.OPENCODE_BASE_URL or "https://opencode.ai/zen/go/v1",
                api_key=settings.OPENCODE_API_KEY or "",
                source="auto",
            )
        )

    if _key_ok(settings.XAI_API_KEY):
        out.append(
            LLMEndpoint(
                name="xai",
                model=settings.XAI_MODEL or "grok-3-mini",
                base_url=settings.XAI_BASE_URL or "https://api.x.ai/v1",
                api_key=settings.XAI_API_KEY or "",
                source="auto",
            )
        )

    if _key_ok(settings.GEMINI_API_KEY):
        out.append(
            LLMEndpoint(
                name="gemini",
                model=settings.GEMINI_MODEL or "gemini-2.0-flash",
                base_url=settings.GEMINI_BASE_URL
                or "https://generativelanguage.googleapis.com/v1beta/openai/",
                api_key=settings.GEMINI_API_KEY or "",
                source="auto",
            )
        )

    if _key_ok(settings.OPENAI_FALLBACK_API_KEY):
        out.append(
            LLMEndpoint(
                name="openai",
                model=settings.OPENAI_FALLBACK_MODEL or "gpt-4o-mini",
                base_url=None,
                api_key=settings.OPENAI_FALLBACK_API_KEY or "",
                source="auto",
            )
        )

    # Deduplicate by (base_url, model, key prefix)
    seen = set()
    unique: List[LLMEndpoint] = []
    for ep in out:
        sig = (ep.base_url or "", ep.model, ep.api_key[:12])
        if sig in seen:
            continue
        seen.add(sig)
        unique.append(ep)
    return unique


def list_llm_endpoints() -> List[LLMEndpoint]:
    chain = parse_failover_chain(settings.LLM_FAILOVER_CHAIN or "")
    if chain:
        return chain
    return auto_endpoints()


def openai_oauth_endpoint(access_token: str) -> LLMEndpoint:
    """Marker endpoint — build_chat_generator routes this in-process, not over HTTP."""
    return LLMEndpoint(
        name="openai-oauth",
        model=settings.OPENAI_OAUTH_MODEL or "gpt-5.5",
        # Not a real URL. CodexOAuthChatGenerator calls codex_chat_completion directly.
        base_url="codex-oauth",
        api_key=access_token,
        source="oauth",
    )


def with_openai_oauth(access_token: Optional[str]) -> List[LLMEndpoint]:
    eps = list_llm_endpoints()
    if access_token and _key_ok(access_token):
        oauth = openai_oauth_endpoint(access_token)
        # OAuth first; keep env hops as backup
        rest = [e for e in eps if e.name != "openai-oauth"]
        return [oauth] + rest
    return eps


def ordered_endpoints(access_token: Optional[str] = None) -> List[LLMEndpoint]:
    """Prefer last successful provider, then the rest of the chain."""
    global _preferred_name
    eps = with_openai_oauth(access_token)
    if not eps or not _preferred_name:
        return eps
    preferred = [e for e in eps if e.name == _preferred_name]
    rest = [e for e in eps if e.name != _preferred_name]
    return preferred + rest


def build_chat_generator(endpoint: LLMEndpoint):
    # ChatGPT OAuth must not loop back to this same uvicorn worker over HTTP
    # (single-worker deadlock). Call Codex in-process instead.
    if endpoint.name == "openai-oauth" or endpoint.source == "oauth":
        return CodexOAuthChatGenerator(
            access_token=endpoint.api_key,
            model=endpoint.model or settings.OPENAI_OAUTH_MODEL or "gpt-5.5",
        )
    timeout = float(settings.LLM_TIMEOUT_SECONDS or 20.0)
    return OpenAIChatGenerator(
        api_key=Secret.from_token(endpoint.api_key),
        model=endpoint.model,
        api_base_url=endpoint.base_url,
        timeout=timeout,
        max_retries=0,
    )


def is_failoverable_error(exc: BaseException) -> bool:
    """True when another provider might succeed (credits, quota, rate limit, 5xx)."""
    status = getattr(exc, "status_code", None)
    resp = getattr(exc, "response", None)
    if status is None and resp is not None:
        status = getattr(resp, "status_code", None)
    # Nested openai/httpx errors
    body = str(exc)
    cause = getattr(exc, "__cause__", None)
    if cause:
        body = body + " " + str(cause)
    body_l = body.lower()

    if status in (401, 402, 403, 408, 429, 500, 502, 503, 504, 529):
        return True

    markers = (
        "creditserror",
        "insufficient balance",
        "insufficient_quota",
        "insufficient_funds",
        "rate limit",
        "rate_limit",
        "too many requests",
        "overloaded",
        "capacity",
        "billing",
        "quota",
        "unauthorized",
        "invalid_api_key",
        "incorrect api key",
        "model_not_found",
        "does not exist",
        "not available",
        "temporarily unavailable",
        "service unavailable",
        "timeout",
        "timed out",
        "max_time_limit",
        "response incomplete",
        "incomplete_details",
        "connection reset",
        "connection error",
        "502",
        "503",
        "529",
    )
    return any(m in body_l for m in markers)


def mark_success(endpoint: LLMEndpoint) -> None:
    global _preferred_name
    _preferred_name = endpoint.name
    logger.info("llm_provider_selected", name=endpoint.name, model=endpoint.model)


def run_with_llm_failover(
    run_fn, *, operation: str = "agent", access_token: Optional[str] = None
) -> Tuple[Any, LLMEndpoint]:
    """
    Call run_fn(endpoint, chat_generator) for each endpoint until one succeeds.

    run_fn signature: (endpoint: LLMEndpoint, generator: OpenAIChatGenerator) -> Any
    """
    endpoints = ordered_endpoints(access_token=access_token)
    if not endpoints:
        raise ValueError(
            "Δεν έχει ρυθμιστεί κανένα LLM. "
            "Βάλε OPENAI_API_KEY (Platform sk-…) ή OPENCODE_API_KEY, "
            "ή συνδέσου με ChatGPT OAuth από Ρυθμίσεις. "
            "Το Microsoft 365 login δεν μετράει ως LLM."
        )

    errors: List[str] = []
    for ep in endpoints:
        try:
            gen = build_chat_generator(ep)
            logger.info("llm_try", operation=operation, name=ep.name, model=ep.model, base=ep.base_url)
            result = run_fn(ep, gen)
            mark_success(ep)
            return result, ep
        except Exception as e:
            if is_failoverable_error(e):
                msg = f"{ep.name}: {e}"
                errors.append(msg)
                logger.warning(
                    "llm_failover",
                    operation=operation,
                    failed=ep.name,
                    error=str(e)[:300],
                    remaining=[x.name for x in endpoints if x.name != ep.name],
                )
                continue
            # Non-retryable (bad prompt shape, programming error, etc.)
            logger.exception("llm_hard_error", operation=operation, name=ep.name)
            raise

    tried = ", ".join(e.name for e in endpoints)
    logger.error("llm_all_failed", errors=errors[:5], tried=tried)
    # Clear bilingual guidance — Microsoft 365 is NOT an LLM provider.
    raise RuntimeError(
        "Δεν ήταν δυνατή η σύνδεση με κανένα LLM ("
        + tried
        + "). "
        "Η σύνδεση Microsoft 365 δίνει μόνο email/ημερολόγιο — όχι μοντέλο chat. "
        "Για απαντήσεις διάλεξε ένα από: "
        "(1) Ρυθμίσεις → Σύνδεση ChatGPT OAuth, "
        "(2) OPENAI_API_KEY / XAI_API_KEY / GEMINI_API_KEY στο .env, "
        "(3) έγκυρο OPENCODE_API_KEY με credits. "
        "Microsoft 365 ≠ LLM."
    )


def llm_status_public(*, openai_oauth_connected: bool = False) -> Dict[str, Any]:
    """Snapshot for /settings and /health — no secrets."""
    eps = list(list_llm_endpoints())
    if openai_oauth_connected:
        oauth = LLMEndpoint(
            name="openai-oauth",
            model=settings.OPENAI_OAUTH_MODEL or "gpt-5.5",
            base_url="codex-oauth",
            api_key="oauth",
            source="oauth",
        )
        # Show OAuth first so the UI reflects the runtime primary path.
        eps = [oauth] + [e for e in eps if e.name != "openai-oauth"]

    preferred = _preferred_name
    if openai_oauth_connected and not preferred:
        preferred = "openai-oauth"

    active = next((e for e in eps if e.name == preferred), None) or (eps[0] if eps else None)
    return {
        "failover_enabled": len(eps) > 1,
        "endpoint_count": len(eps),
        "preferred": preferred,
        "active_name": active.name if active else None,
        "active_model": active.model if active else None,
        "endpoints": [e.public_dict() for e in eps],
        "chain_configured": bool((settings.LLM_FAILOVER_CHAIN or "").strip())
        or openai_oauth_connected,
        "openai_oauth_connected": openai_oauth_connected,
        "openai_oauth_model": settings.OPENAI_OAUTH_MODEL or "gpt-5.5",
    }
