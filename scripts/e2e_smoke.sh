#!/usr/bin/env bash
# E2E smoke: health → demo login → knowledge search → chat (optional RAG question)
# Requires: stack running on localhost:8000
set -euo pipefail

API="${API_BASE:-http://localhost:8000}"
COOKIE_JAR="$(mktemp)"
trap 'rm -f "$COOKIE_JAR"' EXIT

echo "=== 1. Health ==="
HEALTH=$(curl -sf "$API/health")
echo "$HEALTH"
echo "$HEALTH" | grep -q '"status"' || { echo "FAIL: health"; exit 1; }

echo ""
echo "=== 2. Login providers ==="
curl -sf "$API/api/v1/login/providers" | tee /tmp/rafaela_providers.json
echo ""

echo ""
echo "=== 3. Demo login (sets session cookie) ==="
curl -sf -c "$COOKIE_JAR" -X POST "$API/api/v1/login/demo" | tee /tmp/rafaela_demo.json
echo ""
grep -q demo-user /tmp/rafaela_demo.json || echo "WARN: demo response unexpected"

echo ""
echo "=== 4. /login/me ==="
ME=$(curl -sf -b "$COOKIE_JAR" "$API/api/v1/login/me")
echo "$ME"
echo "$ME" | grep -q '"authenticated":true\|"authenticated": true' || {
  echo "FAIL: not authenticated after demo login"
  exit 1
}

echo ""
echo "=== 5. Knowledge search (keyword/RAG) ==="
SEARCH=$(curl -sf -b "$COOKIE_JAR" --get "$API/api/v1/knowledge/search" --data-urlencode "q=follow-up συνάντηση")
echo "$SEARCH" | head -c 800
echo ""
echo "$SEARCH" | grep -qi "follow\|συνάντηση\|πρότυπο\|template\|knowledge\|αποτέλεσμα\|result\|δεν βρέθηκαν" || {
  echo "FAIL: knowledge search empty/error"
  exit 1
}

echo ""
echo "=== 6. Settings (auth required) ==="
curl -sf -b "$COOKIE_JAR" "$API/api/v1/settings" | tee /tmp/rafaela_settings.json
echo ""

echo ""
echo "=== 7. Chat (may take a few seconds; needs OPENAI_API_KEY) ==="
if curl -sf -b "$COOKIE_JAR" -X POST "$API/api/v1/chat" \
  -H "Content-Type: application/json" \
  -d '{"message":"Ποιο πρότυπο follow-up χρησιμοποιούμε μετά από συνάντηση; Απάντησε σύντομα."}' \
  -o /tmp/rafaela_chat.json; then
  head -c 1200 /tmp/rafaela_chat.json
  echo ""
  grep -q '"reply"' /tmp/rafaela_chat.json && echo "OK: chat replied" || echo "WARN: chat response shape unexpected"
else
  echo "WARN: chat failed (missing OPENAI_API_KEY or agent error). Auth+knowledge still OK."
fi

echo ""
echo "=== 8. Unauthorized without cookie ==="
CODE=$(curl -s -o /dev/null -w "%{http_code}" "$API/api/v1/settings")
if [ "$CODE" = "401" ] || [ "$CODE" = "403" ]; then
  echo "OK: settings without cookie → $CODE"
else
  echo "WARN: expected 401 without cookie, got $CODE (REQUIRE_AUTH may be false)"
fi

echo ""
echo "=== E2E smoke finished ==="
