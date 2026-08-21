# Rafaela — Pilot Deploy Runbook

Οδηγίες για **πρώτο pilot** (1 εταιρεία, 1–5 users) σε Proxmox ή VPS.

---

## Local production mode (Docker στο PC σου)

Για να τρέξεις `ENVIRONMENT=production` **χωρίς VPS**, με HTTP στο loopback:

```bash
./scripts/local_prod.sh init   # φτιάχνει .env.prod (secrets + copy keys από .env)
./scripts/local_prod.sh up     # σταματά dev compose · σηκώνει prod + local overlay
```

| URL | |
|-----|--|
| UI | **http://localhost:3000** (όχι `127.0.0.1` — σπάει το cookie μετά το MS login) |
| API | http://localhost:8000 |

Azure App Registration → Redirect URI (Web):
`http://localhost:8000/api/v1/login/microsoft/callback`

| Flag | Local prod τιμή | Γιατί |
|------|-----------------|--------|
| `ENVIRONMENT` | `production` | κλείνει demo login, docs, αυστηρό auth |
| `REQUIRE_AUTH` | `true` | |
| `COOKIE_SECURE` | **`false`** | είσαι σε `http://` · true μόνο με HTTPS |
| `DRY_RUN` | `true` | ασφαλές pilot · flip όταν θες αληθινά writes |
| `TRUSTED_PROXY_HOPS` | `0` | χωρίς nginx |

- Login: **Microsoft** (το Demo είναι 403).
- ChatGPT OAuth callback: `localhost:1455` (το `docker-compose.prod.local.yml` το ανοίγει).
- Πίσω στο dev trial: `./scripts/local_prod.sh dev`
- Αρχεία: `.env.prod.local.example`, `docker-compose.prod.local.yml`, `scripts/local_prod.sh`

> Αυτό **δεν** είναι public internet. Για HTTPS + domain δες Cloudflare Tunnel / VPS παρακάτω.
> Μην κάνεις tunnel/port-forward αυτό το stack στο internet χωρίς να αλλάξεις πρώτα
> `FRONTEND_URL` σε non-loopback: το CORS επιτρέπει loopback origins όσο το
> `FRONTEND_URL` είναι loopback, ό,τι θα άνοιγε credentialed cross-origin αιτήματα
> από `localhost` σελίδα οποιουδήποτε επισκέπτη.

---

## Προαπαιτούμενα

- [ ] Domain (π.χ. `rafaela.example.com`, `api.rafaela.example.com`)
- [ ] `OPENAI_API_KEY`
- [ ] Ισχυρά: `SECRET_KEY`, `POSTGRES_PASSWORD`
- [ ] (Προαιρετικά) Google / Microsoft OAuth apps με **production redirect URIs**
- [ ] Docker + Docker Compose στο host

---

## Επιλογή Α — Proxmox + Cloudflare Tunnel

### 1. VM

- Ubuntu 24.04, 2–4 vCPU, 4–8 GB RAM, 40 GB disk  
- Εγκατάσταση Docker: `curl -fsSL https://get.docker.com | sh`

### 2. Κώδικας

```bash
cd /opt
git clone <REPO_URL> rafaela && cd rafaela
# ή scp/unzip του project
cp .env.prod.example .env.prod
nano .env.prod   # ή: ./scripts/pilot_deploy.sh check
```

Συμπλήρωσε (πλήρες template: `.env.prod.example`):

```env
ENVIRONMENT=production
DRY_RUN=true
REQUIRE_AUTH=true
SECRET_KEY=<long-random>
POSTGRES_PASSWORD=<strong>
OPENAI_API_KEY=sk-...
FRONTEND_URL=https://rafaela.example.com
NEXT_PUBLIC_API_URL=https://api.rafaela.example.com
MS_REDIRECT_URI=https://api.rafaela.example.com/api/v1/auth/microsoft/callback
GOOGLE_REDIRECT_URI=https://api.rafaela.example.com/api/v1/auth/google/callback
GOOGLE_LOGIN_REDIRECT_URI=https://api.rafaela.example.com/api/v1/login/google/callback
MS_LOGIN_REDIRECT_URI=https://api.rafaela.example.com/api/v1/login/microsoft/callback
COOKIE_SECURE=true
TRUSTED_PROXY_HOPS=1
QDRANT_URL=http://qdrant:6333
```

