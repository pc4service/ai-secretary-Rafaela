# Rafaela — Pilot Deploy Runbook

Οδηγίες για **πρώτο pilot** (1 εταιρεία, 1–5 users) σε Proxmox ή VPS.

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
nano .env.prod
```

Συμπλήρωσε:

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
QDRANT_URL=http://qdrant:6333
```

### 3. Start

```bash
docker compose -f docker-compose.prod.yml --env-file .env.prod up -d --build
curl -sf http://127.0.0.1:8000/health
```

> Αν το `docker-compose.prod.yml` δεν περιλαμβάνει ακόμα `qdrant`, πρόσθεσέ το όπως στο dev compose ή χρησιμοποίησε keyword fallback (δουλεύει χωρίς Qdrant).

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
| 4 | Knowledge: «πρότυπο follow-up» |
| 5 | HITL propose email → Έγκριση → dry-run μήνυμα |
| 6 | Settings: σύνδεση Google/MS (αν OAuth έτοιμο) |
| 7 | Backup Postgres (cron / snapshot) |
| 8 | `DRY_RUN=false` **μόνο** μετά από γραπτή έγκριση pilot |

---

## Backups (ελάχιστο)

```bash
# Παράδειγμα dump
docker compose -f docker-compose.prod.yml exec -T db \
  pg_dump -U secretary secretary > backup_$(date +%F).sql
```

Κράτα 7–14 ημερήσια αντίγραφα εκτός VM.

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
