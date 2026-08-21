#!/usr/bin/env bash
# Local production-mode stack (your machine, HTTP on 127.0.0.1)
#
#   ./scripts/local_prod.sh init    # create .env.prod from template + .env secrets
#   ./scripts/local_prod.sh up      # stop dev compose, build & start prod.local
#   ./scripts/local_prod.sh down    # stop prod local
#   ./scripts/local_prod.sh status
#   ./scripts/local_prod.sh logs
#   ./scripts/local_prod.sh dev     # stop prod local, start normal docker-compose
#
# Notes:
#   - Demo login is disabled (production). Use Microsoft Sign-in.
#   - COOKIE_SECURE=false (HTTP). For real HTTPS use tunnel/VPS.
#   - DRY_RUN=true by default — calendar writes stay simulated.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

COMPOSE_PROD=(
  docker compose
  -f docker-compose.prod.yml
  -f docker-compose.prod.local.yml
  --env-file .env.prod
)
COMPOSE_DEV=(docker compose -f docker-compose.yml)
CMD="${1:-up}"
API="${API_BASE:-http://127.0.0.1:8000}"

info() { echo "=== $* ==="; }
die() { echo "ERROR: $*" >&2; exit 1; }

env_get_file() {
  local file="$1" key="$2"
  grep -E "^${key}=" "$file" 2>/dev/null | tail -1 | cut -d= -f2- | tr -d '\r' || true
}

# Upsert KEY=VALUE in .env.prod (Python for Windows/Git Bash safety)
set_env_key() {
  KEY="$1" VAL="$2" python - <<'PY'
import os
from pathlib import Path
key, val = os.environ["KEY"], os.environ["VAL"]
path = Path(".env.prod")
lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
out, found = [], False
for line in lines:
    if line.startswith(key + "="):
        out.append(f"{key}={val}")
        found = True
    else:
        out.append(line)
if not found:
    out.append(f"{key}={val}")
path.write_text("\n".join(out) + "\n", encoding="utf-8")
PY
}

gen_secret() {
  python -c "import secrets; print(secrets.token_hex(32))"
}

cmd_init() {
  info "Init .env.prod for local production"
  if [[ ! -f .env.prod ]]; then
    cp .env.prod.local.example .env.prod
    echo "Created .env.prod from .env.prod.local.example"
  else
    echo ".env.prod exists — filling missing secrets / forcing local-safe flags"
  fi

  sk="$(env_get_file .env.prod SECRET_KEY)"
  if [[ -z "$sk" || "$sk" == CHANGE_ME* ]]; then
    set_env_key SECRET_KEY "$(gen_secret)"
    echo "OK: generated SECRET_KEY"
  else
    echo "OK: SECRET_KEY already set"
  fi

  pp="$(env_get_file .env.prod POSTGRES_PASSWORD)"
  if [[ -z "$pp" || "$pp" == CHANGE_ME* ]]; then
    pp="$(python -c "import secrets; print(secrets.token_hex(12))")"
    set_env_key POSTGRES_PASSWORD "$pp"
    set_env_key DATABASE_URL "postgresql+asyncpg://secretary:${pp}@db:5432/secretary"
    echo "OK: generated POSTGRES_PASSWORD + DATABASE_URL"
  else
    echo "OK: POSTGRES_PASSWORD already set"
  fi

  if [[ -f .env ]]; then
    for k in \
      OPENAI_API_KEY OPENCODE_API_KEY OPENCODE_BASE_URL OPENCODE_MODEL \
      OPENAI_OAUTH_MODEL OPENAI_OAUTH_REASONING_EFFORT \
      MS_CLIENT_ID MS_CLIENT_SECRET MS_TENANT_ID \
      GOOGLE_CLIENT_ID GOOGLE_CLIENT_SECRET \
      FIRECRAWL_API_KEY LLM_FAILOVER_CHAIN
    do
      cur="$(env_get_file .env.prod "$k")"
      src="$(env_get_file .env "$k")"
      if [[ -z "$cur" || "$cur" == CHANGE_ME* || "$cur" == "sk-..." || "$cur" == "fc-..." ]]; then
        if [[ -n "$src" && "$src" != "sk-..." && "$src" != "fc-..." ]]; then
          set_env_key "$k" "$src"
          echo "OK: copied $k from .env"
        fi
      fi
    done
  fi

  set_env_key ENVIRONMENT production
  set_env_key DEBUG false
  set_env_key DRY_RUN true
  set_env_key REQUIRE_AUTH true
  set_env_key COOKIE_SECURE false
  # IMPORTANT: use one hostname everywhere. Mixing localhost + 127.0.0.1 breaks
  # the session cookie (set on OAuth callback host, read from the other).
  set_env_key FRONTEND_URL "http://localhost:3000"
  set_env_key NEXT_PUBLIC_API_URL "http://localhost:8000"
  set_env_key TRUSTED_PROXY_HOPS 0
  set_env_key MS_REDIRECT_URI "http://localhost:8000/api/v1/auth/microsoft/callback"
  set_env_key MS_LOGIN_REDIRECT_URI "http://localhost:8000/api/v1/login/microsoft/callback"
  set_env_key OPENAI_OAUTH_REDIRECT_URI "http://localhost:1455/auth/callback"
  set_env_key CORS_ORIGINS '["http://localhost:3000","http://127.0.0.1:3000"]'
  set_env_key QDRANT_URL "http://qdrant:6333"
  set_env_key KNOWLEDGE_DIR "/knowledge"

  echo ""
  echo "Local production .env.prod ready."
  echo "  UI:     http://localhost:3000   (use THIS host — not 127.0.0.1)"
  echo "  API:    http://localhost:8000"
  echo "  Login:  Microsoft (demo disabled)"
  echo "  Flags:  DRY_RUN=true COOKIE_SECURE=false REQUIRE_AUTH=true"
  echo "  Azure redirect URI must include:"
  echo "    http://localhost:8000/api/v1/login/microsoft/callback"
  echo "Next: ./scripts/local_prod.sh up"
}

