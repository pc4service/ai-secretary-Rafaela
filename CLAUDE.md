# CLAUDE.md

Project instructions for Claude Code (and compatible agents).

**Full rules:** see [AGENTS.md](./AGENTS.md) — read it first.

## One-screen summary

- **Product:** Rafaela — GDPR AI secretary (EL/EN), HITL approvals, mail **read-only**.
- **Stack:** FastAPI + Haystack · Next.js · Postgres · Redis · Qdrant · Docker Compose.
- **Root:** this directory (`ai-secretary`). Don’t invent a different monorepo layout.
- **Secrets:** never commit or print `.env` / tokens / API keys.
- **Safe defaults:** `DRY_RUN=true`; calendar writes via `propose_*` only.

## Before coding

1. Skim `AGENTS.md`, `README.md`, and the files you will touch.
2. Prefer small diffs; no unrelated refactors.
3. For “audit / professional review” requests: **report first**, implement only after the user says **go**.

## Verify

```bash
docker compose ps
curl -s http://localhost:8000/health
curl -s http://localhost:8000/api/v1/knowledge/status
```

Agent/tool changes: smoke-test chat with a tool prompt (emails or `search_knowledge` / follow-up template).

## Out of scope unless asked

- Rewriting agent framework away from Haystack  
- Disabling HITL or enabling unsupervised mail send  
- Production billing/go-live without deploy + security review  
