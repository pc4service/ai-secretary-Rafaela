# Rafaela — Audit Log (P0 / P1 / P2 / P3)

Ζωντανό έγγραφο. Κάθε φάση audit γράφεται εδώ με ευρήματα, κατάσταση και
επαλήθευση. Προτεραιότητες κατά `AGENTS.md` → «Priority when asked to make it
professional».

| Priority | Σημασία |
|----------|---------|
| **P0** | Security, auth, data isolation, secret hygiene, unbroken OAuth |
| **P1** | Reliability (errors, timeouts, failover), HITL UX, knowledge quality |
| **P2** | Observability, tests/CI, deploy/backup docs |
| **P3** | Multi-tenant/billing polish, UI polish, extra connectors |

Κατάσταση: ✅ done · 🔧 in progress · ⬜ open · ➖ won't fix (με αιτιολογία)

---

## Φάση 1 — 2026-08-16 · Audit knowledge/RAG + Firecrawl

**Σκοπός:** έλεγχος των μη-committed αλλαγών (knowledge base, Qdrant, Firecrawl
scrape → knowledge) πριν το commit. Επεκτάθηκε στο HITL γιατί το νέο
`knowledge_save_page` περνά από το ίδιο write-path.

**Εύρος:** `services/knowledge.py`, `services/firecrawl_web.py`,
`tools/knowledge_tools.py`, `tools/firecrawl_tools.py`, `main.py`,
`agent/secretary_agent.py`, `core/config.py`, `docker-compose*.yml`,
`backend/tests/`, `knowledge/`.

### P0 — Security critical

| # | Εύρημα | Κατάσταση |
|---|--------|-----------|
| P0-1 | Broken access control στα `/actions/*` — χωρίς auth, `user_id` από query/body | ✅ done |
| P0-2 | Καμία επαλήθευση ιδιοκτησίας στο resolve — οποιοσδήποτε ενέκρινε ενέργεια οποιουδήποτε | ✅ done |
| P0-3 | Τα `propose_*` tools έγραφαν πάντα `demo-user` — όλοι οι χρήστες σε ένα bucket | ✅ done |
| P0-4 | Το LLM μπορούσε να επιλέξει `user_id` (ποιανού tokens/δεδομένα) | ✅ done |
| P0-5 | Live `ms_send_email` / `google_send_email` branches στον executor | ✅ done |

**Διόρθωση αρχικής εκτίμησης (P0-3):** στο πρώτο report είχε αναφερθεί ότι το
`action.payload["user_id"] = body.user_id` επέτρεπε στον caller να επιλέξει
ποιανού τα tokens εκτελούνται. Στην πραγματικότητα ήταν **no-op** (detached
SQLAlchemy object· το `resolve_action` ξαναδιαβάζει σε νέο session). Η πραγματική
συνέπεια ήταν ότι το `run_agent` δεχόταν `user_id` αλλά δεν το περνούσε ποτέ στα
tools, άρα κάθε pending action γραφόταν και εκτελούνταν ως `demo-user`.

### P1 — Reliability / HITL UX / knowledge quality

| # | Εύρημα | Κατάσταση |
|---|--------|-----------|
| P1-1 | Το approval δείχνει μόνο metadata — ο χρήστης εγκρίνει χωρίς να δει το περιεχόμενο | ✅ done |
| P1-2 | Prompt injection: το scraped περιεχόμενο μπαίνει ως οδηγία, όχι ως δεδομένο | ✅ done |
| P1-3 | `POST /knowledge/index` χωρίς επιβολή auth· `recreate=true` σβήνει το collection | ✅ done |
| P1-4 | Αδύναμο SSRF/scope guard (literal substrings, όχι private ranges) | ✅ done |

### P2 — Observability / tests / docs

| # | Εύρημα | Κατάσταση |
|---|--------|-----------|
| P2-1 | Καμία κάλυψη tests για `firecrawl_tools.py` και τα νέα endpoints | ✅ done |
| P2-2 | Κάθε save κάνει re-embed **όλων** των chunks, όχι μόνο του νέου αρχείου | ✅ done |
| P2-3 | `_openai_key()` — μπερδεμένη λογική επιλογής key, χρειάζεται σχόλιο | ✅ done |

