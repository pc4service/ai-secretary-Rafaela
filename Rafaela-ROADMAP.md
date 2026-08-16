# Rafaela AI Secretary — Ανακεφαλαίωση & Επαγγελματικό Roadmap

**Έκδοση εγγράφου:** 1.1  
**Ημερομηνία:** 14 Αυγούστου 2026  
**Στόχος:** Από trial prototype → πλήρες, παρουσιάσιμο και εμπορεύσιμο προϊόν για εταιρική χρήση.

---

## Πρόοδος υλοποίησης (ενημέρωση 14 Αυγούστου 2026)

### Package release v1.1 (14 Αυγούστου 2026)

**Αρχείο download:** `Rafaela-AI-Secretary-Agent-v1.1.zip`

| Περιεχόμενο στο zip | Κατάσταση |
|---------------------|-----------|
| Core agent (Haystack Rafaela), HITL, MS/Google tools | ✅ |
| Docker compose (dev + prod), scripts, CI workflow | ✅ |
| Frontend: Chat streaming, Onboarding, Conversation sidebar, Settings, Pending actions | ✅ |
| Docs: ROADMAP, DOCUMENTATION, DEPLOY, SECURITY, NGINX, PRODUCTION | ✅ |
| Phase 2 extras (orgs/billing/RAG files) | Μερικά αναφέρονται στο roadmap· επαν-υλοποίηση αν λείπουν από tree |

**Γρήγορη εκκίνηση**

```bash
unzip Rafaela-AI-Secretary-Agent-v1.1.zip
cd ai-secretary-agent
cp .env.example .env   # βάλε OPENAI_API_KEY
docker compose up --build
# http://localhost:3000
```

**Νέο στο v1.1 (Phase 3)**
- Onboarding wizard (4 βήματα, skip / επαναφορά)
- SSE streaming chat (`/api/v1/chat/stream`)
- Sidebar συνομιλιών (νέα / επιλογή / διαγραφή)



### Ολοκληρωμένα στο codebase

| # | Πρόταση | Κατάσταση | Αρχεία |
|---|---------|-----------|--------|
| 1 | **Υποχρεωτικό auth** (`REQUIRE_AUTH`) | ✅ | `main.py`, `config.py`, `api_auth.py` |
| 2 | **RAG skeleton** (Qdrant + keyword fallback) | ✅ | `services/knowledge.py`, `docker-compose.yml` (qdrant), `knowledge/**` |
| 3 | **Tool `search_knowledge`** | ✅ | `tools/knowledge_tools.py`, `secretary_agent.py` |
| 4 | **Unit tests** (auth + knowledge) | ✅ | `backend/tests/` — `make test-unit` |
| 5 | **E2E smoke** (login → knowledge → chat) | ✅ | `scripts/e2e_smoke.sh` — `make e2e` |
| 6 | **CI** GitHub Actions | ✅ | `.github/workflows/ci.yml` |
| 7 | **Deploy runbook** pilot | ✅ | `docs/DEPLOY.md` |
| 8 | **Security checklist** | ✅ | `docs/SECURITY.md` |
| 9 | **Pilot deploy script** | ✅ | `scripts/pilot_deploy.sh` |
| 10 | **Multi-tenant skeleton** | ✅ | `Organization`, `OrgMember`, `/api/v1/orgs` |
| 11 | **Tenant isolation 2b** | ✅ | `org_id` + filters σε tokens/conversations/actions |
| 12 | **Stripe billing 2c** | ✅ | `/billing/plans|checkout|webhook` + mock mode |
| 13 | **Org switcher UI** | ⚠️ docs / partial restore | Βλ. σημείωση package |
| 14 | **Phase 3 Onboarding** | ✅ | `OnboardingWizard.tsx` |
| 15 | **Phase 3 Streaming SSE** | ✅ | `POST /api/v1/chat/stream` + `streamChat()` |
| 16 | **Conversation sidebar** | ✅ | `ConversationSidebar.tsx` |

### Πώς τρέχεις τα 3 επίπεδα ελέγχου

```bash
# A. Unit (χωρίς Docker stack)
make test-unit

# B. Stack up
docker compose up --build -d
# Demo login στο browser ή:
make e2e

# C. Semantic index (προαιρετικό, χρειάζεται OPENAI_API_KEY)
# Μετά demo login, cookie session, ή από container:
docker compose exec backend python -c "from app.services.knowledge import index_knowledge_to_qdrant; print(index_knowledge_to_qdrant(recreate=True))"
```