cmd_up() {
  [[ -f .env.prod ]] || die "Missing .env.prod — run: ./scripts/local_prod.sh init"

  env_val="$(env_get_file .env.prod ENVIRONMENT)"
  cookie="$(env_get_file .env.prod COOKIE_SECURE)"
  dry="$(env_get_file .env.prod DRY_RUN)"
  [[ "$env_val" == "production" ]] || die "ENVIRONMENT must be production in .env.prod"
  [[ "$cookie" == "false" ]] || echo "WARN: COOKIE_SECURE=$cookie — prefer false on plain HTTP"
  echo "DRY_RUN=$dry"

  info "Stopping dev stack (frees :3000 / :8000)"
  "${COMPOSE_DEV[@]}" down --remove-orphans 2>/dev/null || true

  info "Building & starting local production stack"
  "${COMPOSE_PROD[@]}" up -d --build

  info "Waiting for health on $API"
  for _ in $(seq 1 60); do
    if curl -sf "$API/health" >/dev/null 2>&1; then
      echo ""
      curl -s "$API/health"; echo
      echo -n "providers: "; curl -s "$API/api/v1/login/providers"; echo
      code=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$API/api/v1/login/demo" || true)
      echo "demo login HTTP $code (expect 403)"
      docs=$(curl -s -o /dev/null -w "%{http_code}" "$API/docs" || true)
      echo "docs HTTP $docs (expect 404)"
      echo ""
      echo "Open http://localhost:3000 → Microsoft sign-in"
      echo "(Do not mix with http://127.0.0.1 — cookies will not stick.)"
      echo "Back to dev trial: ./scripts/local_prod.sh dev"
      exit 0
    fi
    sleep 3
  done
  echo "ERROR: backend not healthy" >&2
  "${COMPOSE_PROD[@]}" logs --tail=60 backend || true
  exit 1
}

cmd_down() {
  info "Stopping local production stack"
  "${COMPOSE_PROD[@]}" down --remove-orphans
}

cmd_dev() {
  info "Stopping local production → starting dev compose"
  "${COMPOSE_PROD[@]}" down --remove-orphans 2>/dev/null || true
  "${COMPOSE_DEV[@]}" up -d --build
  echo "Dev: http://localhost:3000"
}

cmd_status() {
  "${COMPOSE_PROD[@]}" ps || true
  curl -sf "$API/health" || echo "health failed"
  echo
}

cmd_logs() {
  "${COMPOSE_PROD[@]}" logs -f --tail=80
}

case "$CMD" in
  init) cmd_init ;;
  up) cmd_up ;;
  down) cmd_down ;;
  dev) cmd_dev ;;
  status) cmd_status ;;
  logs) cmd_logs ;;
  *)
    echo "Usage: $0 {init|up|down|dev|status|logs}"
    exit 1
    ;;
esac