### 3. Start

```bash
./scripts/pilot_deploy.sh check
./scripts/pilot_deploy.sh up
./scripts/pilot_deploy.sh smoke
# ή χειροκίνητα:
# docker compose -f docker-compose.prod.yml --env-file .env.prod up -d --build
curl -sf http://127.0.0.1:8000/health
curl -sf http://127.0.0.1:8000/api/v1/knowledge/status
```

> **Knowledge:** keyword πάντα· semantic/hybrid όταν τρέχει το service `qdrant` (υπάρχει στο prod compose). Χωρίς embeddings key πέφτει σε hash embedder / keyword.

### 4. Cloudflare Tunnel

1. Zero Trust → Tunnels → Create  
2. Install `cloudflared` με token στη VM  
3. Public hostnames:

| Hostname | Service |
|----------|---------|
| `rafaela.example.com` | `http://127.0.0.1:3000` |
| `api.rafaela.example.com` | `http://127.0.0.1:8000` |

4. OAuth redirect URIs = ακριβώς τα HTTPS API paths  
5. Rebuild frontend αν άλλαξε `NEXT_PUBLIC_API_URL`

### 5. Smoke

```bash
curl -sf https://api.rafaela.example.com/health
# Browser: Demo login → chat → knowledge question
```

---

## Επιλογή Β — Hostinger (ή άλλο) VPS

### 1. VPS

- Ubuntu, root/ssh, ανοιχτά 80/443 (και 22 περιορισμένα)

### 2. Ίδιο clone + `.env.prod` με public URLs

### 3. Compose

```bash
docker compose -f docker-compose.prod.yml --env-file .env.prod up -d --build
```

### 4. Nginx + Let’s Encrypt

Δες `docs/NGINX.md` (`rafaela.conf` ή single-domain).

```bash
sudo certbot --nginx -d rafaela.example.com -d api.rafaela.example.com
```

### 5. Firewall

```bash
sudo ufw allow OpenSSH
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
# ΜΗΝ εκθέσεις 5432/6379 δημόσια
```

---

## Μετά το deploy — checklist pilot

| # | Έλεγχος |
|---|---------|
| 1 | `/health` → ok, `dry_run: true` |
| 2 | Login Demo ή OAuth |
| 3 | Chat απαντά |
| 4 | Knowledge: `GET /api/v1/knowledge/search?q=follow-up` ή chat «πρότυπο follow-up» |
| 5 | HITL propose **calendar event** → Έγκριση → dry-run (το send-email δεν είναι ενεργό) |
| 6 | Settings: σύνδεση Google/MS (αν OAuth έτοιμο) |
| 7 | Backup Postgres (cron / snapshot) |
| 8 | `DRY_RUN=false` **μόνο** μετά από γραπτή έγκριση pilot |

---

## Backups (ελάχιστο)

```bash
./scripts/pilot_deploy.sh backup   # → backups/secretary_YYYYMMDD_HHMMSS.sql (κρατά 14)
# ή:
# docker compose -f docker-compose.prod.yml --env-file .env.prod exec -T db \
#   pg_dump -U secretary secretary > backup_$(date +%F).sql
```

Κράτα 7–14 ημερήσια αντίγραφα **και** αντίγραφο εκτός VM (cron + offsite).

---

## Rollback

```bash
git log --oneline -5
git checkout <previous-sha>
docker compose -f docker-compose.prod.yml --env-file .env.prod up -d --build
```

---

## Support contacts (συμπλήρωσε)

| Ρόλος | Επαφή |
|-------|--------|
| Technical | |
| On-call pilot | |
| DPO / GDPR | |