### Phase 0 / Phase 1 checklist (ενημερωμένο)

- [x] HITL + DRY_RUN + Docker trial
- [x] Login (Demo / Google / MS) vs Integration OAuth
- [x] Auth lock στα sensitive endpoints
- [x] Knowledge samples + search tool
- [x] Unit + E2E scripts
- [x] CI (GitHub Actions → unit tests + compose config)
- [x] Pilot deploy runbook (`docs/DEPLOY.md`)
- [x] Security checklist (`docs/SECURITY.md`)
- [x] Pilot deploy script + runbook (εκτέλεση στο host του πελάτη)
- [x] Multi-tenant skeleton (orgs API)
- [x] Full tenant isolation (org_id σε conversations/tokens/pending + filters) (Phase 2b)
- [x] Stripe billing skeleton + UI plans (Phase 2c)

---

## Μέρος Α — Ανακεφαλαίωση από την αρχή

### Α.1 Ιδέα & GDPR (αρχή)

Ορίστηκε **AI Executive Secretary** με:

- Ημερολόγιο & email (Microsoft 365 + Google)
- Έρευνα web (Firecrawl)
- Συνομιλία (Ελληνικά / Αγγλικά)
- **GDPR by design:** consent, minimization, encryption, audit, right to erasure, dry-run

### Α.2 Τεχνική επιλογή stack

| Στρώμα | Επιλογή |
|--------|---------|
| Agent | Haystack 3.x Agent + tools |
| Backend | FastAPI |
| Frontend | Next.js 15 + Tailwind |
| DB / cache | PostgreSQL + Redis |
| Research | Firecrawl |
| Deploy | Docker Compose (+ prod hardened) |
| Χαρακτήρας | **Rafaela** (γυναικείος, επαγγελματικός) |

**Όχι** Hostinger AI Agents ως runtime (είναι SaaS business advisors, όχι custom secretary).

### Α.3 Υλοποιημένο prototype (τρέχον)

- System prompt Rafaela + GDPR κανόνες  
- MS365 / Google: list + **propose** (HITL) + execute  
- Encrypted OAuth tokens στη Postgres  
- Conversation memory  
- Pending Actions UI (Έγκριση / Απόρριψη)  
- Login: Google / Microsoft identity **ή** Demo (trial)  
- Integration OAuth ξεχωριστά από login  
- `DRY_RUN=true` για ασφαλείς δοκιμές  
- Docker dev + `docker-compose.prod.yml`  
- Nginx configs + Cloudflare Tunnel οδηγίες  
- Docs: README, DOCUMENTATION, NGINX, PRODUCTION, AGENT_SYSTEM_PROMPT  

### Α.4 HITL & DRY_RUN

```text
Χρήστης ζητά write → propose_* tool → PendingAction
→ UI Έγκριση/Απόρριψη → execute → αν DRY_RUN: προσομοίωση, αλλιώς πραγματικό API
```

### Α.5 «Μάθηση» AI

Το μοντέλο **δεν** fine-tune-άρεται από τα chats αυτόματα.  
Βελτίωση = **μνήμη + RAG + καλύτερα tools/prompt + feedback από HITL**.

### Α.6 RAG & embeddings

- Framework: **μείνε Haystack** (όχι μετάβαση σε LangChain για RAG)  
- Embeddings default: **BGE-M3** (local) ή OpenAI `text-embedding-3-*` (API)  
- Fine-tune BGE-M3 μέσω **FlagEmbedding** όταν υπάρχουν domain data  
- Hyperparameters FT (σύνοψη):

  1. Σταθεροποίησε data + hard negatives  
  2. Ξεκίνα με `lr=1e-5`, `epochs=1`, `group_size=8`, `temp=0.02`  
  3. Ψάξε κυρίως LR και αριθμό/ποιότητα negatives  
  4. Σταμάτα όταν το val nDCG σταματά να ανεβαίνει  
  5. Μετά ρύθμισε chunking, top_k, hybrid, rerank — συχνά πιο αποδοτικά από υπερ-fine-tuning  

### Α.7 Υποδομή

