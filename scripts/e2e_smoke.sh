#!/usr/bin/env bash
# E2E smoke: health → session → knowledge → guards → chat (if LLM available)
# Works on trial (demo login) and production (skips demo when 403).
#
#   ./scripts/e2e_smoke.sh
#   API_BASE=https://api.example.com ./scripts/e2e_smoke.sh
set -euo pipefail

API="${API_BASE:-http://localhost:8000}"
COOKIE_JAR="$(mktemp)"
trap 'rm -f "$COOKIE_JAR"' EXIT
FAILS=0

# Prefer a real interpreter. On Windows, `python3` may be the Store stub.
PYTHON=""
for cand in python3 python py; do
  if command -v "$cand" >/dev/null 2>&1 && "$cand" -c "import json" >/dev/null 2>&1; then
    PYTHON="$cand"
    break
  fi
done

pass() { echo "OK:  $*"; }
warn() { echo "WARN: $*"; }
fail() { echo "FAIL: $*"; FAILS=$((FAILS + 1)); }

py() {
  [[ -n "$PYTHON" ]] || return 1
  "$PYTHON" "$@"
}

echo "=== 1. Health ($API) ==="
if ! HEALTH=$(curl -sf "$API/health"); then
  fail "health unreachable"
  echo "Smoke aborted."
  exit 1
fi
echo "$HEALTH"
echo "$HEALTH" | grep -q '"status"' && pass "health status present" || fail "health shape"
DRY=$(echo "$HEALTH" | py -c "import sys,json; print(json.load(sys.stdin).get('dry_run'))" 2>/dev/null || echo "?")
ENV=$(echo "$HEALTH" | py -c "import sys,json; print(json.load(sys.stdin).get('environment'))" 2>/dev/null || echo "?")
echo "     environment=$ENV dry_run=$DRY"
if [[ "$ENV" == "production" && "$DRY" != "True" && "$DRY" != "true" ]]; then
  warn "production with dry_run=$DRY — confirm this is intentional"
fi

echo ""
echo "=== 2. Login providers ==="
curl -sf "$API/api/v1/login/providers" | tee /tmp/rafaela_providers.json
echo ""

echo ""
echo "=== 3. Session (demo if allowed) ==="
DEMO_CODE=$(curl -s -o /tmp/rafaela_demo.json -w "%{http_code}" -c "$COOKIE_JAR" -X POST "$API/api/v1/login/demo")
if [[ "$DEMO_CODE" == "200" ]]; then
  pass "demo login"
  grep -q demo-user /tmp/rafaela_demo.json || warn "demo body unexpected"
elif [[ "$DEMO_CODE" == "403" ]]; then
  warn "demo login disabled (expected in production) — remaining checks need an existing session cookie"
  if [[ -n "${RAFAELA_COOKIE:-}" ]]; then
    echo "$RAFAELA_COOKIE" >"$COOKIE_JAR"
    pass "using RAFAELA_COOKIE from env"
  else
    warn "set RAFAELA_COOKIE='rafaela_session=…' to test authenticated routes on production"
  fi
else
  fail "demo login HTTP $DEMO_CODE"
fi

echo ""
echo "=== 4. /login/me ==="
if ME=$(curl -sf -b "$COOKIE_JAR" "$API/api/v1/login/me"); then
  echo "$ME"
  echo "$ME" | grep -q '"authenticated": *true' && pass "authenticated session" || warn "not authenticated — skip authz tests"
else
  warn "/login/me failed (no session)"
  ME=""
fi
AUTHED=0
echo "${ME:-}" | grep -q '"authenticated": *true' && AUTHED=1 || true

echo ""
echo "=== 5. Knowledge status (public) ==="
KS=$(curl -sf "$API/api/v1/knowledge/status") || { fail "knowledge/status"; KS="{}"; }
echo "$KS" | head -c 400; echo
echo "$KS" | grep -q 'file_count\|chunk_count' && pass "knowledge status" || fail "knowledge status shape"