### Θετικά ευρήματα (να μη χαλάσουν)

- Path-traversal guard στο `save_knowledge_markdown` (`knowledge.py:94-102`)
- Send-email tools σκόπιμα εκτός `_default_tools()` — mail read-only στην πράξη
- Graceful degradation: χωρίς Qdrant/embeddings πέφτει σε keyword-only
- Prod compose: qdrant χωρίς `ports:`, με `mem_limit` + `no-new-privileges`
- Cap μεγέθους (`_MAX_CHARS`) στο scraped content

---

## Φάση 2 — 2026-08-16 · Υλοποίηση P0

### Τι άλλαξε

| Αρχείο | Αλλαγή |
|--------|--------|
| `services/agent_context.py` | **Νέο.** Contextvar με τον acting user· τα tools το διαβάζουν αντί για model-supplied `user_id` |
| `agent/secretary_agent.py` | `run_agent` δένει τον χρήστη με `set_agent_user()` πριν τρέξει tool· GDPR stubs χρησιμοποιούν το context |
| `tools/ms365_tools.py` | `_normalize_user_id` → context· resolve στο σώμα του tool· `create_pending_action(user_id=uid)` |
| `tools/google_tools.py` | Ίδιο μοτίβο (νέο `_normalize_user_id`) |
| `tools/firecrawl_tools.py` | `knowledge_save_page` γράφεται με τον σωστό owner |
| `services/pending_actions.py` | `resolve_action(owner_user_id=…)` — έλεγχος ιδιοκτησίας στο ίδιο transaction· executor καλείται με `action.user_id` |
| `main.py` | `require_user` και στα 3 `/actions/*`· `BLOCKED_ACTION_TYPES`· `execute_action(…, user_id)`· `ActionResolveRequest.user_id` αφαιρέθηκε |

### Σχεδιαστικές αποφάσεις

- **404 αντί για 403** σε ξένο action: δεν διαρρέει η ύπαρξη IDs άλλων χρηστών.
  Καταγράφεται `pending_action_owner_mismatch` warning.
- **Το context διαβάζεται στο σώμα του tool**, όχι μέσα στο `_inner()`: το
  `_run()` εκτελεί σε `ThreadPoolExecutor` worker που **δεν** κληρονομεί
  contextvars. Αυτό είναι το λεπτό σημείο — μη το μετακινήσεις μέσα στο `_inner`.
- **Hardcoded `BLOCKED_ACTION_TYPES`** αντί για env flag, ώστε να μην ανοίγει
  κατά λάθος από λανθασμένο `.env` σε production. Τρίτο στρώμα πάνω από τα
  μη-registered tools και τα OAuth scopes.

### Επαλήθευση

```
17 passed  (νέα: tests/test_agent_context.py, tests/test_action_guards.py)
```

| Έλεγχος | Αποτέλεσμα |
|---------|-----------|
| pending/history/resolve χωρίς auth | 401 |
| ίδια με demo session | 200 |
| attacker βλέπει action του victim στη λίστα | False |
| attacker resolve ξένου action | `not_found` + warning |
| owner resolve | `rejected` OK |
| tool με `user_id="attacker-tries-this"` υπό `set_agent_user("google-abc-999")` | `stored owner: google-abc-999`, override αγνοήθηκε |
| `/health`, `/knowledge/status` | OK |
| chat με tool prompt (follow-up template) | απαντά από το πρότυπο |

---

## Φάση 3 — 2026-08-17 · Υλοποίηση P1

### Τι άλλαξε

