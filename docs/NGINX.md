# Nginx reverse proxy – Rafaela

Configs live in `docker/nginx/`:

| File | Use case |
|------|----------|
| `rafaela.conf` | Δύο hostnames: `app.*` (UI) + `api.*` (backend) |
| `rafaela-single-domain.conf` | Ένα domain: `/` → UI, `/api/` → backend |

## 1. Προετοιμασία

```bash
# Στο host (Ubuntu/Debian παράδειγμα)
sudo apt update && sudo apt install -y nginx certbot python3-certbot-nginx

# Αντιγραφή config
sudo cp docker/nginx/rafaela.conf /etc/nginx/sites-available/rafaela
# ή single-domain:
# sudo cp docker/nginx/rafaela-single-domain.conf /etc/nginx/sites-available/rafaela

# Επεξεργασία: άλλαξε app.example.com / api.example.com
sudo nano /etc/nginx/sites-available/rafaela

sudo ln -sf /etc/nginx/sites-available/rafaela /etc/nginx/sites-enabled/
sudo nginx -t
```

## 2. DNS

Δημιούργησε A/AAAA records:

- `app.example.com` → IP server  
- `api.example.com` → IP server  

(ή μόνο `secretary.example.com` για single-domain)

## 3. TLS (Let's Encrypt)

Πρώτα ενεργοποίησε μόνο το HTTP block (ή προσωρινά σχόλιασε τα `ssl_certificate` lines), μετά:

```bash
sudo certbot --nginx -d app.example.com -d api.example.com
# ή
sudo certbot --nginx -d secretary.example.com
```

Ο Certbot ενημερώνει συχνά τα paths των certificates αυτόματα.

Χειροκίνητα:

```bash
sudo certbot certonly --webroot -w /var/www/certbot \
  -d app.example.com -d api.example.com
sudo systemctl reload nginx
```

## 4. .env.prod (σημαντικό)

Με **δύο domains**:

```env
NEXT_PUBLIC_API_URL=https://api.example.com
MS_REDIRECT_URI=https://api.example.com/api/v1/auth/microsoft/callback
GOOGLE_REDIRECT_URI=https://api.example.com/api/v1/auth/google/callback
```

Με **ένα domain**:

```env
NEXT_PUBLIC_API_URL=https://secretary.example.com
MS_REDIRECT_URI=https://secretary.example.com/api/v1/auth/microsoft/callback
GOOGLE_REDIRECT_URI=https://secretary.example.com/api/v1/auth/google/callback
```

Στο Azure / Google Cloud βάλε **ακριβώς** τα ίδια redirect URIs.

Rebuild frontend μετά αλλαγή `NEXT_PUBLIC_API_URL` (μπαίνει στο build):

```bash
docker compose -f docker-compose.prod.yml --env-file .env.prod up -d --build frontend
```

## 5. CORS στο FastAPI

Το backend επιτρέπει origins από config. Για production πρόσθεσε στο `.env` / settings:

```text
https://app.example.com
```

(Αν χρησιμοποιείς single-domain, το browser καλεί same-origin `/api/` και το CORS είναι λιγότερο κρίσιμο.)

## 6. Έλεγχος

```bash
sudo nginx -t && sudo systemctl reload nginx

curl -I https://app.example.com
curl https://api.example.com/health
# single-domain:
curl https://secretary.example.com/health
```

## 7. Τι κάνει το config

- HTTP → HTTPS redirect  
- TLS 1.2/1.3 + HSTS  
- Security headers (X-Frame, nosniff, Referrer-Policy)  
- Rate limiting (API πιο αυστηρό)  
- Μεγαλύτερο `proxy_read_timeout` για chat/agent  
- `X-Forwarded-Proto` για σωστά redirects OAuth  
- Frontend WebSocket upgrade headers (Next.js)  

## 8. Προαιρετικά

**Μόνο localhost ports στο Docker (ήδη στο prod compose):**

```yaml
ports:
  - "127.0.0.1:3000:3000"
  - "127.0.0.1:8000:8000"
```

**Fail2ban / firewall:** άνοιξε μόνο 80/443 στο internet· 22 για SSH με περιορισμό.

**Logs:**

```bash
sudo tail -f /var/log/nginx/access.log /var/log/nginx/error.log
```
EOF
