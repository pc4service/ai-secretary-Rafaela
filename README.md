# Rafaela – AI Secretary (GDPR-Compliant)

Professional AI Executive Secretary powered by **Haystack**, **Firecrawl**, Microsoft 365 & Google Workspace, with encrypted token storage, conversation memory and human-in-the-loop approvals.

## Features

- **Rafaela** – bilingual (Greek/English) AI secretary
- **Microsoft 365** & **Google Workspace** (OAuth · Mail **read-only** · Calendar HITL)
- **ChatGPT OAuth** – Sign in with ChatGPT from Settings (in-process Codex · no public relay · `OPENAI_OAUTH_REASONING_EFFORT=low`)
- **Knowledge RAG** – templates in `knowledge/` (keyword always · semantic/hybrid with Qdrant)
- **Human-in-the-loop** – calendar / knowledge writes require approval
- **Conversation memory** – PostgreSQL + sidebar
- **Streaming chat** (SSE) + onboarding · **timestamps** (start / answer / duration, Europe/Athens)
- **Faster agent path** – intent router (simple vs tools), filtered tools, `AGENT_MAX_STEPS`
- Encrypted OAuth tokens, audit log, shared rate limit, `DRY_RUN=true` by default
- **`REQUIRE_AUTH`** – session isolation on actions/conversations (always on in production)

## Quick Start

```bash
cd C:\DEVELOP\ai-secretary
cp .env.example .env
docker compose up --build
```

| Service  | URL                        |
|----------|----------------------------|
| Frontend | http://localhost:3000      |
| Backend  | http://localhost:8000      |
| API Docs | http://localhost:8000/docs (not in production) |

## UI Tabs

1. **Chat** – talk to Rafaela; approve/reject calendar proposals
2. **Ενέργειες** – pending actions + history
3. **Ρυθμίσεις** – Microsoft, Google, ChatGPT OAuth, GDPR flags

## Architecture highlights

- Tokens stored encrypted in `oauth_tokens`
- Intent router (`services/intent_router.py`) before full tool agent
- Conversations + messages in DB for memory
- `pending_actions` table for HITL workflow
- `audit_logs` for every significant event
- `knowledge/` markdown + hybrid search (Qdrant optional)
- LLM failover (`llm_router.py`)
- Hardening log: `docs/AUDIT.md`

## Checks

```bash
make health
make test
make knowledge
```

## OAuth setup

Redirect URIs (local):
- `http://localhost:8000/api/v1/auth/microsoft/callback`
- `http://localhost:8000/api/v1/auth/google/callback`
- ChatGPT / Codex: `http://localhost:1455/auth/callback` (published in compose)

## GDPR

- DRY_RUN=true by default
- Propose → Approve flow for all writes
- Data export / delete tools available to the agent
- Configurable retention
- Audit trail

## Docs

- `docs/ROADMAP.md` — product roadmap
- `docs/AUDIT.md` — security hardening log
- `docs/DEPLOY.md` / `docs/SECURITY.md` — pilot
- `AGENTS.md` — coding-agent rules

## License

MIT (skeleton). Use responsibly.