| Αρχείο | Αλλαγή |
|--------|--------|
| `services/untrusted.py` | **Νέο.** `UNTRUSTED_OPEN/CLOSE`, `wrap_untrusted()`, `strip_delimiters()` |
| `tools/firecrawl_tools.py` | `_content_preview()` — 1500 χαρακτήρες του πραγματικού περιεχομένου στο approval· scrape output πλαισιωμένο |
| `services/knowledge.py` | `format_search_for_agent` fencing· η οδηγία μετακινήθηκε **έξω** από το μπλοκ |
| `agent/secretary_agent.py` | `research_with_firecrawl` πλαισιωμένο· νέος κανόνας injection στο system prompt |
| `tools/ms365_tools.py`, `tools/google_tools.py` | Λίστες email πλαισιωμένες (τρίτου περιεχόμενο) |
| `services/firecrawl_web.py` | SSRF guard: private/loopback/link-local/reserved IPs, internal suffixes, credentials-in-URL, μη-web ports |
| `main.py` | `/knowledge/search` + `/index` → `require_user`· audit στο index |
| `components/PendingActions.tsx` | Label για `knowledge_save_page` |
| `AGENTS.md`, `docs/ROADMAP.md`, `docs/DOCUMENTATION.md`, `docs/SECURITY.md` (+ `Rafaela-*` mirrors) | Ενημέρωση εντολών/πινάκων που άλλαξαν λόγω auth |

### Σχεδιαστικές αποφάσεις

- **`/knowledge/status` παραμένει ανοιχτό**: είναι το τεκμηριωμένο health probe και
  επιστρέφει μόνο μετρήσεις/ονόματα αρχείων — ποτέ περιεχόμενο. Το `/search`
  κλείδωσε γιατί επιστρέφει το ίδιο το εσωτερικό υλικό.
- **Το fencing αφαιρεί forged delimiters**: χωρίς αυτό, ένα έγγραφο μπορεί να
  «κλείσει» το μπλοκ νωρίς και να μιλήσει σαν σύστημα. Καλύπτεται με test.
- **Ο SSRF guard είναι scope enforcement, όχι πλήρης άμυνα**: το fetch γίνεται από
  την υποδομή του Firecrawl, και ένα hostname που κάνει resolve σε private IP
  περνά ακόμα. Τεκμηριωμένο ρητά στο docstring για να μη θεωρηθεί εγγύηση.

### Επαλήθευση

```
40 passed  (νέα: tests/test_untrusted.py· επέκταση tests/test_firecrawl_web.py)
```

| Έλεγχος | Αποτέλεσμα |
|---------|-----------|
| `/knowledge/status` χωρίς auth | 200 (σκόπιμα ανοιχτό) |
| `/knowledge/search` χωρίς auth · με auth | 401 · 200 |
| `/knowledge/index` χωρίς auth · με auth | 401 · 200 |
| Live injection: έγγραφο με forged `END_UNTRUSTED_CONTENT` | 1 open / 1 close marker· η επίθεση έμεινε **μέσα** στο fence ως δεδομένο |
| SSRF: 13 blocked targets (private/loopback/metadata/IPv6/creds/ports/wp-admin/crm) | όλα `ValueError` |
| 4 δημόσια URLs (incl. ports 80/443) | επιτρέπονται |

### Εκκρεμεί για P2

Πέρα από τα P2-1..3 της Φάσης 1, προστέθηκε:

| # | Θέμα | Κατάσταση |
|---|------|-----------|
| P2-4 | Τα `backend/tests/` δεν είναι mounted στο container — τρέχουν με `docker compose cp`. Χρειάζεται mount ή CI job | ✅ done |

---

## Φάση 4 — 2026-08-18 · Υλοποίηση P2

### Νέα ευρήματα κατά την υλοποίηση

| # | Εύρημα | Κατάσταση |
|---|--------|-----------|
| P2-5 | **Το CI δεν έχει τρέξει ποτέ**: `ci.yml` ενεργοποιείται σε `main`/`develop`, το branch είναι `master` | ✅ done |
| P2-6 | Το CI εγκαθιστούσε χειροδιαλεγμένες εξαρτήσεις — τα νέα guard tests (import `app.main`) θα έσκαγαν | ✅ done |

### Τι άλλαξε