| Επιλογή | Ρόλος |
|---------|--------|
| **Proxmox (γραφείο)** | Μέγιστος έλεγχος, data on-prem, Tunnel |
| **Hostinger VPS** | Εύκολο uptime, λιγότερη sysadmin |
| **Dev** | Docker local σε Windows/Mac + Git |

### Α.8 Πώς τρέχει σήμερα (trial)

```bash
cd ai-secretary-agent
cp .env.example .env          # OPENAI_API_KEY=...
docker compose up --build
# http://localhost:3000 → Demo login
```

---

## Μέρος Β — Όραμα προϊόντος (τι πουλάμε)

**Rafaela** = GDPR-aware AI Executive Secretary για μικρομεσαίες / ομάδες:

- Σύνδεση εταιρικού email & calendar  
- Προσχέδια ενεργειών με **υποχρεωτική ανθρώπινη έγκριση**  
- Εταιρική γνώση (RAG) σε πρότυπα & διαδικασίες  
- Audit trail, retention, export/delete  
- Self-host ή managed EU hosting  

**Διαφοροποίηση:** όχι generic chatbot· **controlled actions + compliance + integrations**.

---

## Μέρος Γ — Roadmap προς επαγγελματικό / πωλήσιμο προϊόν

Φάσεις από **τώρα** → **v1.0 commercial**.

```text
Phase 0  Foundation (σχεδόν έτοιμο)     ████████░░  ~80%
Phase 1  Harden & RAG MVP
Phase 2  Multi-tenant & Billing-ready
Phase 3  UX / Admin / Polish
Phase 4  Compliance pack & Sales assets
Phase 5  Launch (pilot → GA)
```

---

### Phase 0 — Foundation (ολοκλήρωση prototype)  
**Διάρκεια:** 1–2 εβδομάδες · **Κατάσταση:** σε μεγάλο βαθμό υλοποιημένο

| # | Βήμα | Παραδοτέο | Κριτήριο ολοκλήρωσης |
|---|------|-----------|----------------------|
| 0.1 | Σταθεροποίηση repo | GitHub private, `.gitignore`, semver tags | Clone + `compose up` σε καθαρό PC |
| 0.2 | Έλεγχος E2E trial | Demo login → chat → HITL dry-run | Checklist περασμένο |
| 0.3 | Secrets template | `.env.example` / `.env.prod.example` πλήρη | Νέος dev σετ-άρεται σε <30΄ |
| 0.4 | Health + smoke | `/health`, `scripts/test_chat.sh` | CI ή χειροκίνητο green |
| 0.5 | Docs εσωτερικά | README + ROADMAP + ARCHITECTURE | Ομάδα μπορεί onboarding |

**Κώδικας / εντολές:**

```bash
git init && git add . && git commit -m "chore: rafaela foundation"
docker compose up --build
curl -sf http://localhost:8000/health
./scripts/test_chat.sh
```

---

### Phase 1 — Harden + RAG MVP  
**Διάρκεια:** 3–5 εβδομάδες · **Στόχος:** αξιόπιστο single-tenant / pilot

| # | Βήμα | Τι να κάνεις | Αρχεία / τεχνολογία |
|---|------|--------------|---------------------|
| 1.1 | Auth σε όλα τα API | `require_user` σε chat, actions, settings, conversations | `api_auth.py`, `main.py` |
| 1.2 | Integration OAuth με session user | State = authenticated `user_id` | `microsoft.py`, `google.py` |
| 1.3 | Qdrant στο compose | Vector DB service | `docker-compose.yml` |
| 1.4 | Index pipeline | Φάκελος `knowledge/` → chunks → embeddings (BGE-M3 ή OpenAI) | `scripts/index_knowledge.py`, Haystack |
| 1.5 | Tool `search_knowledge` | Agent καλεί RAG όταν χρειάζεται εταιρική γνώση | `tools/knowledge.py`, `secretary_agent.py` |
| 1.6 | Sample knowledge | 10–20 md πρότυπα (email, meeting follow-up) | `knowledge/` |
| 1.7 | Rate limit + audit UI | Ήδη rate limit· απλό admin view logs | optional `frontend` |
| 1.8 | Automated tests | pytest: auth JWT, pending resolve, dry-run path | `backend/tests/` |
| 1.9 | Prod deploy runbook | Proxmox **ή** VPS + Tunnel/Nginx | `docs/DEPLOY.md` |

**Κριτήριο εξόδου Phase 1:**

