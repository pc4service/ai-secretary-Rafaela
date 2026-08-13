# Rafaela – AI Secretary (GDPR-Compliant)

Professional AI Executive Secretary powered by **Haystack**, **Firecrawl**, Microsoft 365 & Google Workspace, with encrypted token storage, conversation memory and human-in-the-loop approvals.

## Features

- **Rafaela** – bilingual (Greek/English) AI secretary
- **Microsoft 365** & **Google Workspace** (OAuth + Mail + Calendar)
- **Human-in-the-loop** – every write action requires explicit approval
- **Conversation memory** – chat history persisted in PostgreSQL
- **Encrypted OAuth tokens** (Fernet)
- **Audit log** for GDPR accountability
- **Rate limiting** (60 req/min per IP)
- **Dry-run / Trial mode** by default
- Modern Next.js UI: Chat · Ενέργειες · Ρυθμίσεις

## Quick Start

```bash
cd ai-secretary-agent
cp .env.example .env
# Set at least OPENAI_API_KEY=sk-...

docker compose up --build
```

| Service  | URL                        |
|----------|----------------------------|
| Frontend | http://localhost:3000      |
| Backend  | http://localhost:8000      |
| API Docs | http://localhost:8000/docs |

## UI Tabs

1. **Chat** – talk to Rafaela; approve/reject inline when she proposes actions
2. **Ενέργειες** – full list of pending actions + history
3. **Ρυθμίσεις** – connect/disconnect Microsoft & Google, GDPR status

## Architecture highlights

- Tokens stored encrypted in `oauth_tokens`
- Conversations + messages in DB for memory
- `pending_actions` table for HITL workflow
- `audit_logs` for every significant event
- Simple rate limiter middleware

## OAuth setup

See previous README section / Azure Portal + Google Cloud Console.
Redirect URIs:
- `http://localhost:8000/api/v1/auth/microsoft/callback`
- `http://localhost:8000/api/v1/auth/google/callback`

## GDPR

- DRY_RUN=true by default
- Propose → Approve flow for all writes
- Data export / delete tools available to the agent
- Configurable retention
- Audit trail

## License

MIT (skeleton). Use responsibly.