| Αρχείο | Αλλαγή |
|--------|--------|
| `backend/pytest.ini` | **Νέο.** `testpaths`, `asyncio_mode=auto` — τέλος τα CLI flags |
| `docker-compose.yml` | Mount `./backend/tests:/app/tests:ro` + `pytest.ini` (dev only· **όχι** στο prod) |
| `Makefile` | `make test` → pytest στο container· το παλιό chat smoke έγινε `make test-chat`· `make knowledge` κάνει demo login πριν το `/search` |
| `.github/workflows/ci.yml` | Trigger και σε `master`· `pip install -r requirements.txt`· `QDRANT_URL=""` τεκμηριωμένο |
| `services/knowledge.py` | Incremental indexing με `_chunk_hash` + `_stored_hashes`· purge stale points· docstring στο `_openai_key` |
| `tests/test_firecrawl_tools.py`, `tests/test_api_guards.py`, `tests/test_knowledge_index.py` | **Νέα** |

### Σχεδιαστικές αποφάσεις

- **Το hash καλύπτει μόνο title+text** — ό,τι πραγματικά embed-άρεται. Αλλαγή σε
  tags ή score δεν προκαλεί άσκοπο re-embed (καλύπτεται με test).
- **Migration χωρίς ειδικό χειρισμό**: points από την παλιά έκδοση δεν έχουν
  `chunk_hash`, οπότε διαβάζονται ως `""` → re-embed μία φορά, μετά skip.
- **Recursion μία φορά** στο dim mismatch: το retry ξεκινά χωρίς collection, άρα
  παίρνει dim από το δικό του πρώτο batch και δεν ξανασυγκρούεται.
- **`_stored_hashes` καταπίνει σφάλματα** → `{}` = «ξανα-embed-άρε τα πάντα».
  Χειρότερη περίπτωση κόστος, ποτέ crash.
- **Τα guard tests δεν σηκώνουν lifespan** (`TestClient` χωρίς context manager),
  ώστε να τρέχουν χωρίς DB/Qdrant — άρα και στο CI.

### Επαλήθευση

```
63 passed   (από 40)
63 passed   και υπό συνθήκες CI: QDRANT_URL="" , χωρίς DB
```

| Έλεγχος | Αποτέλεσμα |
|---------|-----------|
| `make test` χωρίς `docker compose cp` | τρέχει από το mount |
| Index 1η φορά · 2η · 3η | 21 indexed · 0/21 skipped · 0/21 skipped |
| Νέο αρχείο | indexed=1, skipped=21 |
| Επεξεργασία αρχείου | indexed=1, skipped=21 |
| Διαγραφή αρχείου | removed=1, chunks πίσω στο baseline |
| `/health`, `/knowledge/status`, `/search` με session | OK |

**Κόστος:** τα embeddings έπαψαν να ξαναϋπολογίζονται σε κάθε boot και κάθε save
— μόνο τα αλλαγμένα chunks.

---

## Εκκρεμή (P3 και λοιπά)

| # | Θέμα | Κατάσταση |
|---|------|-----------|
| P3-1 | `REQUIRE_AUTH` αναφέρεται σε `SECURITY.md`/CI αλλά δεν υπάρχει στο `config.py` | ✅ done |
| P3-2 | Το `knowledge/` είναι κοινό για όλους τους χρήστες — δεν υπάρχει per-tenant διαχωρισμός | ⬜ open |
| P3-3 | Rate limiter in-memory per-IP — δεν αντέχει multi-worker/multi-instance (θέλει Redis) | ⬜ open |

---

## Φάση 5 — 2026-08-18 · P3-1 (REQUIRE_AUTH) + IDOR στις συνομιλίες

### ⚠ Εύρημα P0 που είχε ξεφύγει από τη Φάση 1

Υλοποιώντας το `REQUIRE_AUTH` βρέθηκε ότι τα `/conversations/*` είχαν **την ίδια
ευπάθεια με τα `/actions/*`**, στα πιο ευαίσθητα δεδομένα του προϊόντος:

| # | Εύρημα | Κατάσταση |
|---|--------|-----------|
| P0-6 | `GET /conversations?user_id=X` — λίστα συνομιλιών οποιουδήποτε χρήστη | ✅ done |
| P0-7 | `GET /conversations/{id}/messages` — **καμία απολύτως** επαλήθευση ιδιοκτησίας· το `get_conversation_messages()` δεν δεχόταν καν `user_id`. Όποιος ήξερε ένα conversation id διάβαζε το ιστορικό | ✅ done |
| P0-8 | `DELETE /conversations/{id}?user_id=X` — διαγραφή συνομιλίας άλλου χρήστη | ✅ done |
| P0-9 | `/auth/{ms,google}/login?user_id=X` — το OAuth `state` καθόριζε σε ποιον λογαριασμό αποθηκεύονται τα tokens | ✅ done |