- Pilot πελάτης: 1 εταιρεία, 1–5 users  
- RAG απαντά από `knowledge/`  
- Κανένα write χωρίς HITL  
- `DRY_RUN` configurable ανά περιβάλλον  

**Σειρά υλοποίησης RAG (κώδικας):**

1. Προσθήκη `qdrant` service  
2. `pip` deps: `haystack-ai`, `qdrant-haystack`, sentence-transformers ή OpenAI embedder  
3. Script index  
4. `@tool search_knowledge(query: str)`  
5. Ενημέρωση system prompt  
6. Re-index σε κάθε deploy knowledge  

---

### Phase 2 — Multi-tenant & commercial core  
**Διάρκεια:** 4–6 εβδομάδες · **Στόχος:** πολλές εταιρείες / τιμολόγηση

| # | Βήμα | Περιγραφή |
|---|------|-----------|
| 2.1 | Organizations (tenants) | Πίνακες `orgs`, `org_members`, `org_id` σε tokens/conversations/actions |
| 2.2 | Roles | `owner` / `admin` / `member` / `viewer` |
| 2.3 | Isolation | Queries πάντα φιλτραρισμένα ανά `org_id` |
| 2.4 | Invites | Email invite + accept flow |
| 2.5 | Usage metering | Messages / tool calls / tokens ανά org (για billing) |
| 2.6 | Plans | Free trial · Starter · Business (limits) |
| 2.7 | Stripe (ή Paddle) | Checkout, webhooks, customer portal |
| 2.8 | Feature flags | π.χ. RAG, multi-calendar ανά plan |

**Σχήμα δεδομένων (απλοποιημένο):**

```text
Org 1─n User
Org 1─n OAuthToken
Org 1─n Conversation / PendingAction / KnowledgeIndex
Org 1─1 Subscription
```

**Κριτήριο εξόδου:** 2 orgs στο ίδιο deployment χωρίς διαρροή δεδομένων.

---

### Phase 3 — UX, Admin, αξιοπιστία

**Done in v1.1:** Onboarding ✅ · Streaming SSE ✅ · Conversation sidebar ✅  
**Pending:** Admin console · notifications · full mobile polish  
**Διάρκεια:** 3–4 εβδομάδες

| # | Βήμα | Περιγραφή |
|---|------|-----------|
| 3.1 | Onboarding wizard | Σύνδεση login → σύνδεση mail/calendar → πρώτο chat |
| 3.2 | Conversation sidebar | Λίστα / μετονομασία / διαγραφή συνομιλιών |
| 3.3 | Streaming answers | SSE ή websocket για αίσθηση «ζωντανού» agent |
| 3.4 | Notifications | Email ή in-app όταν υπάρχει pending action |
| 3.5 | Admin console | Users, audit, retention, dry-run toggle ανά org |
| 3.6 | Error UX | Καθαρά μηνύματα (όχι raw stack traces) |
| 3.7 | Mobile-responsive | Chat + approve σε τηλέφωνο |
| 3.8 | Observability | Structured logs, Sentry/OpenTelemetry, uptime check |

---

### Phase 4 — Compliance & sales readiness  
**Διάρκεια:** 3–5 εβδομάδες (παράλληλα με Phase 3 όπου γίνεται)

| # | Βήμα | Παραδοτέο |
|---|------|-----------|
| 4.1 | DPIA template | Έγγραφο για πελάτες / DPO |
| 4.2 | DPA / ToS / Privacy | Νομικά κείμενα (με δικηγόρο) |
| 4.3 | Subprocessors list | OpenAI, hosting, email provider |
| 4.4 | Data export/delete API | Ολοκληρωμένο GDPR pack στο UI |
| 4.5 | Security checklist | Secrets, TLS, backups, non-root, scans |
| 4.6 | SLA / support tiers | Email support, response times |
| 4.7 | Sales deck + demo script | 10΄ demo: HITL + calendar + RAG |
| 4.8 | Case study pilot | 1–2 πελάτες pilot με μετρήσεις |
| 4.9 | Pricing page | Public ή one-pager |

**Demo script (για πώληση):**

1. Login  
2. «Δείξε τα επόμενα ραντεβού μου»  
3. «Ετοίμασε email follow-up βάσει προτύπου» (RAG)  
4. HITL: Έγκριση σε dry-run  
5. Audit / Ρυθμίσεις GDPR  

