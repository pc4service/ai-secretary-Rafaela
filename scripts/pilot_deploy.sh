#!/usr/bin/env bash
# Pilot deploy helper — run ON the target host (Proxmox VM or VPS)
#
#   ./scripts/pilot_deploy.sh check   # validate .env.prod only
#   ./scripts/pilot_deploy.sh up      # build & start
#   ./scripts/pilot_deploy.sh status
#   ./scripts/pilot_deploy.sh smoke
#   ./scripts/pilot_deploy.sh backup  # pg_dump to ./backups/
#   ./scripts/pilot_deploy.sh down | logs
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

COMPOSE=(docker compose -f docker-compose.prod.yml --env-file .env.prod)
CMD="${1:-up}"
API="${API_BASE:-http://127.0.0.1:8000}"

die() { echo "ERROR: $*" >&2; exit 1; }
info() { echo "=== $* ==="; }

if [[ ! -f .env.prod ]]; then
  cp .env.prod.example .env.prod
  echo "Created .env.prod from example."
  echo "Edit it (SECRET_KEY, POSTGRES_PASSWORD, URLs, keys) then re-run."
  exit 1
fi

# --- .env.prod validation (no secrets printed) ---
env_get() {
  # last non-comment assignment wins
  grep -E "^${1}=" .env.prod 2>/dev/null | tail -1 | cut -d= -f2- | sed 's/\r$//' || true
}

env_nonempty() {
  local v
  v="$(env_get "$1")"
  [[ -n "$v" ]]
}

env_looks_placeholder() {
  local v
  v="$(env_get "$1")"
  [[ -z "$v" || "$v" == CHANGE_ME* || "$v" == *CHANGE_ME* || "$v" == "sk-..." || "$v" == yourdomain.com* || "$v" == *example.com* ]]
}

check_env() {
  local errors=0 warns=0
  info "Validating .env.prod"

  for k in SECRET_KEY POSTGRES_PASSWORD DATABASE_URL FRONTEND_URL NEXT_PUBLIC_API_URL; do
    if ! env_nonempty "$k"; then
      echo "FAIL: $k is empty"
      errors=$((errors + 1))
    elif env_looks_placeholder "$k"; then
      echo "FAIL: $k still looks like a placeholder"
      errors=$((errors + 1))
    else
      echo "OK:   $k set"
    fi
  done

  local env_val dry req cookie hops front api
  env_val="$(env_get ENVIRONMENT)"
  dry="$(env_get DRY_RUN)"
  req="$(env_get REQUIRE_AUTH)"
  cookie="$(env_get COOKIE_SECURE)"
  hops="$(env_get TRUSTED_PROXY_HOPS)"
  front="$(env_get FRONTEND_URL)"
  api="$(env_get NEXT_PUBLIC_API_URL)"

  [[ "${env_val,,}" == "production" ]] || {
    echo "FAIL: ENVIRONMENT must be production (got '${env_val:-empty}')"
    errors=$((errors + 1))
  }
  [[ "${dry,,}" == "true" || "${dry,,}" == "false" ]] || {
    echo "FAIL: DRY_RUN must be true|false"
    errors=$((errors + 1))
  }
  if [[ "${dry,,}" != "true" ]]; then
    echo "WARN: DRY_RUN is not true — real writes may execute after HITL approve"
    warns=$((warns + 1))
  else
    echo "OK:   DRY_RUN=true (pilot-safe)"
  fi
  if [[ "${req,,}" != "true" ]]; then
    echo "WARN: REQUIRE_AUTH is not true (production still forces auth, but set it explicitly)"
    warns=$((warns + 1))
  else
    echo "OK:   REQUIRE_AUTH=true"
  fi
  if [[ "${cookie,,}" != "true" ]]; then
    echo "FAIL: COOKIE_SECURE must be true behind HTTPS"
    errors=$((errors + 1))
  else
    echo "OK:   COOKIE_SECURE=true"
  fi
  if [[ -z "$hops" || "$hops" == "0" ]]; then
    echo "WARN: TRUSTED_PROXY_HOPS=0 — behind nginx set 1 (or 2 with Cloudflare)"
    warns=$((warns + 1))
  else
    echo "OK:   TRUSTED_PROXY_HOPS=$hops"
  fi
  if [[ "$front" != https://* ]]; then
    echo "FAIL: FRONTEND_URL should be https://… for pilot"
    errors=$((errors + 1))
  fi
  if [[ "$api" != https://* ]]; then
    echo "FAIL: NEXT_PUBLIC_API_URL should be https://… for pilot"
    errors=$((errors + 1))
  fi

  # At least one LLM path
  if env_looks_placeholder OPENAI_API_KEY && ! env_nonempty OPENCODE_API_KEY; then
    echo "WARN: no OPENAI_API_KEY / OPENCODE_API_KEY — pilot needs ChatGPT OAuth per user or a Platform key"
    warns=$((warns + 1))
  else
    echo "OK:   LLM key slot present (or non-placeholder)"
  fi

  local sk
  sk="$(env_get SECRET_KEY)"
  if [[ ${#sk} -lt 32 ]]; then
    echo "FAIL: SECRET_KEY shorter than 32 chars"
    errors=$((errors + 1))
  fi

  echo ""
  echo "Summary: $errors error(s), $warns warning(s)"
  [[ "$errors" -eq 0 ]] || die "fix .env.prod and re-run"
}

case "$CMD" in
  check)
    check_env
    echo "Env check passed."
    ;;
  up)
    check_env
    info "Building & starting pilot stack"
    "${COMPOSE[@]}" up -d --build
    info "Waiting for backend health on $API"
    for _ in $(seq 1 45); do
      if curl -sf "$API/health" >/dev/null 2>&1; then
        echo "Backend healthy:"
        curl -s "$API/health"
        echo ""
        curl -s "$API/api/v1/knowledge/status" | head -c 500 || true
        echo ""
        exit 0
      fi
      sleep 2
    done
    echo "ERROR: backend not healthy in time" >&2
    "${COMPOSE[@]}" logs --tail=50 backend || true
    exit 1
    ;;
  status)
    "${COMPOSE[@]}" ps
    curl -sf "$API/health" || echo "health failed"
    echo ""
    curl -sf "$API/api/v1/knowledge/status" || echo "knowledge/status failed"
    echo ""
    ;;
  smoke)
    info "Smoke against $API"
    API_BASE="$API" ./scripts/e2e_smoke.sh
    ;;
  backup)
    mkdir -p backups
    STAMP="$(date +%Y%m%d_%H%M%S)"
    OUT="backups/secretary_${STAMP}.sql"
    info "Postgres dump → $OUT"
    "${COMPOSE[@]}" exec -T db \
      pg_dump -U "${POSTGRES_USER:-secretary}" "${POSTGRES_DB:-secretary}" >"$OUT"
    ls -lh "$OUT"
    # keep last 14 dumps
    ls -1t backups/secretary_*.sql 2>/dev/null | tail -n +15 | xargs -r rm -f
    ;;
  down)
    "${COMPOSE[@]}" down
    ;;
  logs)
    "${COMPOSE[@]}" logs -f --tail=100
    ;;
  *)
    echo "Usage: $0 {check|up|status|smoke|backup|down|logs}"
    exit 1
    ;;
esac