**Γιατί ξέφυγε:** η Φάση 1 σκόπιμα περιορίστηκε στο diff (knowledge/Firecrawl) και
επεκτάθηκε στο HITL μόνο επειδή το `knowledge_save_page` περνά από εκεί. Τα
`/conversations/*` δεν ήταν στο diff. Μάθημα: ο έλεγχος «ποια endpoints δέχονται
`user_id` από τον client» έπρεπε να γίνει καθολικά από την αρχή, όχι ανά diff.

### Τι άλλαξε

| Αρχείο | Αλλαγή |
|--------|--------|
| `core/config.py` | `REQUIRE_AUTH: bool = False` + property `auth_required` (πάντα True σε production) |
| `api_auth.py` | `resolve_user_id()` — ταυτότητα **μόνο** από session· 401 όταν `auth_required`, αλλιώς demo fallback για local dev |
| `services/conversation.py` | `get_conversation_messages(..., user_id=None)` με join στο `Conversation.user_id` |
| `main.py` | `/conversations/*`, `/settings`, `/chat`, `/chat/stream`, `/auth/*/login` → `resolve_user_id`· `/auth/*/disconnect` → `require_user`· `user_id` αφαιρέθηκε από το `ChatRequest` |
| `.env.example`, `docs/SECURITY.md`, `ci.yml` | Τεκμηρίωση· το CI τρέχει πλέον με `REQUIRE_AUTH=true` |

### Σχεδιαστικές αποφάσεις

- **Δύο επίπεδα**: `require_user` (σκληρό 401) για ενέργειες που αλλάζουν
  εξωτερική κατάσταση — approve/reject, disconnect. `resolve_user_id` (demo
  fallback εκτός production) για user-scoped reads, ώστε να μη σπάσει το local
  `curl`. Σε production δεν υπάρχει διαφορά: και τα δύο απαιτούν session.
- **Η production δεν εμπιστεύεται το flag**: το `auth_required` επιστρέφει True
  σε production ακόμη κι αν `REQUIRE_AUTH=false`, γιατί ένα λάθος `.env` δεν
  πρέπει να ανοίγει τα δεδομένα όλων.
- **Το `user_id` στο `get_conversation_messages` παραμένει optional**, ώστε
  internal callers που έχουν ήδη φορτώσει τη συνομιλία για γνωστό ιδιοκτήτη να
  μην επαναλαμβάνουν τον έλεγχο — αλλά το docstring λέει ρητά ότι κάθε request
  path οφείλει να το περνά.

### Επαλήθευση

```
75 passed  (από 63· νέο tests/test_require_auth.py)
75 passed  και με REQUIRE_AUTH=true
```

Ζωντανός έλεγχος IDOR (πριν/μετά, με πραγματική DB):

| Σενάριο | Αποτέλεσμα |
|---------|-----------|
| Ιδιοκτήτης διαβάζει τη συνομιλία του | 1 μήνυμα ✅ |
| Επιτιθέμενος διαβάζει την ίδια συνομιλία | **0 μηνύματα** |
| Επιτιθέμενος τη βλέπει στη λίστα του | False |
| Επιτιθέμενος τη διαγράφει | False |

Ζωντανός έλεγχος με `REQUIRE_AUTH=true` (uvicorn σε δεύτερο port):

| Endpoint | Anonymous |
|----------|-----------|
| `/health`, `/knowledge/status` | 200 (σκόπιμα ανοιχτά) |
| `/conversations`, `/conversations/{id}/messages`, `/settings` | 401 |
| `/auth/microsoft/login?user_id=victim`, `/auth/google/login?user_id=victim` | 401 |
| `/actions/pending`, `/chat` | 401 |

---

## Φάση 6 — 2026-08-18 · Καθολικό authorization audit (report only)

Μετά το P0-6..9 που ξέφυγε, έλεγχος **όλων** των endpoints αντί ανά diff.

