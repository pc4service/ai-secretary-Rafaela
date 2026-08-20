"""
ChatGPT / Codex OAuth (PKCE) — Sign in with ChatGPT.

Uses the public Codex CLI client so the user can connect their ChatGPT
subscription. Tokens are stored encrypted like Microsoft/Google.

Official Platform API keys remain a separate path (OPENAI_API_KEY).
"""

from __future__ import annotations

import base64
import hashlib
import json
import secrets
import time
from typing import Any, Dict, Optional, Tuple
from urllib.parse import urlencode

import httpx
import structlog

from app.core.config import settings

logger = structlog.get_logger()

CLIENT_ID = "app_EMoamEEZ73f0CkXaXp7hrann"
AUTHORIZE_URL = "https://auth.openai.com/oauth/authorize"
TOKEN_URL = "https://auth.openai.com/oauth/token"
# Codex public client only accepts this loopback callback.
DEFAULT_REDIRECT_URI = "http://localhost:1455/auth/callback"
SCOPE = "openid profile email offline_access"
CODEX_BASE = "https://chatgpt.com/backend-api/codex"

# state -> {verifier, user_id}. Shared across workers: the callback can land on
# a different process than the one that generated the PKCE verifier.
from app.services.state_store import StateStore

_pending = StateStore("openai_oauth", 600)


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _pkce_pair() -> Tuple[str, str]:
    verifier = _b64url(secrets.token_bytes(32))
    challenge = _b64url(hashlib.sha256(verifier.encode("ascii")).digest())
    return verifier, challenge


def redirect_uri() -> str:
    return getattr(settings, "OPENAI_OAUTH_REDIRECT_URI", None) or DEFAULT_REDIRECT_URI


def create_login_url(user_id: str) -> str:
    verifier, challenge = _pkce_pair()
    state = secrets.token_urlsafe(24)
    _pending.put(state, {"verifier": verifier, "user_id": user_id})
    params = {
        "response_type": "code",
        "client_id": CLIENT_ID,
        "redirect_uri": redirect_uri(),
        "scope": SCOPE,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
        "state": state,
        "id_token_add_organizations": "true",
        "codex_cli_simplified_flow": "true",
        "originator": "codex_cli_rs",
    }
    return f"{AUTHORIZE_URL}?{urlencode(params)}"


def pop_pending(state: str) -> Optional[Dict[str, Any]]:
    return _pending.pop(state)


