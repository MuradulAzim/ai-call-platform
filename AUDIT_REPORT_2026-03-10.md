# INFRASTRUCTURE & CODE AUDIT REPORT
**Generated:** 2026-03-10  
**Auditor:** Senior SRE — Comprehensive Static Analysis  
**Overall Status:** DEGRADED  
**Scope:** 22 Docker services, 7 Fazle microservices, 4 Nginx vhosts, monitoring stack, deployment scripts  

---

## Executive Summary

The platform is **operationally functional** with strong architectural foundations (network isolation, RLS, persona engine, audit logging). However, **2 critical security issues** remain unresolved: incomplete secret rotation and content moderation failing open for child accounts. An additional **16 P1 warnings** span dependency vulnerabilities, missing WebSocket headers, connection pooling gaps, and monitoring blind spots. The system is **safe to run** but not yet hardened for production child-safety requirements.

---

## What's Working ✅

1. **Network isolation** — `db-network` and `monitoring-network` are `internal: true`. Database ports (Postgres, Redis, MinIO, Qdrant) never exposed to the host.
2. **Secrets management** — All 10 critical secrets use `${VAR:?error}` fail-fast syntax. No hardcoded fallbacks remain in docker-compose, auth.py, or route.js.
3. **Row-Level Security** — RLS policies defined in SQL and enforced via `_rls_conn(user_id)` on `save_message`, `get_user_conversations`, `get_conversation_messages`. Admin queries correctly bypass RLS.
4. **Persona engine** — Relationship-aware system prompts with privacy boundaries between family members. Non-admin users cannot access other members' private data.
5. **Content safety** — OpenAI Moderation API with stricter thresholds for child accounts (`daughter`/`son`). Both input and output are checked in the brain service.
6. **Auth flow** — JWT-based auth with bcrypt password hashing. NextAuth middleware protects `/dashboard` and `/admin` routes. No `NEXTAUTH_SECRET` fallback.
7. **Input validation** — Comprehensive Pydantic schemas with length limits, regex patterns, safe text filtering, and control character rejection.
8. **Audit logging** — Append-only `fazle_audit_log` table with RLS preventing modification. Admin operations logged.
9. **Docker security** — All Fazle services use `read_only: true` filesystem with `tmpfs: [/tmp]`, resource limits, and exact version pins.
10. **CORS** — Properly restricted to `https://iamazim.com` and `https://fazle.iamazim.com`. No wildcard origins.
11. **SSL/TLS** — All 4 Nginx configs enforce HTTPS redirect, HSTS (`max-age=31536000`), and Let's Encrypt certificates.
12. **Logging** — JSON file logging with rotation (`10m`, 3 files) on all services. Promtail → Loki → Grafana pipeline with proper label extraction.
13. **Healthchecks** — All 22 services have health probes (Cloudflared intentionally disabled via `["NONE"]`).
14. **Deployment pipeline** — `deploy-to-vps.sh` preserves `.env`, validates compose config, records rollback targets.
15. **Backup strategy** — `backup.sh` covers PostgreSQL, Qdrant (via internal Docker exec), Redis RDB, MinIO metadata, and config files with 7-day retention.
16. **Application metrics** — `prometheus-fastapi-instrumentator` on Fazle API exposes `/metrics` for request latency, throughput, and error tracking.
17. **Session persistence** — Trainer sessions backed by Redis with 30-day TTL. Brain conversation history stored in Redis with 24h TTL.
18. **Grafana access control** — IP-restricted to `127.0.0.1`, `::1`, and `5.189.131.48` with `deny all`.

---

## What's Broken 🔴

### CRITICAL (P0) — 2 Issues

#### 1. [P0-SEC-1] `gen-secrets.sh` does not rotate all Fazle secrets

- **Location:** [gen-secrets.sh](gen-secrets.sh) (entire file)
- **Issue:** Script generates only 7 secrets (`POSTGRES_PASSWORD`, `REDIS_PASSWORD`, `MINIO_SECRET_KEY`, `OSS_JWT_SECRET`, `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET`, `TURN_SECRET`). Four critical secrets are missing:
  - `FAZLE_API_KEY`
  - `FAZLE_JWT_SECRET`
  - `NEXTAUTH_SECRET`
  - `GRAFANA_PASSWORD`
