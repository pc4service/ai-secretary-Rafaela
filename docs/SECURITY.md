# Rafaela — Security Checklist (Pilot / Sales)

Σύντομο έγγραφο για IT / DPO / pilot πελάτη.

---

## 1. Αρχές σχεδίασης

| Αρχή | Υλοποίηση |
|------|-----------|
| Least privilege | Ξεχωριστά OAuth scopes login vs mail/calendar |
| Human-in-the-loop | Κάθε write (event / knowledge save) → propose → approve |
| Dry-run default | `DRY_RUN=true` μέχρι ρητή ενεργοποίηση |
| Encryption at rest | OAuth tokens με Fernet |
| Auth session | HTTP-only cookie JWT · login υπάρχει · **`REQUIRE_AUTH` lock δεν είναι ακόμα στο config** |
| Data isolation | `/actions/*` απαιτούν session· κάθε ενέργεια ελέγχεται ως προς τον ιδιοκτήτη (ξένο action → 404, χωρίς διαρροή ύπαρξης) |
| Agent identity | Το LLM δεν επιλέγει `user_id` — δένεται server-side ανά run (`services/agent_context.py`) |
| Mail read-only | 3 στρώματα: tools εκτός agent · scopes χωρίς `Mail.Send`/`gmail.send` · `BLOCKED_ACTION_TYPES` στον executor |
| Prompt injection | Ανακτημένο περιεχόμενο (web, knowledge, emails) πλαισιώνεται ως δεδομένα· forged delimiters αφαιρούνται (`services/untrusted.py`) |
| Audit | `audit_logs` για chat, OAuth, resolve actions, knowledge index |
| Data minimization | Tools ζητούν μόνο ό,τι χρειάζεται |

---

## 2. Προ-pilot checklist

### Infrastructure

- [ ] TLS παντού (Cloudflare / Let’s Encrypt)
- [ ] DB & Redis **όχι** εκτεθειμένα στο internet
- [ ] Containers non-root όπου γίνεται (prod Dockerfiles)
- [ ] Ισχυρά `SECRET_KEY` / `POSTGRES_PASSWORD` (όχι defaults)
- [ ] Firewall: μόνο 22 (περιορισμένο), 80, 443
- [ ] Αυτόματα backups + μία δοκιμή restore

### Application

- [ ] `REQUIRE_AUTH=true`
- [ ] `COOKIE_SECURE=true` πίσω από HTTPS
- [ ] `DRY_RUN=true` για pilot εβδομάδα 1
- [ ] CORS μόνο trusted frontend origins
- [ ] Rate limiting ενεργό
- [ ] OAuth redirect URIs ακριβώς HTTPS production URLs

### Process

- [ ] Ποιος εγκρίνει HITL στον πελάτη (ρόλος)
- [ ] Διαδικασία incident (διαρροή token / λάθος send)
- [ ] Λίστα subprocessors (OpenAI, host, Cloudflare…)
- [ ] DPA υπογεγραμμένο πριν πραγματικά δεδομένα πελάτη

---

## 3. Δεδομένα που επεξεργάζεται η Rafaela

| Κατηγορία | Παράδειγμα | Σημείωση |
|-----------|------------|----------|
| Λογαριασμός | email, όνομα από IdP | Login OAuth |
| Integration tokens | access/refresh | Κρυπτογραφημένα στη DB |
| Συνομιλίες | chat messages | Retention ρυθμιζόμενο |
| Pending actions | προτεινόμενα emails/events | Μέχρι approve/reject |
| Knowledge | εταιρικά md/pdf στο index | Ο πελάτης ελέγχει τι ανεβάζει |
| Audit | ενέργειες συστήματος | Μεγαλύτερο retention |

**Δεν** πρέπει να μπαίνουν στο knowledge index ειδικές κατηγορίες δεδομένων χωρίς νομική βάση.

---

## 4. Αν κάτι πάει στραβά

| Συμβάν | Ενέργεια |
|--------|----------|
| Υποψία διαρροής token | Disconnect integration + rotate `SECRET_KEY` / encryption key + revoke OAuth app sessions |
| Λάθος αποστολή email | HITL θα έπρεπε να το είχε μπλοκάρει· review logs · `DRY_RUN` μέχρι root cause |
| Unauthorized API access | Ελέγξτε cookies, CORS, `REQUIRE_AUTH` · rotate secrets |
| Ransomware / host compromise | Απομόνωση VM · restore από backup · ενημέρωση πελάτη κατά DPA |

---

## 5. Συνιστώμενες ρυθμίσεις production

```env
ENVIRONMENT=production
DEBUG=false
DRY_RUN=true          # μέχρι go-live write
REQUIRE_AUTH=true
COOKIE_SECURE=true
SECRET_KEY=<32+ chars random>
POSTGRES_PASSWORD=<strong>
```

---

## 6. External reviews (προαιρετικά πριν GA)

- [ ] Dependency scan (`pip audit` / Trivy images)
- [ ] Pen-test ελαφρύ (auth, IDOR σε conversation ids)
- [ ] Νομικός έλεγχος Privacy / ToS / DPA

---

*Έγγραφο: `docs/SECURITY.md` — συνοδευτικό pilot & πωλήσεων.*