---

### Phase 5 — Launch  

| Στάδιο | Ενέργεια |
|--------|----------|
| **Closed pilot** | 3–10 εταιρείες, feedback, bugs |
| **Open beta** | Waitlist, limits, weekly releases |
| **GA v1.0** | Stable API, billing live, docs public |
| **Post-GA** | Mobile app;, Slack/Teams bot, more tools |

---

## Μέρος Δ — Βήμα-βήμα τεχνική ουρά (priority backlog)

### P0 — Πριν από οποιαδήποτε πώληση

1. [ ] Auth υποχρεωτικό σε όλα τα sensitive endpoints  
2. [ ] Ολοκληρωμένο E2E test script (login → chat → pending → resolve)  
3. [ ] Backups Postgres (ημερήσια) + restore drill  
4. [ ] `DRY_RUN` default true σε staging  
5. [ ] SECURITY.md + responsible disclosure  

### P1 — Αξία προϊόντος

6. [ ] RAG MVP (`knowledge/` + Qdrant + tool)  
7. [ ] User preferences (υπογραφή, timezone, γλώσσα) στο prompt  
8. [ ] Streaming chat  
9. [ ] Onboarding wizard  
10. [ ] Multi-tenant org model  

### P2 — Εμπορικό

11. [ ] Stripe subscriptions  
12. [ ] Admin + usage dashboard  
13. [ ] Public docs site  
14. [ ] Status page  

### P3 — Προχωρημένο

15. [ ] BGE-M3 fine-tune σε πελατειακά docs (ανά org ή shared)  
16. [ ] Hybrid BM25 + dense  
17. [ ] Reranker  
18. [ ] Teams/Slack connector  
19. [ ] White-label  

---

## Μέρος Ε — Οδηγίες ανάπτυξης (ομάδα)

### E.1 Branching

```text
main          → production
develop       → integration
feature/*     → νέα δυνατότητα
fix/*         → διορθώσεις
```

### E.2 Definition of Done (κάθε feature)

- [ ] Κώδικας + tests όπου γίνεται  
- [ ] Δουλεύει με `DRY_RUN=true`  
- [ ] Δεν παραβιάζει HITL για writes  
- [ ] Docs / changelog  
- [ ] Review + merge  

### E.3 Τοπικό dev

```bash
cp .env.example .env
docker compose up --build
# UI http://localhost:3000
```

### E.4 Deploy staging/prod

```bash
git pull
docker compose -f docker-compose.prod.yml --env-file .env.prod up -d --build
curl -sf https://api.yourdomain.com/health
```

### E.5 RAG index (μετά Phase 1)

```bash
# παράδειγμα
python scripts/index_knowledge.py --path knowledge/ --recreate
```

### E.6 Fine-tune embeddings (μόνο αν μετρηθεί ανάγκη)

Βλ. εσωτερικό doc / FlagEmbedding:

1. JSONL query/pos/neg  
2. Hard negatives  
3. `lr=1e-5`, `epochs=1`, `group_size=8`, `temp=0.02`  
4. Val nDCG  
5. Re-index με νέο μοντέλο  

---

## Μέρος ΣΤ — Αρχιτεκτονική στόχου (v1 commercial)

```text
                    ┌──────────── Cloudflare / TLS ────────────┐
                    │                                          │
               ┌────▼────┐                              ┌──────▼─────┐
               │ Web UI  │                              │   API      │
               │ Next.js │◄──────── REST / SSE ─────────│  FastAPI   │
               └─────────┘                              │  Haystack  │
                                                        │  Agent     │
                                                        └─────┬──────┘
                    ┌───────────────┬─────────────────┬───────┴────────┐
                    ▼               ▼                 ▼                ▼
               PostgreSQL        Redis            Qdrant         MS/Google
               (tenants,         (cache,          (RAG)          APIs
                HITL, auth)       rate limit)
```

---

## Μέρος Ζ — Εμπορικό πακέτο (τι παραδίδει η εταιρεία)

| Στοιχείο | Περιγραφή |
|----------|-----------|
| **Λογισμικό** | Rafaela cloud **ή** on-prem Docker bundle |
| **Onboarding** | 2–4 ώρες setup integrations + knowledge |
| **Support** | Email / Slack channel ανά tier |
| **Compliance pack** | DPA, DPIA template, security overview |
| **Training** | 1 session για approvers (HITL) |
| **Optional** | Custom RAG corpus, white-label, SLA |