### Μεθοδολογία — και ένα λάθος που έπιασα εγκαίρως

Το πρώτο πέρασμα έκανε introspection στο `app.routes` με `isinstance(r, APIRoute)`
και βρήκε **26** routes. Το πραγματικό OpenAPI schema έχει **34**: το FastAPI
κρατά τα included routers ένθετα ως `_IncludedRouter`, οπότε ολόκληρο το
`/api/v1/login/*` ήταν αόρατο. Χωρίς cross-check με το `openapi.json` θα είχα
ξαναδηλώσει «όλα καθαρά» έχοντας δει το 76% της επιφάνειας.

**Κανόνας για επόμενα audits:** πηγή αλήθειας είναι το `openapi.json` του ζωντανού
server, όχι το introspection.

### Ευρήματα

| # | Priority | Εύρημα | Κατάσταση |
|---|----------|--------|-----------|
| P0-10 | **P0** | `/auth/{microsoft,google}/callback`: το `state` χρησιμοποιείται **απευθείας ως user_id** χωρίς καμία επαλήθευση. Μη-αυθεντικοποιημένος καλών γράφει OAuth tokens σε λογαριασμό της επιλογής του | ✅ done |
| P1-5 | P1 | `/api/v1/system-prompt` χωρίς auth — εκθέτει πλήρη πολιτική agent, λίστα tools και τους κανόνες anti-injection | ✅ done |
| P1-6 | P1 | Hardcoded `http://localhost:3000` redirect στα MS/Google callbacks ενώ αλλού χρησιμοποιείται `settings.FRONTEND_URL` — σπάει το connect flow σε deploy | ✅ done |
| P1-7 | P1 | `/internal/codex/v1/chat/completions` εκτεθειμένο στη δημόσια πόρτα· bearer relay που θα έπρεπε να είναι internal-only | ⬜ open |
| P2-7 | P2 | `_oauth_states` και `_pending` in-memory — με >1 worker το login/connect σπάει (state σε worker A, callback σε worker B)· χάνονται σε restart | ✅ done |
| P2-8 | P2 | `/docs`, `/redoc`, `/openapi.json` πάντα ενεργά — σε production δημοσιεύουν όλη την επιφάνεια API | ✅ done |
| P2-9 | P2 | CORS: `http://localhost:3000` προστίθεται πάντα με `allow_credentials=True`, και σε production | ✅ done |

### Λεπτομέρεια για το P0-10

Το **σωστό μοτίβο υπάρχει ήδη στο ίδιο αρχείο**: το `_openai_oauth_callback`
κάνει `pop_pending(state)` και παίρνει το `user_id` από την **αποθηκευμένη**
εγγραφή, όχι από το URL. Τα login callbacks (`api_auth.py`) επίσης επαληθεύουν
το state. Μόνο τα δύο integration callbacks αποκλίνουν:

```python
# ms_callback / google_callback — state == user_id, χωρίς έλεγχο
await save_oauth_token(user_id=state, provider="microsoft", ...)
```

Δεν απαιτείται καν αλληλεπίδραση του θύματος: ο επιτιθέμενος καλεί το callback
με δικό του `code` και `state=<victim>`, και το mailbox/calendar του συνδέεται
στον λογαριασμό του θύματος. Από εκεί, ο agent του θύματος διαβάζει δεδομένα του
επιτιθέμενου (data poisoning) και τα προτεινόμενα ραντεβού γράφονται στο δικό
του ημερολόγιο.

Η διόρθωση του P3-1 (το `state` βγαίνει πλέον από το session κατά την **έναρξη**)
δεν καλύπτει το callback, που εξακολουθεί να εμπιστεύεται ό,τι του έρθει.

### Επαληθευμένα σωστά

- Login callbacks επαληθεύουν `state` έναντι server-side store ✅
- `/login/demo` επιστρέφει 403 εκτός `development`/`trial` ✅
- OpenAI callback: `user_id` από το pending record, όχι από το URL ✅
- **Κανένα** endpoint δεν δέχεται πλέον `user_id` από query/body ✅
- Όλα τα user-scoped endpoints αντλούν ταυτότητα από το session ✅

### Πίνακας κάλυψης (34 routes)

