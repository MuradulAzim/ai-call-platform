# LOCAL REMEDIATION REPORT

**Project:** Dograh Voice SaaS + Fazle Personal AI  
**VPS:** Contabo 5.189.131.48 (Ubuntu 22.04.5)  
**Branch:** `hotfix/audit-remediation-local`  
**Deployment Date:** 2026-03-09  
**Deployment Duration:** ~2 hours  

---

## Phase B-D Remediation (Latest Round)

### Phase B — Fix the Brain (Network Isolation)

| # | Issue | Fix | File |
|---|-------|-----|------|
| 5 | AI services isolated from internet — no OpenAI connectivity | Added `app-network` to fazle-brain, fazle-memory, fazle-web-intelligence, fazle-trainer | `docker-compose.yaml` |

### Phase C — Data Integrity & Persistence

| # | Issue | Fix | File |
|---|-------|-----|------|
| 6 | PostgreSQL RLS defined but never activated | Switched `save_message`, `get_user_conversations`, `get_conversation_messages` from `_get_conn()` to `_rls_conn(user_id)` | `fazle-system/api/database.py` |
| 7 | Trainer sessions lost on restart (in-memory dict) | Replaced `training_sessions: dict` with Redis-backed storage (`redis[hiredis]`), 30-day TTL, db/2 | `fazle-system/trainer/main.py`, `trainer/requirements.txt`, `docker-compose.yaml` |
| 8 | Missing healthchecks on fazle-voice and node-exporter | Added healthcheck blocks (python urllib on :8700, wget on :9100) | `docker-compose.yaml` |

### Phase D — Observability & Polish

| # | Issue | Fix | File |
|---|-------|-----|------|
| 9 | No application metrics — Prometheus only scrapes infra | Added `prometheus-fastapi-instrumentator` to API, exposed `/metrics`, added `fazle-api` scrape target | `api/requirements.txt`, `api/main.py`, `configs/prometheus/prometheus.yml` |
| 10 | PWA manifest references non-existent icon files | Cleared icons array to prevent browser 404 warnings | `fazle-system/ui/public/manifest.json` |
| 11 | .env.example has duplicates and missing vars | Removed duplicate GRAFANA_USER/PASSWORD, added FAZLE_NEXTAUTH_URL and FAZLE_LIVEKIT_URL | `.env.example` |

### Network Changes Summary

| Service | Before | After |
|---------|--------|-------|
| fazle-brain | ai-network, db-network | ai-network, db-network, **app-network** |
| fazle-memory | ai-network, db-network | ai-network, db-network, **app-network** |
| fazle-web-intelligence | ai-network | ai-network, **app-network** |
| fazle-trainer | ai-network | ai-network, **app-network**, **db-network** |
| fazle-voice | app-network, ai-network | app-network, ai-network (+ healthcheck) |
| node-exporter | monitoring-network | monitoring-network (+ healthcheck) |

---

## Commit History

| Commit | Phase | Description |
|--------|-------|-------------|
| `4086cee` | 0 | Setup local validation environment, .gitignore, remove secrets |
| `05b917c` | 1 | Security: remove privileged mode, fix auth bypass, harden CORS |
| `8c1e85c` | 2 | Persistence: PostgreSQL for tasks, Redis for conversations |
| `0b76740` | 3 | Stability: pin 13 Docker images, fix Coturn TLS, restrict CORS |
| `efa5047` | 4 | Ops: correct backup script, remove stale configs, deployment manifest |
| `89b0398` | 5 | App: Next.js 14.2.35, Pydantic input validation, healthchecks |
| `a8df4a9` | 6 | Release: pre-deploy checklist, gitignore for deployment-package |
| `b099162` | 7 | Deploy/rollback scripts for VPS |
| `5f127ee` | 8 | Deploy fixes: version compat, auth bug, Grafana proxy, Ollama DNS |

---

## Files Modified (Phase 8 — Deployment Fixes)

| File | Change |
|------|--------|
| `docker-compose.yaml` | Redis 7.2.5→8.0.2, MinIO pin RELEASE.2025-09-07, Qdrant v1.12.1→v1.17.0, cloudflared healthcheck NONE, Ollama DNS 8.8.8.8/1.1.1.1 |
| `fazle-system/api/main.py` | Fix `env_prefix` double-prefix bug (`FAZLE_FAZLE_API_KEY` → `FAZLE_API_KEY`) |
| `configs/nginx/iamazim.com.conf` | Fix Grafana `proxy_pass` to preserve `/grafana/` subpath (was stripping it) |

---

## Issues Discovered & Resolved During Deployment

### 1. Image Version Incompatibilities
VPS was running `:latest` tags before pinning. Existing data formats were incompatible with the pinned older versions:

- **Redis**: RDB format 12 (from Redis 8.x) unreadable by 7.2.5 → Fixed: `redis:8.0.2-alpine`
- **MinIO**: xl meta version 3 data from latest → Fixed: `minio/minio:RELEASE.2025-09-07T16-13-09Z`
- **Qdrant**: v1.17.0 data unreadable by v1.12.1 → Fixed: `qdrant/qdrant:v1.17.0`

### 2. Cloudflared Healthcheck
Minimal container image has no `wget`, `curl`, `ls`, or `which` — healthcheck commands fail. Fixed: `test: ["NONE"]`

### 3. CRLF Line Endings
Windows-originated `.sh` files had `\r\n` line endings causing bash failures (coturn crash: `set -e` → "illegal option -"). Fixed: `sed -i 's/\r$//'` on all `.sh` files on VPS.

### 4. Fazle API Key Bug
`pydantic_settings` with `env_prefix = "FAZLE_"` and field `fazle_api_key` looked for `FAZLE_FAZLE_API_KEY`. Fixed: renamed field to `api_key` so it maps to `FAZLE_API_KEY`.

### 5. SSL Certificate Not Served
Nginx hadn't reloaded since cert renewal — was serving an old cert missing `fazle.iamazim.com` SAN. Fixed: `systemctl reload nginx`.

### 6. Grafana Redirect Loop
`GF_SERVER_SERVE_FROM_SUB_PATH=true` requires nginx to preserve the `/grafana/` path prefix. `proxy_pass http://127.0.0.1:3030/` was stripping it. Fixed: `proxy_pass http://127.0.0.1:3030` (no trailing slash).

### 7. Ollama DNS Resolution
Docker embedded DNS (127.0.0.11) fails to resolve external hosts via the host's systemd-resolved (127.0.0.53). Fixed: explicit `dns: [8.8.8.8, 1.1.1.1]` in docker-compose.

---

## Manual Steps Performed on VPS

1. **Pre-deploy backup** (`20260308_235748`): PostgreSQL dump, Redis RDB, configs, env
2. **VPS git init** with pre-remediation commit `3872a1a` as rollback target
3. **Deployment package upload** via SCP (`vps-deploy-b099162.tar.gz`, 97KB)
4. **CRLF fix**: `find . -name '*.sh' -exec sed -i 's/\r$//' {} +`
5. **Env vars appended**: `GRAFANA_USER`, `GRAFANA_PASSWORD`, `FAZLE_API_KEY`, `FAZLE_LLM_PROVIDER`, `FAZLE_LLM_MODEL`, `FAZLE_OLLAMA_MODEL`, `OPENAI_API_KEY`
6. **Database migration**: `001_scheduler_tables.sql` (CREATE TABLE + 3 indexes)
7. **Full rebuild**: `docker compose build --no-cache` (7 Fazle services)
8. **Nginx reload**: `sudo systemctl reload nginx` (SSL cert + Grafana proxy fix)
9. **Ollama model pull**: `llama3.1` (4.9 GB) via host-network temp container
10. **Post-deploy backup** (`20260309_011025`): verified backup script works

---

## Validation Results

| Check | Status | Details |
|-------|--------|---------|
| All 23 containers running | ✅ PASS | 21 healthy, 2 no-healthcheck (cloudflared, node-exporter) |
| `https://iamazim.com/health` | ✅ PASS | `{"status":"ok","version":"1.16.0"}` |
| `https://fazle.iamazim.com/health` | ✅ PASS | `{"status":"healthy","service":"fazle-api"}` |
| Fazle UI (port 3020) | ✅ PASS | HTTP 200 |
| Fazle API auth — no key | ✅ PASS | HTTP 401 "Invalid API key" |
| Fazle API auth — wrong key | ✅ PASS | HTTP 401 "Invalid API key" |
| Fazle API auth — valid key | ✅ PASS | HTTP 502 (Brain→OpenAI, expected with placeholder key) |
| Grafana (`/grafana/login`) | ✅ PASS | HTTP 200 |
| Ollama model loaded | ✅ PASS | `llama3.1:latest` (4.9 GB) |
| Backup script | ✅ PASS | PostgreSQL, Redis, configs backed up |
| Docker compose config valid | ✅ PASS | `docker compose config` passes |

---

## VPS Git State

- **Rollback target (pre-remediation):** Backup `20260308_235748` + git commit `3872a1a`
- **Current deployed commit:** `53f48f4` ("deploy: audit remediation applied")
- **Rollback procedure:** Restore from backup, `docker compose up -d`

---

## Known Limitations

1. **OPENAI_API_KEY** is placeholder (`sk-replace-with-real-openai-key`) — Fazle Brain/chat endpoints return 502 until real key is set
2. **Qdrant snapshots** skipped in backup (service returns empty/no data)
3. **Cloudflared** has no healthcheck (container too minimal for any check command)
4. **Ollama DNS** requires explicit DNS config; Docker embedded DNS unreliable with systemd-resolved