echo ""
echo "=== 6. Knowledge search (auth) ==="
if [[ "$AUTHED" -eq 1 ]]; then
  # ASCII query avoids Windows/locale curl encoding issues
  SEARCH=$(curl -sf -b "$COOKIE_JAR" --get "$API/api/v1/knowledge/search" --data-urlencode "q=follow-up meeting")
  echo "$SEARCH" | head -c 600; echo
  echo "$SEARCH" | grep -qi "follow\|meeting\|template\|email\|count" \
    && pass "knowledge search" || fail "knowledge search empty/error"
else
  warn "skip knowledge search (no session)"
fi

echo ""
echo "=== 7. Settings ==="
if [[ "$AUTHED" -eq 1 ]]; then
  curl -sf -b "$COOKIE_JAR" "$API/api/v1/settings" | tee /tmp/rafaela_settings.json | head -c 500
  echo ""
  pass "settings with session"
else
  warn "skip settings (no session)"
fi

echo ""
echo "=== 8. Anonymous guards ==="
code=$(curl -s -o /dev/null -w "%{http_code}" "$API/api/v1/actions/pending")
[[ "$code" == "401" ]] && pass "actions/pending → 401" || fail "actions/pending expected 401 got $code"

code=$(curl -s -o /dev/null -w "%{http_code}" "$API/api/v1/knowledge/search?q=x")
[[ "$code" == "401" ]] && pass "knowledge/search → 401" || fail "knowledge/search expected 401 got $code"

code=$(curl -s -o /dev/null -w "%{http_code}" "$API/api/v1/system-prompt")
[[ "$code" == "401" ]] && pass "system-prompt → 401" || fail "system-prompt expected 401 got $code"

code=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$API/internal/codex/v1/chat/completions" \
  -H 'Content-Type: application/json' -d '{}')
[[ "$code" == "404" ]] && pass "internal codex → 404" || fail "internal codex expected 404 got $code"

code=$(curl -s -o /dev/null -w "%{http_code}" "$API/api/v1/settings")
if [[ "$code" == "401" || "$code" == "403" ]]; then
  pass "settings without cookie → $code"
elif [[ "$ENV" == "production" ]]; then
  fail "settings without cookie expected 401 in production, got $code"
else
  warn "settings without cookie → $code (demo fallback OK outside production)"
fi

if [[ "$ENV" == "production" ]]; then
  code=$(curl -s -o /dev/null -w "%{http_code}" "$API/docs")
  [[ "$code" == "404" ]] && pass "docs closed in production" || warn "docs HTTP $code (expected 404 in production)"
fi

echo ""
echo "=== 9. Chat (optional LLM) ==="
if [[ "$AUTHED" -eq 1 ]]; then
  # ASCII-only body so curl works on Windows codepages; file avoids quoting issues.
  CHAT_BODY="$(mktemp)"
  CHAT_OUT="$(mktemp)"
  printf '%s' '{"message":"Reply in one short English sentence: confirm you are Rafaela."}' >"$CHAT_BODY"
  CHAT_CODE=$(curl -s -o "$CHAT_OUT" -w "%{http_code}" -b "$COOKIE_JAR" -X POST "$API/api/v1/chat" \
    -H "Content-Type: application/json" \
    --data-binary "@$CHAT_BODY" || echo "000")
  head -c 400 "$CHAT_OUT"; echo
  if [[ "$CHAT_CODE" == "200" ]] && grep -q '"reply"' "$CHAT_OUT"; then
    pass "chat replied (HTTP $CHAT_CODE)"
  else
    warn "chat failed HTTP ${CHAT_CODE} (no LLM credits/key or agent error) — auth+knowledge still counted"
  fi
  rm -f "$CHAT_BODY" "$CHAT_OUT"
else
  warn "skip chat (no session)"
fi

echo ""
if [[ "$FAILS" -gt 0 ]]; then
  echo "=== E2E smoke FINISHED WITH $FAILS FAILURE(S) ==="
  exit 1
fi
echo "=== E2E smoke finished OK ==="
