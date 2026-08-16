# AGENTS.md — Rafaela AI Secretary

Instructions for coding agents (Claude Code, Cursor, Pi, Codex, etc.).
Read this before making changes.

---

## What this project is

**Rafaela** — bilingual (EL/EN) GDPR-oriented AI executive secretary.

| Layer | Stack |
|-------|--------|
| Agent | Haystack 3.x + tools |
| Backend | FastAPI (`backend/app`) |
| Frontend | Next.js 15 + Tailwind (`frontend`) |
| Data | PostgreSQL, Redis |
| Vectors | Qdrant (optional semantic / hybrid RAG) |
| Deploy | Docker Compose (dev + prod) |

**Product rules (non-negotiable)**

1. **Privacy / GDPR** — minimize data, encrypt tokens, audit significant actions.
2. **HITL** — calendar (and any external write) goes through `propose_*` → pending action → user approve/reject. Never claim a write succeeded without approval.
3. **Mail is read-only** — list/read OK; no real send from the agent. Drafts only.
4. **`DRY_RUN=true` by default** — even approved writes may be simulated in trial.
5. **No secrets in git** — never commit `.env`, tokens, API keys, or paste them into docs/PRs.

---

## Repo map

```text
ai-secretary/
├── backend/app/
│   ├── main.py                 # FastAPI routes
│   ├── api_auth.py             # login (demo / MS / Google)
│   ├── agent/secretary_agent.py
│   ├── services/               # ms, google, knowledge, llm_router, oauth…
│   ├── tools/                  # Haystack @tool functions
│   ├── models/                 # SQLAlchemy
│   └── core/config.py          # settings from env
├── frontend/src/
│   ├── app/                    # Next.js app router
│   └── components/             # Chat, Settings, Onboarding, …
├── knowledge/                  # Markdown templates for RAG
├── docs/                       # ROADMAP, DEPLOY, SECURITY, …
├── docker-compose.yml          # dev stack
├── docker-compose.prod.yml
├── scripts/                    # e2e, pilot, index helpers
└── .env.example                # template only
```

---

## How to run (local)

```bash
cd C:/DEVELOP/ai-secretary   # or repo root
cp .env.example .env         # fill secrets locally — do not commit
docker compose up --build -d
```

| Service | URL |
|---------|-----|
| Frontend | http://localhost:3000 |
| Backend | http://localhost:8000 |
| API docs | http://localhost:8000/docs |
| Qdrant | http://localhost:6333 |

Useful:

```bash
make health
make knowledge
make logs
make index-knowledge
docker compose exec backend bash
```

Hot-reload: `./backend/app` → `/app/app`, `./knowledge` → `/knowledge:ro`.

---

## LLM / providers

Configured via `.env` + runtime OAuth:

| Path | Role |
|------|------|
| ChatGPT OAuth (`openai-oauth`) | Primary when user connected ChatGPT — model e.g. `gpt-5.5` |
| `OPENCODE_*` | Backup OpenAI-compatible (e.g. kimi-k3) |
| `OPENAI_API_KEY` | Official Platform key (chat and/or embeddings) |
| `XAI_*` | Optional Grok slot |

- Failover: `backend/app/services/llm_router.py`
- Codex/ChatGPT tools: `openai_oauth.py` + `CodexOAuthChatGenerator` (must keep **tool calling** working)
- Do not put OpenCode keys in `OPENAI_API_KEY`

When changing LLM code: verify a chat turn that **calls a tool** (e.g. emails or `search_knowledge`), not only plain text.

---

## Integrations

### Microsoft 365
- **Login:** `/api/v1/login/microsoft` → `MS_LOGIN_REDIRECT_URI`
- **Mail/Calendar connect:** `/api/v1/auth/microsoft/*` → `MS_REDIRECT_URI`
- Both redirect URIs must exist in Azure app registration (Web platform).
- Mail scopes: read-only. Calendar writes: HITL propose tools.

