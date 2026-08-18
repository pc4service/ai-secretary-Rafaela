# Rafaela – AI Secretary (GDPR-Compliant)

Professional AI Executive Secretary powered by **Haystack**, **Firecrawl**, Microsoft 365 & Google Workspace, with encrypted token storage, conversation memory and human-in-the-loop approvals.

## Features

- **Rafaela** – bilingual (Greek/English) AI secretary
- **Microsoft 365** & **Google Workspace** (OAuth · Mail **read-only** · Calendar HITL)
- **ChatGPT OAuth** – Sign in with ChatGPT from Settings (no Platform key required)
- **Knowledge (keyword RAG)** – templates in `knowledge/` via `search_knowledge`
- **Human-in-the-loop** – calendar writes require approval
- **Conversation memory** – PostgreSQL + sidebar
- **Streaming chat** (SSE) + onboarding wizard
- Encrypted OAuth tokens, audit log, rate limit, `DRY_RUN=true` by default

Semantic RAG (Qdrant) is **not** implemented yet — keyword search works without it.

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
| API Docs | http://localhost:8000/docs |

## UI Tabs

1. **Chat** – talk to Rafaela; approve/reject calendar proposals
2. **Ενέργειες** – pending actions + history
3. **Ρυθμίσεις** – Microsoft, Google, ChatGPT OAuth, GDPR flags

## Architecture highlights

- Tokens stored encrypted in `oauth_tokens`
- Conversations + messages in DB for memory
- `pending_actions` table for HITL workflow
- `audit_logs` for every significant event
- `knowledge/` markdown + keyword search
- LLM failover (`llm_router.py`)

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

## License

MIT (skeleton). Use responsibly.
