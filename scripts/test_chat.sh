#!/bin/bash
# Simple smoke test for the AI Secretary Agent

set -e

BASE_URL=${BASE_URL:-http://localhost:8000}

echo "=== Health check ==="
curl -s "$BASE_URL/health" | python3 -m json.tool

echo ""
echo "=== System prompt (truncated) ==="
curl -s "$BASE_URL/api/v1/system-prompt" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['system_prompt'][:400] + '...')"

echo ""
echo "=== Chat test (Greek) ==="
curl -s -X POST "$BASE_URL/api/v1/chat" \
  -H "Content-Type: application/json" \
  -d '{"message": "Γεια σου Αλέξ! Παρουσιάσου σύντομα και πες μου αν είσαι σε dry-run mode."}' \
  | python3 -m json.tool

echo ""
echo "Done."