### Google
- Same split: login vs Workspace connect (`GOOGLE_*` / `GOOGLE_LOGIN_*`).
- Needs `GOOGLE_CLIENT_ID` + `GOOGLE_CLIENT_SECRET` in `.env` + Google Cloud OAuth clients/redirects.

### Knowledge / RAG
- Source files: `knowledge/*.md`
- Service: `backend/app/services/knowledge.py`
- Tools: `search_knowledge`, `knowledge_base_status`
- API: `GET /api/v1/knowledge/status`, `GET /api/v1/knowledge/search?q=`
- Keyword always; semantic/hybrid when Qdrant + embeddings available
- Prefer **templates via `search_knowledge`** before free-form long drafts

---

## Agent behavior (`secretary_agent.py`)

- System prompt owns tone (Rafaela), GDPR, tools policy.
- Register new capabilities as Haystack `@tool` under `backend/app/tools/`.
- After tool results: concise summary; Greek if user wrote Greek.
- Never invent “sent email” / “created event” without pending approval flow.

---

## Coding standards

### Do
- Small, reviewable diffs
- Match existing patterns (structlog, settings, tool error strings)
- Update `.env.example` + docs when adding env vars or ports
- Keep `DRY_RUN` and HITL intact unless explicitly asked otherwise
- Use `Europe/Athens` as default timezone context unless user overrides

### Don’t
- Commit `.env`, keys, cookies, session dumps
- Disable auth in production paths casually
- Add LangChain rewrite “for fun” — stay on Haystack unless agreed
- Drive-by refactors unrelated to the task
- Log full OAuth tokens or email bodies at info level

### Python
- FastAPI + Pydantic settings
- Async DB where existing code is async; tools may bridge with `_run()`
- Typed where practical

### Frontend
- Client components where hooks are needed
- `suppressHydrationWarning` on `html`/`body` (extensions inject attributes)
- Keep Settings/Chat usable; no redesign without ask

---

## Security checklist (every PR)

- [ ] No secrets staged
- [ ] Redirect URIs / CORS changes documented
- [ ] User-scoped data filtered by `user_id` (no IDOR)
- [ ] Writes still HITL or explicitly dry-run
- [ ] Rate limit / auth assumptions unchanged or improved

---

## Testing before you finish

Minimum:

```bash
curl -s http://localhost:8000/health
curl -s http://localhost:8000/api/v1/knowledge/status
curl -s "http://localhost:8000/api/v1/knowledge/search?q=follow-up"
```

If you touched agent/LLM/tools:

```bash
# Chat should tool-call for live data / templates
# Example prompts:
#  - "Διάβασε τα τελευταία emails"
#  - "Ετοίμασε follow-up email βάσει προτύπου"
```

If tests exist:

```bash
# from Makefile / scripts when available
./scripts/e2e_smoke.sh
```

---

## Git

- Conventional commits preferred: `feat:`, `fix:`, `docs:`, `chore:`
- Never force-push `master` unless user asks
- Do not commit `frontend/tsconfig.tsbuildinfo` or `node_modules`

---

## Priority when asked to “make it professional”

Work in this order unless user overrides:

1. **P0** Security, auth, data isolation, secret hygiene, unbroken OAuth  
2. **P1** Reliability (errors, timeouts, failover), HITL UX, knowledge quality  
3. **P2** Observability, tests/CI, deploy/backup docs  
4. **P3** Multi-tenant/billing polish, polish UI, extra connectors  

Default workflow for large asks:

1. **Audit only** → report with P0/P1/P2  
2. Wait for user **go**  
3. Implement a **small slice**  
4. Verify with commands above  

---

## Useful doc links (in-repo)

- `README.md` — quick start  
- `docs/ROADMAP.md` / `Rafaela-ROADMAP.md` — product roadmap  
- `docs/DEPLOY.md` — pilot deploy  
- `docs/SECURITY.md` — security checklist  
- `docs/DOCUMENTATION.md` — fuller product docs  
- `knowledge/README.md` — how to add RAG docs  

---

## Explicit user overrides

If the user says something that conflicts with this file (e.g. “enable real mail send”), follow the **user** for that task, call out the risk briefly, and keep the change scoped.