| Κατηγορία | Πλήθος |
|-----------|--------|
| `require_user` (σκληρό 401) | 7 |
| `resolve_user_id` (session· demo fallback εκτός production) | 8 |
| Σκόπιμα δημόσια (`/`, `/health`, `/knowledge/status`, login start/providers/me/logout, demo) | 11 |
| OAuth callbacks (δημόσια εξ ορισμού — 4 από 4 χρειάζονται state validation· **2 δεν το έχουν**) | 5 |
| Χωρίς auth, υπό εξέταση (`/system-prompt`, `/internal/codex/*`) | 2 |

---

## Φάση 7 — 2026-08-18 · P0-10 + P1-6

### Τι άλλαξε

| Αρχείο | Αλλαγή |
|--------|--------|
| `services/oauth_state.py` | **Νέο.** `issue()` / `consume()` — opaque, single-use, TTL 10′, δεμένο σε provider |
| `main.py` | `ms_login`/`google_login` εκδίδουν state· τα callbacks το εξαργυρώνουν και παίρνουν από εκεί το `user_id`· redirects μέσω `settings.FRONTEND_URL` |

Το μοτίβο ευθυγραμμίζεται με το `_openai_oauth_callback`, που ήδη το έκανε σωστά.

### Σχεδιαστικές αποφάσεις

- **Single-use + TTL**: ένα state που διέρρευσε από logs/referer δεν ξαναχρησιμοποιείται.
- **Δέσιμο σε provider**: state του Microsoft flow δεν εξαργυρώνεται στο Google callback.
- **Redirect σε σελίδα σφάλματος αντί για 400**: ο νόμιμος χρήστης με ληγμένο state
  βλέπει κάτι χρήσιμο, ενώ η απόρριψη καταγράφεται ως `oauth_state_rejected`.
- **Παραμένει in-memory** όπως το login store — το P2-7 (Redis) ισχύει και εδώ και
  τεκμηριώνεται στο docstring. *(Διορθώθηκε στη Φάση 8.)*

### Επαλήθευση

```
85 passed  (από 75· νέο tests/test_oauth_state.py)
```

Ζωντανή επίθεση στον τρέχοντα server:

| Σενάριο | Πριν | Τώρα |
|---------|------|------|
| `GET /auth/microsoft/callback?code=…&state=demo-user` χωρίς session | tokens γράφονταν στον `demo-user` | **307 → `?ms=error`**, κανένα token, warning στα logs |
| `GET /auth/google/callback?...&state=demo-user` | ομοίως | **307 → `?google=error`** |
| Νόμιμο flow | `state=demo-user` (το ίδιο το user id) | `state=72hS__0rMEEaLOPqkwl9T-…` (opaque) |

---

## Φάση 8 — 2026-08-18 · P2-7 (shared OAuth state)

### Τι άλλαξε

| Αρχείο | Αλλαγή |
|--------|--------|
| `services/state_store.py` | **Νέο.** `StateStore(namespace, ttl)` με `put`/`pop`· Redis όταν είναι διαθέσιμο, αλλιώς per-process fallback |
| `api_auth.py` | `_oauth_states` dict → `StateStore("login", 600)`· ο έλεγχος επαληθεύει και τον provider |
| `services/openai_oauth.py` | `_pending` dict → `StateStore("openai_oauth", 600)` (κρατά το PKCE verifier) |
| `services/oauth_state.py` | Χρησιμοποιεί `StateStore`· έφυγε η χειροκίνητη λογική TTL/prune |

Και τα τρία in-memory stores που εντόπισε η Φάση 6 μεταφέρθηκαν.

### Σχεδιαστικές αποφάσεις

- **Sync κλήσεις**: ένα μικρό round trip ανά OAuth flow (όχι ανά request), οπότε
  το κόστος είναι αμελητέο και κανένα call site δεν χρειάστηκε να γίνει async.
- **Fallback αντί για σφάλμα**: αν λείπει/πέσει το Redis, ο κάθε process
  χρησιμοποιεί δικό του dict. Σωστό για single worker και όχι χειρότερο από πριν.
  Καλύπτεται με test όπου ο client πετάει exception.
