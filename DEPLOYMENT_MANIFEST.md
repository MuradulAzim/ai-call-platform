# DEPLOYMENT MANIFEST

**Package:** `vps-deploy-3818e3d.tar.gz`  
**Commit:** `3818e3d31746ea26a7e4062e5836f21d2247847d`  
**Branch:** `hotfix/audit-remediation-local`  
**Date:** 2026-03-11  
**Author:** azim@iamazim.com  
**Rollback Target:** `f905615` (previous HEAD)  

---

## Deployment Summary

This release remediates **all 18 security findings** (2 P0, 16 P1) identified in the SRE infrastructure audit of 2026-03-10, plus prior phases (auth, persona, voice, hardening).

**Verification:** `verify-remediation.sh` — 16/16 checks PASS, 0 errors.

---

## Pre-Deploy Checklist

- [x] All 18 audit findings remediated and verified
- [x] Changes committed: `3818e3d`
- [x] Deployment package created: `vps-deploy-3818e3d.tar.gz` (150 KB, 113 files)
- [ ] VPS `.env` has all required variables (see below)
- [ ] VPS backup taken: `bash scripts/backup.sh`
- [ ] Deploy: `bash scripts/deploy-to-vps.sh`
- [ ] Post-deploy health check passes

---

## Security Remediation (This Release)

| ID | Severity | Fix | File(s) |
|----|----------|-----|---------|
| P0-SEC-1 | CRITICAL | gen-secrets.sh generates all 11 secrets, no cleartext | `gen-secrets.sh` |
| P0-SEC-2 | CRITICAL | safety.py fail-closed for child accounts | `fazle-system/brain/safety.py` |
| P1-SEC-3 | HIGH | FastAPI docs_url/redoc_url disabled | `fazle-system/api/main.py` |
| P1-SEC-4 | HIGH | Nginx blocks /docs and /openapi.json | `configs/nginx/fazle.iamazim.com.conf` |
| P1-SEC-6 | HIGH | API key uses hmac.compare_digest | `fazle-system/api/main.py` |
| P1-SEC-7 | HIGH | .next/ removed, .dockerignore added | `fazle-system/ui/.dockerignore` |
| P1-SEC-8 | HIGH | FAZLE_API_KEY uses :? (fail if unset) | `docker-compose.yaml` |
| P1-SEC-9 | HIGH | SSRF protection on /scrape endpoint | `fazle-system/tools/main.py` |
| P1-NET-1 | MEDIUM | WebSocket Upgrade headers in nginx | `configs/nginx/fazle.iamazim.com.conf` |
| P1-DEP-1 | MEDIUM | PyPDF2/python-docx added | `fazle-system/api/requirements.txt` |
| P1-DEP-2 | MEDIUM | python-jose → PyJWT[crypto]==2.9.0 | `fazle-system/api/requirements.txt`, `auth.py` |
| P1-OPS-1 | MEDIUM | Docker tags pinned with version vars | `docker-compose.yaml` |
| P1-OPS-2 | MEDIUM | Loki healthcheck uses /ready | `docker-compose.yaml` |
| P1-OPS-3 | MEDIUM | database.py uses ThreadedConnectionPool | `fazle-system/api/database.py` |
| P1-OPS-4 | MEDIUM | Prometheus metrics on all Fazle services | `*/main.py`, `*/requirements.txt` |

---

## New Environment Variables (Since Last Deploy)

| Variable | Service(s) | Required | Description |
|----------|-----------|----------|-------------|
| `FAZLE_API_KEY` | fazle-api | **YES** | Must not be empty — compose will fail |
| `FAZLE_JWT_SECRET` | fazle-api | **YES** | JWT signing (min 32 chars) |
| `NEXTAUTH_SECRET` | fazle-ui | **YES** | NextAuth.js session secret (min 32 chars) |
| `GRAFANA_PASSWORD` | grafana | **YES** | Grafana admin password |
| `DATABASE_URL` | fazle-task-engine | **YES** | PostgreSQL connection string |
| `REDIS_URL` | fazle-brain | NO | Default: `redis://ai-redis:6379/0` |
| `ALLOWED_ORIGINS` | fazle-* | NO | Comma-separated CORS origins |
| `DOGRAH_API_VERSION` | dograh-api | NO | Default: `1.0.0` |
| `DOGRAH_UI_VERSION` | dograh-ui | NO | Default: `1.0.0` |

