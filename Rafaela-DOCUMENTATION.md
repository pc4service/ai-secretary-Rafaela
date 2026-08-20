# Rafaela – AI Secretary Agent

**Version:** 1.2 · **Updated:** 16 August 2026

GDPR-aware AI executive secretary (Haystack + FastAPI + Next.js).

## Quick start

```bash
cd C:\DEVELOP\ai-secretary
cp .env.example .env
docker compose up --build
# UI http://localhost:3000 · API http://localhost:8000/docs
```

### Τι υπάρχει τώρα (αληθινό tree)

| Feature | Endpoint / UI | Σημείωση |
|---------|----------------|----------|
| Streaming chat | `POST /api/v1/chat/stream` | SSE |
| Onboarding + conversations | `OnboardingWizard`, sidebar | |
| Login | Demo / Google / MS | Cookie session |
| MS365 + Google | Settings · `/auth/microsoft|google` | Mail **read-only** |
| ChatGPT OAuth | Settings · `/auth/openai` | Callback `localhost:1455` |
| Knowledge keyword | `GET /api/v1/knowledge/search` + tool | Όχι ακόμα Qdrant |
| HITL calendar | propose → approve | Email send **δεν** είναι registered |

Classic chat: `POST /api/v1/chat` still available.

---


# Rafaela – AI Secretary Agent  
## Πλήρης Τεκμηρίωση & Ανασκόπηση Έργου

**Έκδοση:** 0.1.0-trial  
**Ημερομηνία:** 10 Αυγούστου 2026  
**Κατάσταση:** Development / Trial-ready  

---

## 1. Ανασκόπηση Συνομιλίας & Εξέλιξης

Η ανάπτυξη έγινε σταδιακά μέσα από τη συζήτηση:

| Βήμα | Αίτημα | Αποτέλεσμα |
|------|--------|------------|
| 1 | Δυνατότητες AI Secretary + GDPR | Ορισμός capabilities & privacy-by-design |
| 2 | Prompt + Haystack, Firecrawl, UI/UX Pro Max, MS365/Google | Development prompt + tech stack |
| 3 | Σύντομο Agent System Prompt + Docker skeleton | Backend skeleton, Docker Compose |
| 4 | MS365 + Google tools + Next.js frontend | OAuth, tools, Chat/Settings UI |
| 5 | Encrypted tokens + HITL + μετονομασία σε Rafaela | DB tokens, propose→approve flow, female character |
| 6 | Memory + Pending Actions UI + hardening | Conversation DB, Ενέργειες tab, rate limit, audit |

**Τελικός χαρακτήρας:** Rafaela – γυναικείος, επαγγελματικός, θερμός AI Executive Secretary (Ελληνικά / Αγγλικά).

---

## 2. Τι Είναι το Project

Η **Rafaela** είναι ένας GDPR-compliant AI Executive Secretary που:

- Διαχειρίζεται ημερολόγιο & email (Microsoft 365 + Google Workspace)
- Κάνει έρευνα στο web (Firecrawl)
- Ζητά **πάντα** επιβεβαίωση πριν από write ενέργειες (Human-in-the-Loop)
- Αποθηκεύει συνομιλίες και κρυπτογραφημένα OAuth tokens στη PostgreSQL
- Τρέχει σε Docker για εύκολες δοκιμές

---

## 3. Αρχιτεκτονική

```
┌─────────────────┐     ┌──────────────────────┐     ┌─────────────────┐
│  Next.js UI     │────▶│  FastAPI + Haystack  │────▶│  PostgreSQL     │
│  (port 3000)    │     │  Agent (port 8000)   │     │  Redis          │
│  Chat           │     │  OAuth / Tools       │     │  Encrypted      │
│  Ενέργειες     │     │  HITL / Memory       │     │  tokens & logs  │
│  Ρυθμίσεις     │     │  Rate limit / Audit  │     │                 │
└─────────────────┘     └──────────┬───────────┘     └─────────────────┘
                                   │
                    ┌──────────────┼──────────────┐
                    ▼              ▼              ▼
              Microsoft      Google         Firecrawl
              Graph API      Gmail/Cal      (research)
```

### Tech Stack

| Στρώμα | Τεχνολογία |
|--------|------------|
| Agent / Orchestration | Haystack 3.x (`Agent` + tools) |
| Web research | Firecrawl |
| Backend API | FastAPI + Uvicorn |
| Auth integrations | MSAL (Microsoft), google-auth (Google) |
| Database | PostgreSQL 16 + SQLAlchemy async |
| Cache | Redis 7 |
| Frontend | Next.js 15, React 19, Tailwind CSS |
| Encryption | Fernet (cryptography) |
| Deployment | Docker Compose |

---

## 4. Δομή Project

