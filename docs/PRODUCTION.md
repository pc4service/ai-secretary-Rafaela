# Production Docker

## Files

| File | Role |
|------|------|
| `docker-compose.prod.yml` | Hardened compose (no DB/Redis ports, non-root images, limits) |
| `docker/Dockerfile.backend.prod` | Non-root, multi-worker uvicorn, no reload |
| `docker/Dockerfile.frontend.prod` | Multi-stage Next.js standalone |
| `.env.prod.example` | Template for production secrets |

## Quick start

```bash
cp .env.prod.example .env.prod
# Edit .env.prod – set SECRET_KEY, POSTGRES_PASSWORD, OPENAI_API_KEY, OAuth, NEXT_PUBLIC_API_URL

docker compose -f docker-compose.prod.yml --env-file .env.prod up -d --build
```

## Security features

- DB and Redis **not** published to the host
- `secretary-internal` network is **internal** (DB/Redis isolated)
- Backend + frontend bound to `127.0.0.1` only (use reverse proxy for public access)
- Non-root users in images
- `no-new-privileges`, `cap_drop: ALL`, `read_only` + tmpfs
- Memory/CPU limits
- Healthchecks + `depends_on` conditions
- No source bind-mounts (immutable containers)

## Reverse proxy

Point HTTPS to:

- `127.0.0.1:3000` → frontend  
- `127.0.0.1:8000` → API  

Update OAuth redirect URIs and `NEXT_PUBLIC_API_URL` to your public HTTPS hostnames.

## Stop / wipe

```bash
docker compose -f docker-compose.prod.yml --env-file .env.prod down
# Data volumes:
docker compose -f docker-compose.prod.yml --env-file .env.prod down -v
```