**Προτεινόμενα tiers (ενδεικτικά):**

| Plan | Users | RAG | Integrations | HITL |
|------|-------|-----|--------------|------|
| Trial | 1 | Sample | 1 provider | Ναι |
| Starter | 3 | 100 docs | Google ή MS | Ναι |
| Business | 15 | Unlimited* | Google + MS | Ναι + admin |
| Enterprise | Custom | On-prem / VPC | SSO, DPA | Full audit |

\*fair use

---

## Μέρος Η — Χρονοδιάγραμμα (ενδεικτικό)

| Μήνας | Focus |
|-------|--------|
| **M1** | Phase 0 κλείσιμο + Phase 1 RAG + auth harden |
| **M2** | Phase 1 ολοκλήρωση + πρώτος pilot |
| **M3** | Phase 2 multi-tenant skeleton + metering |
| **M4** | Billing + admin + UX onboarding |
| **M5** | Compliance docs + sales deck + 2ο pilot |
| **M6** | Beta δημόσιο / GA prep |

*(Προσαρμόστε ανά μέγεθος ομάδας: 1 fullstack vs 3–4 άτομα.)*

---

## Μέρος Θ — KPIs επιτυχίας

| KPI | Στόχος pilot |
|-----|----------------|
| Time-to-first-value | < 15΄ από login έως πρώτη χρήσιμη ενέργεια |
| HITL approval rate | Μετρήσιμο· μείωση λαθών vs χωρίς HITL |
| RAG hit usefulness | >70% «χρήσιμο» σε εσωτερικό rating |
| Uptime staging/prod | >99% μηνιαία |
| Critical bugs open | 0 πριν GA |
| Paying conversion (μετά beta) | Ορισμός από sales |

---

## Μέρος Ι — Ρίσκα & μετριασμός

| Ρίσκο | Μετριασμός |
|-------|------------|
| LLM hallucinated send | HITL υποχρεωτικό + DRY_RUN default |
| OAuth / token leak | Encryption at rest, short-lived access, audit |
| Vendor lock OpenAI | Abstraction `LLM_PROVIDER` ήδη· δοκιμή 2ου provider |
| Downtime on-prem | VPS fallback ή SLA on-prem |
| Scope creep | Roadmap phases· P0 πριν features |
| GDPR claims | Νομικός έλεγχος DPA· ελάχιστα δεδομένα στο LLM context |

---

## Μέρος Κ — Checklist «έτοιμο για παρουσίαση πώλησης»

- [ ] Live demo URL (staging) με Demo + sample knowledge  
- [ ] Slide deck 8–12 σελίδες  
- [ ] 10΄ script demo (HITL + RAG + calendar)  
- [ ] One-pager pricing  
- [ ] Security & GDPR one-pager  
- [ ] Pilot agreement template  
- [ ] Recorded demo video (5΄)  
- [ ] FAQ για IT/DPO  

---

## Σύνοψη μιας σελίδας

1. **Τώρα:** Δούλεψε Docker trial, κλείσε Phase 0, άρχισε RAG + auth harden (Phase 1).  
2. **3 μήνες:** Pilot με πραγματική εταιρεία, multi-tenant σε εξέλιξη.  
3. **6 μήνες:** Billing, compliance pack, GA-ready.  
4. **Πουλάτε:** Controlled AI secretary (HITL + integrations + RAG + GDPR), όχι «ακόμα ένα ChatGPT wrapper».  
5. **Μην καθυστερείτε** με fine-tune embeddings πριν μετρήσετε ότι το base RAG δεν αρκεί.

---

## Επόμενη άμεση ενέργεια (αυτή την εβδομάδα)

```text
□ Git remote + προστασία main
□ E2E checklist σε καθαρό μηχάνημα
□ Απόφαση hosting pilot: Proxmox Tunnel vs VPS
□ Ξεκίνημα Phase 1.1–1.5 (auth lock + RAG skeleton)
□ 1 εσωτερικό demo στην ομάδα πωλήσεων
```

---

*Έγγραφο: `docs/ROADMAP.md` — Rafaela AI Secretary*  
*Συμπληρώνει: `DOCUMENTATION.md`, `PRODUCTION.md`, `NGINX.md`, `AGENT_SYSTEM_PROMPT.md`*