```
ai-secretary/
├── backend/
│   ├── app/
│   │   ├── agent/secretary_agent.py   # Haystack Agent + Rafaela system prompt
│   │   ├── core/config.py             # Settings από .env
│   │   ├── core/security.py           # Fernet encrypt/decrypt
│   │   ├── models/database.py         # User, OAuthToken, PendingAction,
│   │   │                              # Conversation, Message, AuditLog
│   │   ├── services/
│   │   │   ├── microsoft.py           # MS Graph Mail + Calendar
│   │   │   ├── google.py              # Gmail + Google Calendar
│   │   │   ├── openai_oauth.py        # ChatGPT / Codex OAuth
│   │   │   ├── llm_router.py          # multi-provider failover
│   │   │   ├── knowledge.py           # keyword RAG (Qdrant stub)
│   │   │   ├── token_store.py
│   │   │   ├── pending_actions.py
│   │   │   ├── conversation.py
│   │   │   └── gdpr.py
│   │   ├── tools/
│   │   │   ├── ms365_tools.py
│   │   │   ├── google_tools.py
│   │   │   └── knowledge_tools.py     # search_knowledge
│   │   ├── api_auth.py                # login session
│   │   └── main.py
│   └── requirements.txt
├── knowledge/                         # εταιρικά md πρότυπα
├── frontend/
│   ├── src/app/page.tsx
│   ├── src/app/login/page.tsx
│   ├── src/components/
│   │   ├── Chat.tsx
│   │   ├── ConversationSidebar.tsx
│   │   ├── OnboardingWizard.tsx
│   │   ├── PendingActions.tsx
│   │   └── Settings.tsx
│   └── package.json
├── docker/
│   └── Dockerfile.backend
├── docker-compose.yml
├── docs/
│   ├── AGENT_SYSTEM_PROMPT.md
│   └── DOCUMENTATION.md               # (αυτό το αρχείο)
├── scripts/test_chat.sh
├── .env.example
├── Makefile
└── README.md
```

---

## 5. Βασικές Δυνατότητες

### Agent (Rafaela)
- Bilingual (Ελληνικά πρώτα αν ο χρήστης γράφει ελληνικά)
- Calendar list / propose create event
- Email **list only** (send tools not registered)
- Knowledge templates (`search_knowledge`, keyword)
- Web research (Firecrawl)
- GDPR export / delete tools
- Πάντα propose → approve για write actions

### Human-in-the-Loop
1. Χρήστης ζητά write ενέργεια  
2. Agent καλεί `*_propose_*` tool  
3. Δημιουργείται `PendingAction` στη DB  
4. UI εμφανίζει **Έγκριση** / **Απόρριψη** (στο chat και στην καρτέλα Ενέργειες)  
5. Μόνο μετά την έγκριση εκτελείται (ή dry-run)

### GDPR
- Privacy by design
- Encrypted tokens at rest
- Dry-run mode by default (`DRY_RUN=true`)
- Configurable retention
- Audit log
- Export / delete tools στο agent
- Data minimization (least-privilege OAuth scopes)

---

## 6. API Endpoints (σύνοψη)

| Method | Path | Περιγραφή |
|--------|------|-----------|
| GET | `/health` | Health check |
| POST | `/api/v1/chat` | Chat με Rafaela |
| POST | `/api/v1/chat/stream` | SSE streaming chat |
| GET | `/api/v1/system-prompt` | Τρέχον system prompt |
| GET | `/api/v1/knowledge/status` | Knowledge dir / chunks |
| GET | `/api/v1/knowledge/search?q=` | Keyword/semantic search · **auth** |
| POST | `/api/v1/knowledge/index` | Re-index στο Qdrant · **auth** |
| GET | `/api/v1/settings` | Κατάσταση συνδέσεων |
| GET | `/api/v1/auth/openai/login` | ChatGPT OAuth URL |
| GET | `/api/v1/auth/microsoft/login` | OAuth URL Microsoft |
| GET | `/api/v1/auth/microsoft/callback` | OAuth callback |
| POST | `/api/v1/auth/microsoft/disconnect` | Αποσύνδεση |
| GET | `/api/v1/auth/google/login` | OAuth URL Google |
| GET | `/api/v1/auth/google/callback` | OAuth callback |
| POST | `/api/v1/auth/google/disconnect` | Αποσύνδεση |
| GET | `/api/v1/actions/pending` | Pending HITL actions |
| GET | `/api/v1/actions/history` | Ιστορικό ενεργειών |
| POST | `/api/v1/actions/{id}/resolve` | Approve / Reject |
| GET | `/api/v1/conversations` | Λίστα συνομιλιών |
| GET | `/api/v1/conversations/{id}/messages` | Μηνύματα |
| DELETE | `/api/v1/conversations/{id}` | Διαγραφή συνομιλίας |

---

## 7. Συνολικές Οδηγίες Εκκίνησης