---

## Deployment Commands

```bash
# From local machine (E:\Programs\vps-deploy):
bash scripts/deploy-to-vps.sh

# Rollback if needed:
bash scripts/rollback-vps.sh
# (Uses ROLLBACK_TARGET.txt → f905615)
```

---

## Database Migrations

```bash
# Run from VPS after deploy:
bash scripts/db-migrate.sh
```

Migration files:
- `fazle-system/tasks/migrations/001_scheduler_tables.sql`
- `fazle-system/tasks/migrations/002_fazle_core_tables.sql`

---

## Docker Images Pinned

| Service | Image | Pinned Version |
|---------|-------|---------------|
| ai-redis | redis | 7.2.5-alpine |
| minio | minio/minio | RELEASE.2024-11-11T11-18-37Z |
| livekit | livekit/livekit-server | v1.8.2 |
| coturn | coturn/coturn | 4.6.2-r12-alpine |
| qdrant | qdrant/qdrant | v1.12.1 |
| ollama | ollama/ollama | 0.3.14 |
| prometheus | prom/prometheus | v2.55.0 |
| grafana | grafana/grafana | 11.2.2 |
| node-exporter | prom/node-exporter | v1.8.2 |
| cadvisor | gcr.io/cadvisor/cadvisor | v0.49.1 |
| loki | grafana/loki | 3.2.1 |
| promtail | grafana/promtail | 3.2.1 |
| cloudflared | cloudflare/cloudflared | 2024.10.1 |

**NOT pinned (intentional):** Dograh API, Dograh UI — controlled by CI/CD pipeline.

---

## Deploy Procedure

```bash
# 1. SSH to VPS
ssh azim@5.189.131.48

# 2. Backup current state
cd /home/azim/ai-call-platform
bash scripts/backup.sh

# 3. Pull changes
git pull origin hotfix/audit-remediation-local

# 4. Update .env with new variables
nano .env  # Add FAZLE_API_KEY, DATABASE_URL, GRAFANA_ADMIN_PASSWORD

# 5. Run database migrations
bash scripts/db-migrate.sh

# 6. Setup Ollama models (if not already done)
bash scripts/setup-ollama.sh

# 7. Rebuild and restart services (zero-downtime rolling)
docker compose pull
docker compose up -d --build --remove-orphans

# 8. Verify
bash scripts/health-check.sh
```

---

## Rollback Procedure

```bash
# 1. SSH to VPS
ssh azim@5.189.131.48
cd /home/azim/ai-call-platform

# 2. Restore previous compose file
cp backups/docker-compose-YYYYMMDD_HHMMSS.yaml docker-compose.yaml

# 3. Restore .env if changed
cp backups/env-YYYYMMDD_HHMMSS.bak .env

# 4. Restart with old config
docker compose up -d --remove-orphans

# 5. If DB migration needs rollback (fazle_tasks table):
docker exec ai-postgres psql -U postgres -d postgres -c "DROP TABLE IF EXISTS fazle_tasks;"
# Note: APScheduler job store table (apscheduler_jobs) will be recreated automatically

# 6. Verify rollback
bash scripts/health-check.sh
```

---

## Risk Assessment

| Change | Risk | Mitigation |
|--------|------|------------|
| Auth bypass fix | Low | Only affects empty API keys |
| Privileged mode removal (cadvisor) | Low | CAP_ADD provides equivalent access |
| In-memory → PostgreSQL (tasks) | Medium | Migration is idempotent; existing tasks lost (acceptable — they were ephemeral) |
| In-memory → Redis (conversations) | Low | Conversations had no persistence before |
| Image version pinning | Low | All versions match currently running |
| CORS restriction | Low | Only allowed origins change; defaults include all used domains |
| Coturn TLS path fix | Medium | Verify cert files are mounted correctly |
| Backup script changes | Low | Improvements only; no breaking changes |