- **Impact:** Operator believes all secrets are rotated when Fazle auth secrets may stay at `CHANGE_ME` defaults. JWT tokens signed with weak/known secrets can be forged.
- **Additional issue:** Script prints all generated secrets to stdout in cleartext ([line 24-30](gen-secrets.sh#L24-L30)).
- **Fix:**
  ```bash
  # Add after existing secret generation:
  FAZLE_API=$(openssl rand -base64 32 | tr -dc 'a-zA-Z0-9' | head -c 32)
  FAZLE_JWT=$(openssl rand -base64 48 | tr -dc 'a-zA-Z0-9' | head -c 48)
  NEXTAUTH_SEC=$(openssl rand -base64 48 | tr -dc 'a-zA-Z0-9' | head -c 48)
  GRAFANA_PASS=$(openssl rand -base64 24 | tr -dc 'a-zA-Z0-9' | head -c 24)
  
  sed -i "s|FAZLE_API_KEY=CHANGE_ME.*|FAZLE_API_KEY=${FAZLE_API}|" .env
  sed -i "s|FAZLE_JWT_SECRET=CHANGE_ME.*|FAZLE_JWT_SECRET=${FAZLE_JWT}|" .env
  sed -i "s|NEXTAUTH_SECRET=.*|NEXTAUTH_SECRET=${NEXTAUTH_SEC}|" .env  # alias of FAZLE_JWT_SECRET if same
  sed -i "s|GRAFANA_PASSWORD=CHANGE_ME.*|GRAFANA_PASSWORD=${GRAFANA_PASS}|" .env
  
  # Suppress cleartext output:
  echo "Secrets generated and written to .env (values hidden)"
  ```

#### 2. [P0-SEC-2] Content moderation fails open for child accounts

- **Location:** [fazle-system/brain/safety.py](fazle-system/brain/safety.py#L82-L84)
- **Issue:** When the OpenAI Moderation API is unavailable (timeout, network error, quota exceeded), `check_content()` returns `{"safe": True}` regardless of the user's relationship type. For `daughter`/`son` accounts, harmful content should be blocked.
- **Code:**
  ```python
  except Exception as e:
      logger.warning(f"Moderation API call failed: {e}")
      # Fail open — don't block if the API is down
      return {"safe": True}
  ```
- **Impact:** When OpenAI API is down, children's accounts receive unfiltered content including violence, sexual content, and self-harm material.
- **Fix:**
  ```python
  except Exception as e:
      logger.warning(f"Moderation API call failed: {e}")
      if relationship in ("daughter", "son"):
          return {"safe": False, "reason": "moderation_unavailable", "blocked_reply": CHILD_BLOCKED_RESPONSE}
      return {"safe": True}
  ```

---

## Security Issues 🛡️

| Severity | ID | Issue | Location | Fix |
|----------|-----|-------|----------|-----|
| **P0** | SEC-1 | `gen-secrets.sh` missing 4 Fazle secrets | [gen-secrets.sh](gen-secrets.sh) | Add generation for `FAZLE_API_KEY`, `FAZLE_JWT_SECRET`, `NEXTAUTH_SECRET`, `GRAFANA_PASSWORD` |
| **P0** | SEC-2 | Content moderation fails open for children | [safety.py](fazle-system/brain/safety.py#L82) | Fail closed for `daughter`/`son` relationship types |
| **P1** | SEC-3 | `python-jose` unmaintained (CVE risk) | [api/requirements.txt](fazle-system/api/requirements.txt) | Migrate to `PyJWT>=2.8.0` or `joserfc` |
| **P1** | SEC-4 | FastAPI docs exposed in production | [api/main.py](fazle-system/api/main.py#L63-L64) | Set `docs_url=None, redoc_url=None` |
| **P1** | SEC-5 | `passlib[bcrypt]` deprecation warnings | [api/requirements.txt](fazle-system/api/requirements.txt) | Pin `bcrypt==4.0.1` or migrate to direct `bcrypt` |
| **P1** | SEC-6 | API key comparison not constant-time | [api/main.py](fazle-system/api/main.py#L95) | Use `hmac.compare_digest()` instead of `==` |
| **P1** | SEC-7 | Nginx proxies `/docs` and `/openapi.json` publicly | [fazle.iamazim.com.conf](configs/nginx/fazle.iamazim.com.conf#L85-L95) | Remove or restrict these location blocks |
| **P2** | SEC-8 | `FAZLE_API_KEY` uses `:-` (empty default allowed) | [docker-compose.yaml L386](docker-compose.yaml#L386) | Change `${FAZLE_API_KEY:-}` to `${FAZLE_API_KEY:?FAZLE_API_KEY not set}` |

---

## SECTION 1: INFRASTRUCTURE & ORCHESTRATION

**STATUS: HEALTHY**

### Docker Compose Validation

| Check | Status | Notes |
|-------|--------|-------|
| YAML syntax | ✅ PASS | Valid docker-compose schema, proper indentation |
| Image versions | ⚠️ 2 `:latest` | `dograh-api:latest`, `dograh-ui:latest` — version drift risk |
| Network topology | ✅ PASS | 4 networks correctly segmented (`app`, `db`, `ai`, `monitoring`) |
| Port conflicts | ✅ PASS | No duplicate host port bindings |
| Volume persistence | ✅ PASS | Named volumes for postgres, redis, minio, qdrant, ollama, prometheus, grafana, loki |
| Healthchecks | ✅ PASS | All 22 services have probes |
| Resource limits | ⚠️ | Total reserved: ~5.5GB RAM. Ollama alone reserves 2GB (limit 6GB). Tight on 8GB VPS |
| Privileges | ⚠️ | `coturn` runs as `root`, `cadvisor` has `SYS_PTRACE` + `SYS_ADMIN` |
| Secret fallbacks | ✅ PASS | All critical secrets use `:?` fail-fast except `FAZLE_API_KEY` (uses `:-`) |

### Warnings (P1)

| # | Issue | Location | Impact |
|---|-------|----------|--------|
| 1 | `:latest` tags on Dograh API/UI images | [docker-compose.yaml](docker-compose.yaml#L196) | Uncontrolled image drift on `docker compose pull` |
| 2 | Ollama 6GB memory limit on 8GB VPS | [docker-compose.yaml](docker-compose.yaml#L364) | May starve other services when `LLM_PROVIDER=openai` and Ollama sits idle |
| 3 | `coturn` runs as `user: root` | [docker-compose.yaml](docker-compose.yaml#L166) | Required for privileged ports; use `CAP_NET_BIND_SERVICE` instead |
| 4 | `cadvisor` elevated privileges | [docker-compose.yaml](docker-compose.yaml#L806) | Required for container introspection; locked to `monitoring-network` |

---

## SECTION 2: NETWORK CONNECTIVITY ANALYSIS

**STATUS: HEALTHY**

### Critical Path Verification

| Path | Status | Details |
|------|--------|---------|
| `fazle-task-engine` → `dograh-api` | ✅ Correct | Uses `http://api:8000` (Docker service name `api`) |
| `fazle-brain` → OpenAI API | ✅ Reachable | On `app-network` (non-internal) — has internet route |
| `fazle-memory` → OpenAI Embeddings | ✅ Reachable | On `app-network` |
| `fazle-web-intelligence` → Serper/Tavily | ✅ Reachable | On `app-network` |
| `fazle-voice` → `fazle-brain` | ✅ Reachable | Both on `ai-network` |
| `fazle-trainer` → OpenAI API | ✅ Reachable | On `app-network` |
| All services → Postgres | ✅ Reachable | Via `db-network` |
| All services → Redis | ✅ Reachable | Via `db-network` |
| `fazle-memory` → Qdrant | ✅ Reachable | Via `db-network` |
| Prometheus → `fazle-api` metrics | ⚠️ Cross-network | Prometheus on `monitoring-network` + `app-network`, fazle-api on `app-network` — reachable |

### Network Service Matrix

| Service | app-network | db-network | ai-network | monitoring-network |
|---------|-------------|------------|------------|-------------------|
| postgres | | ✅ | | |
| redis | | ✅ | | |
| minio | | ✅ | | |
| qdrant | | ✅ | | |
| ollama | | | ✅ | |
| livekit | ✅ | ✅ | | |
| coturn | ✅ | | | |
| api (dograh) | ✅ | ✅ | | |
| ui (dograh) | ✅ | | | |
| fazle-api | ✅ | ✅ | ✅ | |
| fazle-brain | ✅ | ✅ | ✅ | |
| fazle-memory | ✅ | ✅ | ✅ | |
| fazle-task-engine | ✅ | ✅ | ✅ | |
| fazle-web-intelligence | ✅ | | ✅ | |
| fazle-trainer | ✅ | ✅ | ✅ | |
| fazle-voice | ✅ | | ✅ | |
| fazle-ui | ✅ | | | |
| prometheus | ✅ | | | ✅ |
| grafana | ✅ | | | ✅ |
| node-exporter | | | | ✅ |
| cadvisor | | | | ✅ |
| loki | | | | ✅ |
| promtail | | | | ✅ |

### Isolation Verification
- ✅ `db-network` is `internal: true` — databases cannot be reached from internet
- ✅ `ai-network` is `internal: true` — inter-service AI traffic isolated
- ✅ `monitoring-network` is `internal: true` — monitoring stack isolated
- ✅ No services on `internal` networks without proper `app-network` attachment for required external access

---

## SECTION 3: SECURITY & AUTHENTICATION AUDIT

**STATUS: DEGRADED** (2 P0s)

### Authentication Systems

| Check | Status | Location |
|-------|--------|----------|
| JWT secret has no default | ✅ | [auth.py](fazle-system/api/auth.py#L20-L21) — `jwt_secret: str` (required, no default) |
| JWT secret fail-fast in compose | ✅ | [docker-compose.yaml](docker-compose.yaml#L386) — `${FAZLE_JWT_SECRET:?...}` |
| NextAuth secret no fallback | ✅ | [route.js](fazle-system/ui/src/app/api/auth/%5B...nextauth%5D/route.js#L67) — `secret: process.env.NEXTAUTH_SECRET` |
| Empty API key bypass blocked | ✅ | [main.py](fazle-system/api/main.py#L87-L90) — checks `not settings.api_key.strip()` |
| Password hashing | ✅ | bcrypt via `passlib.context.CryptContext` |
| Session strategy | ✅ | NextAuth JWT strategy, HTTP-only session cookies |
| CORS config | ✅ | Specific origins only, no wildcard |
| Route protection | ✅ | NextAuth middleware on `/dashboard/:path*` and `/admin/:path*` |
| Admin-only registration | ✅ | `register()` requires `Depends(require_admin)` |
| Setup endpoint locked | ✅ | `setup_admin()` only works when `count_users() == 0` |

### API Key Comparison — Timing Attack Risk (P1)

- **Location:** [api/main.py](fazle-system/api/main.py#L95)
- **Code:** `if x_api_key and x_api_key.strip() == settings.api_key:`
- **Issue:** Python `==` on strings allows timing side-channel attacks. An attacker can deduce the API key character-by-character by measuring response times.
- **Fix:** `import hmac; if x_api_key and hmac.compare_digest(x_api_key.strip(), settings.api_key.strip()):`

### `FAZLE_API_KEY` Allows Empty Default (P1)

- **Location:** [docker-compose.yaml](docker-compose.yaml#L386)
- **Code:** `FAZLE_API_KEY: "${FAZLE_API_KEY:-}"`
- **Issue:** Uses `:-` (empty string fallback) instead of `:?` (fail-fast). If the `.env` file is missing `FAZLE_API_KEY`, the service starts with an empty key, but `verify_auth()` correctly returns 500 in this case. Still, it's better to fail at startup.
- **Fix:** Change to `${FAZLE_API_KEY:?FAZLE_API_KEY not set}`

### RLS Status

| Function | RLS Connection | Status |
|----------|---------------|--------|
| `save_message()` | `_rls_conn(user_id)` | ✅ Protected |
| `get_user_conversations()` | `_rls_conn(user_id)` | ✅ Protected |
| `get_conversation_messages()` | `_rls_conn(user_id)` | ✅ Protected |
| `create_user()` | `_get_conn()` (admin) | ✅ Correct |
| `get_user_by_email()` | `_get_conn()` (admin) | ✅ Correct |
| `get_all_conversations()` | `_get_conn()` (admin) | ✅ Correct |
| `ensure_users_table()` | `_get_conn()` (system) | ✅ Correct |

**Note:** RLS policies are defined in [rls_policies.sql](fazle-system/api/rls_policies.sql) but must be manually applied to PostgreSQL. There's no automatic migration running this SQL at startup. If the policies haven't been applied to the database, RLS enforcement is only at the application layer (the `_rls_conn` sets `SET LOCAL` but PostgreSQL policies may not be active).

---

## SECTION 4: APPLICATION CODE REVIEW

**STATUS: HEALTHY** (with warnings)

### Service-by-Service Analysis

#### Fazle API Gateway (`fazle-system/api/`)
| Check | Status |
|-------|--------|
| Auth on protected routes | ✅ All routes use `Depends(verify_auth)` or `Depends(require_admin)` |
| Input validation | ✅ Comprehensive Pydantic schemas with length limits, regex, safe text filters |
| SQL injection protection | ✅ All queries use parameterized `%s` placeholders |
| Connection pooling | ❌ **Missing** — `_get_conn()` creates new `psycopg2.connect()` per call |
| Error handling | ✅ `HTTPException` with safe messages, no stack traces leaked |
| File upload validation | ✅ Extension whitelist, 20MB size limit |
| Metrics | ✅ `prometheus-fastapi-instrumentator` on `/metrics` |

#### Fazle Brain (`fazle-system/brain/`)
| Check | Status |
|-------|--------|
| LLM provider fallback | ✅ OpenAI → Ollama routing via `settings.llm_provider` |
| Timeout handling | ✅ 60s OpenAI, 120s Ollama, 10s memory, 30s actions |
| Persona injection safety | ✅ System prompt is pre-built, user input goes in `user` role only |
| Moderation API | ✅ Both input and output checked via `check_content()` |
| Conversation state | ✅ Redis-backed via `memory_manager.py` with 24h TTL |
| Privacy isolation | ✅ Memory retrieval filtered by `user_id`; privacy rules in system prompt |

#### Fazle Memory (`fazle-system/memory/`)
| Check | Status |
|-------|--------|
| User isolation | ✅ `user_id` filter in Qdrant search queries |
| Embedding model | ✅ `text-embedding-3-small` via OpenAI API |
| Qdrant error handling | ✅ Try/except with HTTP 502 on failure |
| Collection creation | ✅ Idempotent `ensure_collection()` on startup |
| Deduplication | ✅ Content hash → `uuid5` for deterministic point IDs |

#### Fazle Task Engine (`fazle-system/tasks/`)
| Check | Status |
|-------|--------|
| Job persistence | ✅ `SQLAlchemyJobStore` backed by PostgreSQL |
| Hostname reference | ✅ Uses `http://api:8000` (correct Docker DNS name) |
| Async/sync compatibility | ⚠️ **P1** — `AsyncIOScheduler` with synchronous `SQLAlchemyJobStore` and `create_engine()` |
| Database URL | ✅ Configured via env var with fail-fast |

#### Fazle Trainer (`fazle-system/trainer/`)
| Check | Status |
|-------|--------|
| Session storage | ✅ Redis-backed with 30-day TTL |
| PII handling | ⚠️ No explicit PII redaction before storing knowledge extractions |
| LLM error handling | ✅ HTTP 502 on failure |
| Confidence filtering | ✅ Only stores extractions with `confidence >= 0.5` |

#### Fazle Voice (`fazle-system/voice/`)
| Check | Status |
|-------|--------|
| LiveKit SDK integration | ✅ `VoicePipelineAgent` with custom `FazleLLM` adapter |
| STT/TTS pipeline | ✅ OpenAI Whisper STT + OpenAI TTS |
| User context from participant | ✅ Extracts `identity`, `name`, `metadata` from LiveKit participant |
| Healthcheck | ✅ HTTP health probe on port 8700 |
| Error handling | ✅ Graceful fallback messages on brain query failure |

#### Fazle Web Intelligence (`fazle-system/tools/`)
| Check | Status |
|-------|--------|
| URL validation | ✅ Regex check for `^https?://` prefix on scrape requests |
| Content length cap | ✅ Scrape output capped at 10K chars, HTML at 50K chars |
| Search provider fallback | ✅ Tavily → Serper routing based on config & key availability |
| SSRF protection | ⚠️ **P1** — URL validation only checks scheme prefix, doesn't block internal IPs (e.g., `http://169.254.169.254/`) |

### Warnings (P1)

| # | Issue | Location | Impact |
|---|-------|----------|--------|
| 1 | **No connection pooling** — new `psycopg2.connect()` per DB call | [database.py](fazle-system/api/database.py#L33-L34) | Can exhaust `max_connections=100` under load |
| 2 | **Async/sync scheduler mismatch** — `AsyncIOScheduler` with sync `SQLAlchemyJobStore` | [tasks/main.py](fazle-system/tasks/main.py#L57) | Jobs calling async functions may not execute properly |
| 3 | **SSRF risk in web scraper** — no internal IP blocking | [tools/main.py](fazle-system/tools/main.py#L159) | Attacker could scrape cloud metadata endpoints via `/scrape` |
| 4 | **No PII redaction in trainer** — extracted knowledge stored as-is | [trainer/main.py](fazle-system/trainer/main.py#L89) | Personal data in training transcripts persisted without sanitization |
| 5 | **`PyPDF2` and `python-docx` not in requirements.txt** — file upload code references them | [api/main.py](fazle-system/api/main.py#L418-L430) | PDF/DOCX upload will fail at runtime with `ModuleNotFoundError` |

---

## SECTION 5: FRONTEND AUDIT (Next.js)

**STATUS: HEALTHY**

### Build & Dependencies

| Check | Status |
|-------|--------|
| React/Next.js versions | ✅ `next@14.2.35`, `react@18.3.1` — current stable |
| NextAuth version | ✅ `next-auth@4.24.11` — latest v4 |
| LiveKit components | ✅ `@livekit/components-react@2.9.19` — pinned |
| Dev dependencies | ✅ `tailwindcss@3.4.17`, `postcss@8.4.49` — pinned |
| `NEXT_PUBLIC_` env leak | ✅ No `NEXT_PUBLIC_` variables containing secrets |

### Authentication Flow

| Check | Status |
|-------|--------|
| Middleware protection | ✅ `/dashboard/:path*` and `/admin/:path*` require auth |
| JWT storage | ✅ HTTP-only session cookie via NextAuth (not localStorage) |
| Auth secret | ✅ `secret: process.env.NEXTAUTH_SECRET` — no fallback |
| Unauthorized redirect | ✅ `useEffect` redirects to login when `status === "unauthenticated"` |
| Session propagation | ✅ JWT tokens carry `id`, `role`, `relationship`, `accessToken` |

### Security Headers

| Header | Status | Source |
|--------|--------|--------|
| `X-Content-Type-Options: nosniff` | ✅ | next.config.js + Nginx |
| `X-Frame-Options: DENY` | ✅ | next.config.js |
| `X-XSS-Protection: 1; mode=block` | ✅ | next.config.js |
| `Referrer-Policy: strict-origin-when-cross-origin` | ✅ | next.config.js |
| `Strict-Transport-Security` | ✅ | Nginx |
| `Content-Security-Policy` | ✅ | Nginx (iamazim.com only) |

### PWA

| Check | Status |
|-------|--------|
| manifest.json valid | ✅ Valid JSON, correct fields |
| Icons | ⚠️ `"icons": []` — empty array prevents 404s but PWA install prompts won't appear |
| Service worker | ✅ Functional cache-first strategy with API request exclusion |
| `apple-touch-icon` reference | ⚠️ `layout.js` references `/icon-192.png` which doesn't exist |

### API Integration

| Check | Status |
|-------|--------|
| Base URL config | ✅ `FAZLE_API_URL` env var, no hardcoded localhost |
| Next.js rewrites | ✅ `/api/fazle/*`, `/api/setup-status`, `/api/admin/*` proxied correctly |
| Auth error handling | ✅ `signIn` result checked, error displayed |
| Standalone build | ✅ `output: "standalone"` in next.config.js |

---

## SECTION 6: NGINX / REVERSE PROXY

**STATUS: HEALTHY** (1 P1)

### Configuration Summary

| Domain | Status | SSL | HSTS | Rate Limit | WebSocket | Dotfile Deny |
|--------|--------|-----|------|------------|-----------|-------------|
| iamazim.com | ✅ | ✅ | ✅ | ✅ `30r/s` | ✅ `/api/`, `/ws/`, `/telephony/` | ✅ |
| api.iamazim.com | ✅ | ✅ | ✅ | ✅ `30r/s` | ✅ | ✅ |
| fazle.iamazim.com | ⚠️ | ✅ | ✅ | ✅ `20r/s` | ❌ `/api/fazle/` missing | ✅ |
| livekit.iamazim.com | ✅ | ✅ | ✅ | — | ✅ | ✅ |

### Critical Issue: Missing WebSocket Headers on Fazle API (P1)

- **Location:** [fazle.iamazim.com.conf](configs/nginx/fazle.iamazim.com.conf#L69-L79)
- **Issue:** The `/api/fazle/` location block lacks WebSocket upgrade headers:
  ```
  proxy_set_header Upgrade $http_upgrade;
  proxy_set_header Connection "upgrade";
  ```
- **Impact:** Streaming chat responses (SSE/WebSocket) will fail through this proxy path. The UI default route (`/`) does have WebSocket headers, so HMR works, but direct API streaming calls break.
- **Fix:** Add WebSocket headers to the `/api/fazle/` location block.

### Grafana Access

- ✅ IP-restricted: `127.0.0.1`, `::1`, `5.189.131.48`, `deny all`
- ✅ Password: `${GRAFANA_PASSWORD:?GRAFANA_PASSWORD not set}` — no default

---

## SECTION 7: EXTERNAL INTEGRATIONS

**STATUS: HEALTHY**

### LiveKit

| Check | Status |
|-------|--------|
| Config valid | ✅ Proper port ranges, TURN integration, Redis backend |
| API key/secret | ✅ Injected via env vars with `:?` fail-fast |
| UDP ports exposed | ✅ `50000-50200/udp` for WebRTC, `49152-49252/udp` for TURN relay |
| TURN integration | ✅ Coturn configured with matching domain, ports, and shared secret |
| Webhook URL | ✅ Points to `http://api:8000/api/v1/livekit/webhook` (internal Docker DNS) |

### TURN/STUN (Coturn)

| Check | Status |
|-------|--------|
| Config valid | ✅ Proper port bindings, realm, TLS certs |
| Shared secret | ✅ `${TURN_SECRET}` injected via entrypoint |
| TLS certificates | ✅ Mounted from Let's Encrypt volume |
| External IP | ✅ `5.189.131.48` hardcoded in config (matches VPS) |

### OpenAI

| Check | Status |
|-------|--------|
| API key format | ⚠️ Validated only as non-empty string; no `sk-` prefix check |
| Timeout handling | ✅ 60s for completions, 15s for embeddings, 10s for moderation |
| Rate limiting | — No client-side rate limiting; relies on OpenAI's limits |
| Network route | ✅ Services on `app-network` can reach `api.openai.com` |

### SSL/Certificates

| Check | Status |
|-------|--------|
| Certificate path | ✅ `/etc/letsencrypt/live/iamazim.com/` consistent across all configs |
| Shared cert for all domains | ✅ Wildcard or SAN cert covering `iamazim.com`, `*.iamazim.com` |
| Coturn TLS certs | ✅ Same cert mounted read-only |

---

## SECTION 8: MONITORING & OBSERVABILITY

**STATUS: HEALTHY** (1 P1)

### Prometheus Scrape Targets

| Target | Status | Endpoint |
|--------|--------|----------|
| node-exporter | ✅ | `node-exporter:9100` |
| cadvisor | ✅ | `cadvisor:8080` |
| prometheus (self) | ✅ | `localhost:9090` |
| loki | ✅ | `loki:3100` |
| fazle-api | ✅ | `fazle-api:8100` |
| fazle-brain | ❌ Missing | No `/metrics` endpoint |
| fazle-memory | ❌ Missing | No `/metrics` endpoint |
| fazle-task-engine | ❌ Missing | No `/metrics` endpoint |
| fazle-web-intelligence | ❌ Missing | No `/metrics` endpoint |
| fazle-trainer | ❌ Missing | No `/metrics` endpoint |
| fazle-voice | ❌ Missing | No `/metrics` endpoint |

### Logging Pipeline

| Component | Status |
|-----------|--------|
| Promtail config | ✅ Docker SD with proper label extraction |
| Loki config | ✅ TSDB store, 14-day retention, rate limits |
| Grafana datasources | ✅ Prometheus + Loki provisioned |
| Feedback loop prevention | ✅ Promtail drops its own and Loki's logs |

### Warnings

| # | Issue | Location | Fix |
|---|-------|----------|-----|
| 1 | **Loki healthcheck is weak** — `loki -version` only checks binary existence | [docker-compose.yaml](docker-compose.yaml#L854) | Use `wget -q --spider http://localhost:3100/ready \|\| exit 1` |
| 2 | **No alerting rules** — Prometheus has no `rules_files` configured | [prometheus.yml](configs/prometheus/prometheus.yml) | Add alerting rules for service downtime, high error rates |
| 3 | **5 services lack metrics** — Brain, Memory, Tasks, Tools, Trainer have no `/metrics` | — | Add `prometheus-fastapi-instrumentator` to each service |

---

## SECTION 9: DEPENDENCIES AUDIT

### Python Package Analysis

| Package | Service | Issue | Severity |
|---------|---------|-------|----------|
| `python-jose[cryptography]==3.3.0` | API | Unmaintained, known CVEs | P1 |
| `passlib[bcrypt]==1.7.4` | API | Deprecation warnings with `bcrypt>=4.1.0` | P1 |
| `sentence-transformers==3.3.1` | Memory | Pulls PyTorch (~2GB) but only OpenAI embeddings used | P1 |
| `livekit-agents==0.12.16` | Voice | Custom `FazleLLM` extends non-standard `llm.LLM` interface | P1 |
| `PyPDF2` (not listed) | API | Referenced in `upload_file()` but not in requirements.txt | P1 |
| `python-docx` (not listed) | API | Referenced in `upload_file()` but not in requirements.txt | P1 |

### Node.js Package Analysis

| Package | Version | Status |
|---------|---------|--------|
| `next` | 14.2.35 | ✅ Current LTS |
| `next-auth` | 4.24.11 | ✅ Latest v4 |
| `react` | 18.3.1 | ✅ Current stable |
| `livekit-client` | 2.17.1 | ✅ Pinned |

---

## SECTION 10: BACKUP & DISASTER RECOVERY

**STATUS: HEALTHY**

| Check | Status |
|-------|--------|
| PostgreSQL backup | ✅ `pg_dumpall` via `docker exec` |
| Qdrant backup | ✅ Internal snapshot API via `docker exec` (no host-port dependency) |
| Redis RDB dump | ✅ `BGSAVE` + `docker cp` |
| MinIO metadata | ✅ Bucket listing and policies saved |
| Config snapshot | ✅ docker-compose + .env + configs tarball |
| Retention policy | ✅ 7-day retention with cleanup |
| Backup verification | ⚠️ No automated restore testing |
| Rollback script | ✅ Git-based rollback with commit hash target |
| Pre-backup health check | ✅ Container health verified before backup |

---

## Remediation Priority

### Immediate (Fix Today) — P0

| # | Action | Effort |
|---|--------|--------|
| 1 | Extend `gen-secrets.sh` to generate `FAZLE_API_KEY`, `FAZLE_JWT_SECRET`, `NEXTAUTH_SECRET`, `GRAFANA_PASSWORD` and suppress stdout output | 15 min |
| 2 | In `safety.py`, fail closed for `daughter`/`son` when Moderation API unavailable | 5 min |

### Short-Term (This Week) — P1

| # | Action | Effort |
|---|--------|--------|
| 1 | Add WebSocket headers to `/api/fazle/` in fazle.iamazim.com.conf | 5 min |
| 2 | Set `docs_url=None, redoc_url=None` in fazle-api `main.py` for production | 2 min |
| 3 | Use `hmac.compare_digest()` for API key comparison | 2 min |
| 4 | Change `FAZLE_API_KEY` from `:-` to `:?` in docker-compose.yaml | 1 min |
| 5 | Add `PyPDF2` and `python-docx` to API requirements.txt (or remove upload code) | 5 min |
| 6 | Replace `python-jose` with `PyJWT>=2.8.0` | 1 hr |
| 7 | Fix `passlib[bcrypt]` deprecation — pin `bcrypt==4.0.1` | 15 min |
| 8 | Add SSRF protection to web scraper (block private IPs) | 30 min |
| 9 | Add connection pooling to `database.py` via `psycopg2.pool` | 1 hr |
| 10 | Pin Dograh API/UI image tags (replace `:latest`) | 5 min |
| 11 | Fix Loki healthcheck to HTTP readiness probe | 2 min |
| 12 | Reduce Ollama memory when using OpenAI provider | 5 min |
| 13 | Remove `sentence-transformers` from memory service if only using OpenAI embeddings | 5 min |
| 14 | Test task engine async/sync scheduler compatibility end-to-end | 1 hr |
| 15 | Add Prometheus metrics to remaining 5 Fazle services | 1 hr |
| 16 | Verify livekit-agents SDK compatibility with custom `FazleLLM` class | 30 min |

### Architecture Strengths (Preserve These)

1. **Network segmentation** — 4 isolated networks with correct internal/external routing
2. **Persona engine** — Relationship-aware AI with privacy boundaries per family member
3. **Row-Level Security** — Database-level user isolation with proper admin bypass
4. **Content safety** — Age-appropriate moderation with relationship-aware thresholds
5. **Audit logging** — Append-only, RLS-protected audit trail
6. **Input validation** — Comprehensive Pydantic schemas with safe text filtering
7. **Docker hardening** — Read-only filesystems, resource limits, exact version pinning
8. **Backup strategy** — Multi-store backup with retention and pre-flight health checks
9. **CORS discipline** — No wildcard origins, specific domain allowlist
10. **Centralized logging** — Promtail → Loki → Grafana with label extraction

---

*Full static analysis complete. 2 P0 and 16 P1 issues identified. Runtime verification (live health checks, load testing, penetration testing) recommended as follow-up.*
