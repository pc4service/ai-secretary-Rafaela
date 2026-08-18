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
| P3-1 | `REQUIRE_AUTH` αναφέρεται σε `SECURITY.md`/CI αλλά δεν υπάρχει στο `config.py` | ⬜ open |
| P3-2 | Το `knowledge/` είναι κοινό για όλους τους χρήστες — δεν υπάρχει per-tenant διαχωρισμός | ⬜ open |
| P3-3 | Rate limiter in-memory per-IP — δεν αντέχει multi-worker/multi-instance (θέλει Redis) | ⬜ open |
