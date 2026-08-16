#!/usr/bin/env bash
# Pilot deploy helper — run ON the target host (Proxmox VM or VPS)
# Usage:
#   ./scripts/pilot_deploy.sh          # build & start prod stack
#   ./scripts/pilot_deploy.sh status
#   ./scripts/pilot_deploy.sh smoke
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

COMPOSE="docker compose -f docker-compose.prod.yml --env-file .env.prod"
CMD="${1:-up}"

if [[ ! -f .env.prod ]]; then
  echo "Missing .env.prod — copying from example..."
  cp .env.prod.example .env.prod
  echo "Edit .env.prod (SECRET_KEY, POSTGRES_PASSWORD, OPENAI_API_KEY, URLs) then re-run."
  exit 1
fi

# shellcheck disable=SC1091
set -a
# Load for local checks (compose also uses --env-file)
source .env.prod 2>/dev/null || true
set +a

need() {
  local k="$1"
  if ! grep -q "^${k}=.\+" .env.prod 2>/dev/null; then
    echo "WARN: $k appears empty in .env.prod"
  fi
}

case "$CMD" in
  up)
    need SECRET_KEY
    need POSTGRES_PASSWORD
    need OPENAI_API_KEY
    echo "=== Building & starting pilot stack ==="
    $COMPOSE up -d --build
    echo "Waiting for health..."
    for i in $(seq 1 30); do
      if curl -sf http://127.0.0.1:8000/health >/dev/null 2>&1; then
        echo "Backend healthy."
        curl -s http://127.0.0.1:8000/health | head -c 400 || true
        echo ""
        exit 0
      fi
      sleep 2
    done
    echo "ERROR: backend not healthy in time"
    $COMPOSE logs --tail=40 backend || true
    exit 1
    ;;
  status)
    $COMPOSE ps
    curl -sf http://127.0.0.1:8000/health || echo "health failed"
    ;;
  smoke)
    echo "=== Local smoke (API on 127.0.0.1:8000) ==="
    API_BASE=http://127.0.0.1:8000 ./scripts/e2e_smoke.sh
    ;;
  down)
    $COMPOSE down
    ;;
  logs)
    $COMPOSE logs -f --tail=100
    ;;
  *)
    echo "Usage: $0 {up|status|smoke|down|logs}"
    exit 1
    ;;
esac