- **Παράπλευρο κέρδος ασφάλειας**: το single-use είναι πλέον **καθολικό**. Πριν,
  ένα replayed state που έφτανε σε άλλο worker θα γινόταν δεκτό.
- **TTL από το Redis** (`SETEX`), όχι χειροκίνητο prune — επιβεβαιώθηκε `ttl=600`.

### Επαλήθευση

```
94 passed  (από 85· νέο tests/test_state_store.py)
```

Το ουσιαστικό τεστ — state που εκδίδεται σε μία διεργασία, εξαργυρώνεται σε **άλλη**
(δύο ξεχωριστά `python` invocations στη θέση δύο workers):

```
worker A issued: 2yASEqNOk4Q7Ii10k1n9yFCtqhbyTNJG
worker B resolved user: google-worker-A
replay rejected (good)
```

| Έλεγχος | Αποτέλεσμα |
|---------|-----------|
| Εγγραφές όντως στο Redis με TTL | `keys=2`, `ttl=600` |
| Login callback με πλαστό state | 307 → `?error=invalid_state` |
| `/health`, demo login, `/settings`, `/conversations` | 200 |

---

## Φάση 9 — 2026-08-19 · P1-5 + P2-8 + P2-9 (σφίξιμο δημόσιας επιφάνειας)

### Τι άλλαξε

| Αρχείο | Αλλαγή |
|--------|--------|
| `main.py` | `/system-prompt` → `require_user`· `docs_urls(environment)` κλείνει docs/redoc/openapi σε production· `_cors_origins()` πετάει loopback origins σε production |
| `.env.example` | Προστέθηκε `CORS_ORIGINS` με εξήγηση |

### Σχεδιαστικές αποφάσεις

- **Το `CORS_ORIGINS` default περιέχει localhost**, οπότε δεν αρκεί να μην
  προσθέτουμε localhost — σε production φιλτράρονται **όλα** τα loopback origins,
  ακόμη κι αν είναι ρητά ρυθμισμένα. Καταγράφεται `cors_loopback_origins_dropped`.
- **Το `FRONTEND_URL` μπαίνει αυτόματα** στα allowed origins, ώστε ένα σωστά
  ρυθμισμένο deploy να δουλεύει χωρίς διπλή ρύθμιση.
- **Fail closed**: αν σε production δεν μείνει κανένα origin, το CORS μπλοκάρει
  τα πάντα και λογκάρεται `cors_no_origins_configured` — αντί για σιωπηλό
  permissive fallback.
- **`docs_urls()` ως καθαρή συνάρτηση** αντί για inline συνθήκη: η πρώτη μου
  εκδοχή το έλεγχε με `importlib.reload` του `app.main`, που αντικαθιστούσε
  module objects τα οποία κρατούσαν άλλα test modules. Δουλεύει, αλλά είναι
  εύθραυστο — προτιμήθηκε testable λογική χωρίς reload.

### Επαλήθευση

```
105 passed  (από 94· νέο tests/test_public_surface.py)
```

Ζωντανό instance με `ENVIRONMENT=production`, `FRONTEND_URL=https://rafaela.example.com`:

| Έλεγχος | Production | Dev (trial) |
|---------|-----------|-------------|
| `/docs`, `/redoc`, `/openapi.json` | **404** | 200 |
| `/system-prompt` anonymous | **401** | 401 |
| `/system-prompt` με session | — | 200 |
| `/health` | 200 | 200 |
| demo login | **403** (προϋπάρχον guard) | 200 |
| CORS preflight από `http://localhost:3000` | **κανένα allow-origin** | επιτρέπεται |
| CORS preflight από `https://rafaela.example.com` | `access-control-allow-origin` OK | — |

Στα logs production: `cors_loopback_origins_dropped origins=['http://localhost:3000', 'http://localhost:8000']`.

### Σημείωση για επόμενα audits

Με το P2-8, το `/openapi.json` **δεν** είναι διαθέσιμο σε production. Ο κανόνας
της Φάσης 6 (πηγή αλήθειας το OpenAPI αντί για introspection) ισχύει, αλλά ο
έλεγχος πρέπει να τρέχει σε dev/trial instance.