async def exchange_code(code: str, verifier: str) -> Dict[str, Any]:
    async with httpx.AsyncClient(timeout=30.0) as client:
        res = await client.post(
            TOKEN_URL,
            data={
                "grant_type": "authorization_code",
                "client_id": CLIENT_ID,
                "code": code,
                "code_verifier": verifier,
                "redirect_uri": redirect_uri(),
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
    if res.status_code >= 400:
        logger.warning("openai_oauth_exchange_failed", status=res.status_code, body=res.text[:400])
        raise ValueError(f"OpenAI OAuth token exchange failed ({res.status_code})")
    data = res.json()
    if not data.get("access_token"):
        raise ValueError("OpenAI OAuth response missing access_token")
    return data


async def refresh_access_token(refresh_token: str) -> Dict[str, Any]:
    async with httpx.AsyncClient(timeout=30.0) as client:
        res = await client.post(
            TOKEN_URL,
            data={
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
                "client_id": CLIENT_ID,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
    if res.status_code >= 400:
        logger.warning("openai_oauth_refresh_failed", status=res.status_code, body=res.text[:400])
        raise ValueError(f"OpenAI OAuth refresh failed ({res.status_code})")
    data = res.json()
    if not data.get("access_token"):
        raise ValueError("OpenAI OAuth refresh missing access_token")
    return data


def decode_jwt_payload(token: str) -> Dict[str, Any]:
    try:
        payload = token.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        return json.loads(base64.urlsafe_b64decode(payload))
    except Exception:
        return {}


def chatgpt_account_id(access_token: str) -> Optional[str]:
    claims = decode_jwt_payload(access_token)
    auth = claims.get("https://api.openai.com/auth") or {}
    if isinstance(auth, dict):
        return auth.get("chatgpt_account_id") or auth.get("chatgpt_account_id".replace("_", ""))
    return claims.get("chatgpt_account_id")


def oauth_headers(access_token: str) -> Dict[str, str]:
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
        "originator": "codex_cli_rs",
        "User-Agent": "codex_cli_rs/0.50.0",
    }
    account = chatgpt_account_id(access_token)
    if account:
        headers["ChatGPT-Account-ID"] = account
    return headers


def _extract_output_text(payload: Dict[str, Any]) -> str:
    if isinstance(payload.get("output_text"), str) and payload["output_text"]:
        return payload["output_text"]
    parts: list[str] = []
    for item in payload.get("output") or []:
        if not isinstance(item, dict):
            continue
        if item.get("type") in ("message", "output_text") or item.get("role") == "assistant":
            content = item.get("content") or item.get("text") or ""
            if isinstance(content, str):
                parts.append(content)
            elif isinstance(content, list):
                for c in content:
                    if isinstance(c, dict):
                        parts.append(c.get("text") or c.get("output_text") or "")
                    elif isinstance(c, str):
                        parts.append(c)
    if parts:
        return "".join(parts)
    # SSE-style fallback if someone returned a string body
    return ""


def _parse_codex_sse(raw: str) -> tuple[str, str, list[dict[str, Any]], Optional[str]]:
    """Parse Codex Responses SSE → (response_id, text, tool_calls, incomplete_reason)."""
    response_id = "codex-oauth"
    text_parts: list[str] = []
    final_text = ""
    incomplete_reason: Optional[str] = None
    # call_id / item_id → accumulating tool call
    tool_by_id: Dict[str, Dict[str, Any]] = {}

    def _harvest_response(resp: dict) -> None:
        nonlocal response_id, final_text, incomplete_reason
        if resp.get("id"):
            response_id = str(resp["id"])
        status = str(resp.get("status") or "")
        if status == "incomplete":
            details = resp.get("incomplete_details") or {}
            if isinstance(details, dict):
                incomplete_reason = str(details.get("reason") or "incomplete")
            else:
                incomplete_reason = "incomplete"
        extracted = _extract_output_text(resp)
        if extracted:
            final_text = extracted
        for item in resp.get("output") or []:
            if not isinstance(item, dict):
                continue
            if item.get("type") == "function_call":
                cid = item.get("call_id") or item.get("id") or ""
                tool_by_id[str(cid)] = {
                    "id": str(cid),
                    "type": "function",
                    "function": {
                        "name": item.get("name") or "",
                        "arguments": item.get("arguments") or "{}",
                    },
                }

    for block in raw.split("\n\n"):
        data_lines = [
            line[5:].strip()
            for line in block.splitlines()
            if line.startswith("data:")
        ]
        if not data_lines:
            continue
        payload_raw = "\n".join(data_lines).strip()
        if not payload_raw or payload_raw == "[DONE]":
            continue
        try:
            event = json.loads(payload_raw)
        except json.JSONDecodeError:
            continue
        if not isinstance(event, dict):
            continue

        etype = event.get("type") or ""
        if etype in (
            "response.created",
            "response.completed",
            "response.in_progress",
            "response.incomplete",
            "response.failed",
        ):
            resp = event.get("response") or {}
            if isinstance(resp, dict):
                if resp.get("id"):
                    response_id = str(resp["id"])
                if etype in ("response.completed", "response.incomplete", "response.failed"):
                    _harvest_response(resp)
                # Some streams only set status on the event wrapper
                if etype == "response.incomplete" and not incomplete_reason:
                    incomplete_reason = "max_time_limit"
                if etype == "response.failed":
                    err = event.get("response") or event.get("error") or {}
                    if isinstance(err, dict):
                        incomplete_reason = str(
                            err.get("code") or err.get("message") or "failed"
                        )[:120]
        elif etype == "response.output_text.delta":
            delta = event.get("delta")
            if isinstance(delta, str) and delta:
                text_parts.append(delta)
        elif etype == "response.output_text.done":
            done_text = event.get("text")
            if isinstance(done_text, str) and done_text:
                final_text = done_text
        elif etype == "response.output_item.added":
            item = event.get("item") or {}
            if isinstance(item, dict) and item.get("type") == "function_call":
                cid = str(item.get("call_id") or item.get("id") or "")
                tool_by_id[cid] = {
                    "id": cid,
                    "type": "function",
                    "function": {
                        "name": item.get("name") or "",
                        "arguments": item.get("arguments") or "",
                    },
                }
        elif etype == "response.function_call_arguments.delta":
            item_id = str(event.get("item_id") or "")
            # Map item_id → existing entry if call_id differs
            target = None
            for key, tc in tool_by_id.items():
                if key == item_id or tc.get("_item_id") == item_id:
                    target = tc
                    break
            if target is None and item_id:
                # create placeholder under item_id; later done event may rename
                target = tool_by_id.setdefault(
                    item_id,
                    {
                        "id": item_id,
                        "type": "function",
                        "function": {"name": "", "arguments": ""},
                        "_item_id": item_id,
                    },
                )
            if target is not None:
                delta = event.get("delta") or ""
                if isinstance(delta, str):
                    target["function"]["arguments"] = (
                        target["function"].get("arguments") or ""
                    ) + delta
        elif etype in ("response.function_call_arguments.done", "response.output_item.done"):
            item = event.get("item") if etype == "response.output_item.done" else None
            if isinstance(item, dict) and item.get("type") == "function_call":
                cid = str(item.get("call_id") or item.get("id") or "")
                tool_by_id[cid] = {
                    "id": cid,
                    "type": "function",
                    "function": {
                        "name": item.get("name") or "",
                        "arguments": item.get("arguments") or "{}",
                    },
                }
            elif etype == "response.function_call_arguments.done":
                item_id = str(event.get("item_id") or "")
                args = event.get("arguments")
                for key, tc in list(tool_by_id.items()):
                    if key == item_id or tc.get("_item_id") == item_id:
                        if isinstance(args, str):
                            tc["function"]["arguments"] = args
                        break

    text = final_text or "".join(text_parts)
    tool_calls: list[dict[str, Any]] = []
    for tc in tool_by_id.values():
        fn = tc.get("function") or {}
        name = fn.get("name") or ""
        if not name:
            continue
        args = fn.get("arguments") or "{}"
        tool_calls.append(
            {
                "id": tc.get("id") or f"call_{len(tool_calls)+1}",
                "type": "function",
                "function": {"name": name, "arguments": args},
            }
        )
    return response_id, text, tool_calls, incomplete_reason


def _messages_to_responses_input(messages: list) -> tuple[Optional[str], list]:
    """Convert OpenAI chat.completions messages → Responses API input + instructions."""
    input_items: list = []
    instructions: Optional[str] = None

    for m in messages or []:
        if not isinstance(m, dict):
            continue
        role = m.get("role") or "user"
        content = m.get("content")

        if role == "system":
            if instructions is None and isinstance(content, str):
                instructions = content
            elif isinstance(content, str):
                instructions = (instructions or "") + "\n" + content
            continue

        # Assistant with tool_calls (OpenAI chat format)
        if role == "assistant" and m.get("tool_calls"):
            for tc in m.get("tool_calls") or []:
                if not isinstance(tc, dict):
                    continue
                fn = tc.get("function") or {}
                input_items.append(
                    {
                        "type": "function_call",
                        "call_id": tc.get("id") or f"call_{len(input_items)}",
                        "name": fn.get("name") or "",
                        "arguments": fn.get("arguments") or "{}",
                    }
                )
            if isinstance(content, str) and content.strip():
                input_items.append({"role": "assistant", "content": content})
            continue

        # Tool result
        if role == "tool":
            call_id = m.get("tool_call_id") or m.get("id") or ""
            out = content if isinstance(content, str) else json.dumps(content, ensure_ascii=False)
            input_items.append(
                {
                    "type": "function_call_output",
                    "call_id": call_id,
                    "output": out or "",
                }
            )
            continue

        if role in ("user", "assistant"):
            if content is None:
                content = ""
            if not isinstance(content, str):
                content = json.dumps(content, ensure_ascii=False)
            input_items.append({"role": role, "content": content})
            continue

        # Fallback
        input_items.append(
            {"role": "user", "content": content if isinstance(content, str) else str(content)}
        )

    return instructions, input_items


def _openai_tools_to_responses(tools: Optional[list]) -> list:
    """chat.completions tools[] → Responses API tools[]."""
    out: list = []
    for t in tools or []:
        if not isinstance(t, dict):
            continue
        if t.get("type") == "function" and isinstance(t.get("function"), dict):
            fn = t["function"]
            out.append(
                {
                    "type": "function",
                    "name": fn.get("name") or "",
                    "description": fn.get("description") or "",
                    "parameters": fn.get("parameters") or {"type": "object", "properties": {}},
                }
            )
        elif t.get("type") == "function" and t.get("name"):
            # already responses-shaped
            out.append(t)
        elif t.get("name") and t.get("parameters") is not None:
            out.append(
                {
                    "type": "function",
                    "name": t.get("name") or "",
                    "description": t.get("description") or "",
                    "parameters": t.get("parameters") or {"type": "object", "properties": {}},
                }
            )
    return [x for x in out if x.get("name")]


async def codex_chat_completion(
    access_token: str,
    messages: list,
    model: Optional[str] = None,
    tools: Optional[list] = None,
    tool_choice: Optional[Any] = None,
) -> Dict[str, Any]:
    """Call Codex Responses API and return an OpenAI chat.completions-shaped dict.

    ChatGPT Codex currently requires stream=true and store=false.
    Supports function tools so Haystack Agent can read mail/calendar.
    """
    model = model or getattr(settings, "OPENAI_OAUTH_MODEL", None) or "gpt-5.5"
    instructions, input_items = _messages_to_responses_input(messages)

    body: Dict[str, Any] = {
        "model": model,
        "input": input_items or [{"role": "user", "content": "Hello"}],
        "stream": True,
        "store": False,
    }
    if instructions:
        body["instructions"] = instructions

    responses_tools = _openai_tools_to_responses(tools)
    if responses_tools:
        body["tools"] = responses_tools
        if tool_choice is not None:
            body["tool_choice"] = tool_choice

    # Reasoning models may hit OpenAI *server* max_time_limit; keep client timeout higher.
    timeout = max(float(settings.LLM_TIMEOUT_SECONDS or 20), 180.0)
    # Lower reasoning effort reduces incomplete/max_time_limit on gpt-5.x (when supported).
    effort = (getattr(settings, "OPENAI_OAUTH_REASONING_EFFORT", None) or "").strip().lower()
    if effort in ("low", "medium", "high", "minimal"):
        body["reasoning"] = {"effort": effort}

    headers = oauth_headers(access_token)
    headers["Accept"] = "text/event-stream"

    async with httpx.AsyncClient(timeout=timeout) as client:
        res = await client.post(
            f"{CODEX_BASE}/responses",
            headers=headers,
            json=body,
        )
    if res.status_code >= 400:
        logger.warning("codex_responses_failed", status=res.status_code, body=res.text[:500])
        raise ValueError(
            f"ChatGPT OAuth request failed ({res.status_code}): {res.text[:200]}"
        )

    response_id, text, tool_calls, incomplete_reason = _parse_codex_sse(res.text)

    # Server cut the run short (common with heavy reasoning + many tools).
    if incomplete_reason:
        logger.warning(
            "codex_response_incomplete",
            reason=incomplete_reason,
            has_text=bool((text or "").strip()),
            tool_calls=len(tool_calls or []),
            model=model,
        )
        # Prefer partial tool calls / text so the agent can continue when possible.
        if not (text or "").strip() and not tool_calls:
            # Failoverable — llm_router treats "timeout" / incomplete as retryable.
            raise ValueError(
                f"Response incomplete: {incomplete_reason}. "
                "Try OPENAI_OAUTH_REASONING_EFFORT=low, fewer tools, or a backup LLM."
            )

    message: Dict[str, Any] = {"role": "assistant", "content": text or (None if tool_calls else " ")}
    if tool_calls:
        message["tool_calls"] = tool_calls
        finish_reason = "tool_calls"
    else:
        if not message.get("content"):
            message["content"] = " "
        finish_reason = "length" if incomplete_reason else "stop"

    return {
        "id": response_id,
        "object": "chat.completion",
        "model": model,
        "choices": [
            {
                "index": 0,
                "message": message,
                "finish_reason": finish_reason,
            }
        ],
        "_incomplete_reason": incomplete_reason,
    }