### Προαπαιτούμενα
- Docker + Docker Compose
- (Προαιρετικά) Node 22+ αν τρέχεις frontend εκτός Docker
- OpenAI API key (υποχρεωτικό για τον agent)

### Βήμα 1 – Clone / είσοδος στο project

```bash
cd C:\DEVELOP\ai-secretary
```

### Βήμα 2 – Environment

```bash
cp .env.example .env
```

Επεξεργάσου το `.env`:

```env
OPENAI_API_KEY=sk-...
# Προαιρετικά:
FIRECRAWL_API_KEY=fc-...
MS_CLIENT_ID=...
MS_CLIENT_SECRET=...
GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...
DRY_RUN=true
ENVIRONMENT=trial
```

### Βήμα 3 – Εκκίνηση

```bash
docker compose up --build
# ή
make up
```

### Βήμα 4 – Πρόσβαση

| Υπηρεσία | URL |
|----------|-----|
| Frontend | http://localhost:3000 |
| Backend API | http://localhost:8000 |
| Swagger Docs | http://localhost:8000/docs |
| Health | http://localhost:8000/health |

### Βήμα 5 – Δοκιμή χωρίς OAuth

Στο chat:

```
Γεια σου Rafaela, παρουσιάσου.
Τι ώρα είναι;
```

### Βήμα 6 – Σύνδεση Microsoft / Google (προαιρετικό)

1. Azure Portal → App registration → Redirect URI:  
   `http://localhost:8000/api/v1/auth/microsoft/callback`
2. Google Cloud Console → OAuth Client → Redirect URI:  
   `http://localhost:8000/api/v1/auth/google/callback`
3. Βάλε Client ID/Secret στο `.env`
4. Frontend → **Ρυθμίσεις** → Σύνδεση

### Βήμα 7 – Δοκιμή HITL

```
Φτιάξε follow-up email μετά από meeting (από τα πρότυπα).
Πρότεινε ένα event αύριο στις 10:00.
```

Για calendar write εμφανίζονται **Έγκριση** / **Απόρριψη**.  
Το mail είναι read-only: η Rafaela δίνει draft, δεν στέλνει.

---

## 8. Χρήσιμες Εντολές Makefile

```bash
make up        # docker compose up --build -d
make down      # stop
make logs      # backend logs
make test      # smoke test script
make health    # curl health
make shell     # shell στο backend container
```

---

## 9. System Prompt (Rafaela) – Σύνοψη

- Ρόλος: επαγγελματική, διακριτική, θερμή Executive Secretary
- GDPR first, data minimization
- Write actions **μόνο** μέσω propose_* tools
- Ποτέ δεν ισχυρίζεται ότι στάλθηκε email πριν την έγκριση
- Ελληνικά όταν γράφει ο χρήστης ελληνικά

Πλήρες κείμενο: `docs/AGENT_SYSTEM_PROMPT.md`

---

## 10. Ασφάλεια & Trial Mode

| Ρύθμιση | Default | Σημασία |
|---------|---------|---------|
| `DRY_RUN` | `true` | Δεν γίνονται πραγματικά send/create |
| `ENVIRONMENT` | `trial` | Trial περιβάλλον |
| Rate limit | 60/min/IP | Προστασία από abuse |
| Tokens | Fernet encrypted | At-rest encryption |
| HITL | Υποχρεωτικό | Κάθε write χρειάζεται approve |

**Για production:** άλλαξε `DRY_RUN=false`, ισχυρό `SECRET_KEY`, EU region DB, πραγματικό secrets manager, DPIA.

---

## 11. Επόμενα Βήματα

1. ~~Semantic RAG (Qdrant)~~ ✅  
2. ~~`REQUIRE_AUTH` + isolation~~ ✅  
3. ~~Unit/guard tests + CI~~ ✅  
4. ~~Merge hardening + pilot scripts~~ ✅  
5. ~~Latency A+B+E + Codex incomplete + chat timing~~ ✅ (`docs/AUDIT.md` Φάση 12)  
6. Deploy trial host · optional true streaming  
7. GDPR export UI · multi-tenant μετά pilot  


Graphify / ECC / UI-UX Pro Max: skills του coding assistant — δεν μπαίνουν ως runtime της Rafaela.

---

## 12. Αρχεία τεκμηρίωσης

- `README.md` – γρήγορη εκκίνηση
- `docs/DOCUMENTATION.md` – αυτό το έγγραφο
- `docs/ROADMAP.md` – φάσεις + αληθινό status
- `docs/AGENT_SYSTEM_PROMPT.md` – system prompt (συγχρονισμένο με read-only mail)
- `docs/DEPLOY.md`, `SECURITY.md`, `NGINX.md`, `PRODUCTION.md`
- `.env.example` – μεταβλητές περιβάλλοντος

---

*Τεκμηρίωση δημιουργήθηκε αυτόματα στο πλαίσιο της ανάπτυξης του Rafaela AI Secretary Agent.*
