# PRE-DEPLOYMENT CHECKLIST

**Package:** `vps-deploy-3818e3d.tar.gz`  
**Commit:** `3818e3d`  
**Branch:** `hotfix/audit-remediation-local`  
**Date:** 2026-03-11  
**Target:** VPS `5.189.131.48` (`azim@`)  
**Deploy Dir:** `/home/azim/ai-call-platform`  
**Rollback:** `f905615` via `bash scripts/rollback-vps.sh`  

---

## 1. VPS Pre-Flight (SSH into VPS first)

```bash
ssh azim@5.189.131.48
```

- [ ] **Disk space:** `df -h /` — need 500MB+ free
- [ ] **Docker running:** `docker info >/dev/null 2>&1 && echo OK`
- [ ] **Record current commit:** `cd ~/ai-call-platform && git rev-parse --short HEAD`

## 2. Backup on VPS

```bash
cd ~/ai-call-platform && bash scripts/backup.sh
```

- [ ] PostgreSQL dump created
- [ ] Qdrant snapshot created (if collections exist)

## 3. Verify VPS .env Has Required Variables

The VPS `.env` must contain these variables. New ones added in this release are marked **NEW**:

| Variable | Status | Notes |
|----------|--------|-------|
| `FAZLE_API_KEY` | Must not be empty | Compose will abort if unset |
| `FAZLE_JWT_SECRET` | **NEW** — min 32 chars | JWT signing for Fazle auth |
| `NEXTAUTH_SECRET` | **NEW** — min 32 chars | NextAuth.js session secret |
| `GRAFANA_PASSWORD` | **NEW** | Grafana admin password |
| `DATABASE_URL` | Required | PostgreSQL URI for task engine |
| `POSTGRES_PASSWORD` | Required | Must not be placeholder |
| `REDIS_PASSWORD` | Required | Must not be placeholder |
| `OPENAI_API_KEY` | Required if LLM=openai | Real OpenAI key |

If any **NEW** variables are missing, add them to VPS `.env`:
```bash
# Generate and append missing secrets on VPS:
echo "FAZLE_JWT_SECRET=$(openssl rand -base64 48 | tr -dc 'a-zA-Z0-9' | head -c 48)" >> .env
echo "NEXTAUTH_SECRET=$(openssl rand -base64 48 | tr -dc 'a-zA-Z0-9' | head -c 48)" >> .env
echo "GRAFANA_PASSWORD=$(openssl rand -base64 24 | tr -dc 'a-zA-Z0-9' | head -c 24)" >> .env
```

## 4. Deploy from Local Machine

```bash
# From E:\Programs\vps-deploy (Git Bash or WSL):
bash scripts/deploy-to-vps.sh
```

This will:
1. Verify SSH connectivity
2. Record rollback target on VPS
3. Run `backup.sh` on VPS
4. Upload `vps-deploy-3818e3d.tar.gz`
5. Extract (preserves `.env`)
6. Validate docker-compose config
7. Rebuild and restart all services

## 5. Post-Deploy Verification

```bash
# SSH into VPS:
bash scripts/health-check.sh
bash scripts/db-migrate.sh        # Run migrations if not already applied
docker compose ps                  # All services should be Up/healthy
```

Endpoints to verify:
- `https://iamazim.com` — Dashboard
- `https://fazle.iamazim.com` — Fazle UI
- `https://fazle.iamazim.com/api/fazle/health` — Fazle API health
- `https://api.iamazim.com/api/v1/health` — Dograh API health

## 6. Rollback (If Needed)

```bash
# From local machine:
bash scripts/rollback-vps.sh
# Reverts to commit f905615, preserves .env, rebuilds containers
```

---

## Security Findings Remediated in This Release

| ID | Severity | Summary |
|----|----------|---------|
| P0-SEC-1 | CRITICAL | gen-secrets.sh generates all 11 secrets |
| P0-SEC-2 | CRITICAL | safety.py fail-closed for child accounts |
| P1-SEC-3 | HIGH | FastAPI docs disabled in production |
| P1-SEC-4 | HIGH | Nginx blocks /docs and /openapi.json |
| P1-SEC-6 | HIGH | Timing-safe API key comparison |
| P1-SEC-7 | HIGH | .next/ build cache removed |
| P1-SEC-8 | HIGH | FAZLE_API_KEY required (compose fails if unset) |
| P1-SEC-9 | HIGH | SSRF protection on /scrape |
| P1-NET-1 | MEDIUM | WebSocket proxy headers added |
| P1-DEP-1 | MEDIUM | Missing Python deps added |
| P1-DEP-2 | MEDIUM | python-jose → PyJWT (no known CVEs) |
| P1-OPS-1 | MEDIUM | Docker images pinned |
| P1-OPS-2 | MEDIUM | Loki healthcheck fixed |
| P1-OPS-3 | MEDIUM | DB connection pooling |
| P1-OPS-4 | MEDIUM | Prometheus metrics on all services |

## Post-Deploy Actions

- [ ] Run `bash scripts/db-migrate.sh`
- [ ] Run `bash scripts/setup-ollama.sh` (if models not already pulled)
- [ ] Run `bash scripts/health-check.sh`
- [ ] Verify all 23 containers healthy
- [ ] Test endpoints:
  - `curl -s https://api.iamazim.com/api/v1/health`
  - `curl -s http://localhost:8100/health` (Fazle API)
  - `curl -s http://localhost:3020` (Fazle UI)

## Sign-Off

- [ ] All local validation gates passed (Phases 0–6)
- [ ] Deployment package created and verified
- [ ] Rollback plan tested (script syntax validated)
- [ ] Ready to deploy: **YES / NO**
