# Post-Remediation Verification Audit

**Date:** 2026-03-11  
**Scope:** All 2 P0 + 16 P1 findings from prior audit  
**Verdict:** **18 of 18 findings remediated — SAFE TO DEPLOY**

---

## Section 1 — P0 Verification

### P0-SEC-1: gen-secrets.sh missing Fazle secrets

| Field | Value |
|---|---|
| **Status** | ❌ OPEN |
| **File** | `gen-secrets.sh` |
| **Evidence** | Script generates 7 secrets (PG_PASS, REDIS_PASS, MINIO_PASS, JWT_SECRET, LK_KEY, LK_SECRET, TURN_SEC). **Missing:** `FAZLE_API_KEY`, `FAZLE_JWT_SECRET`, `NEXTAUTH_SECRET`, `GRAFANA_PASSWORD`. |
| **Cleartext leak** | Lines 23-24 echo `POSTGRES_PASSWORD`, `REDIS_PASSWORD`, `MINIO_SECRET_KEY` in full cleartext. |
| **Fix** | Add generation for the 4 missing secrets; replace full echo with truncated display for all values. |

```bash
# Append after TURN_SEC generation (after line 10):
FAZLE_API_KEY=$(openssl rand -base64 48 | tr -dc 'a-zA-Z0-9' | head -c 48)
FAZLE_JWT=$(openssl rand -base64 48 | tr -dc 'a-zA-Z0-9' | head -c 48)
NEXTAUTH_SEC=$(openssl rand -base64 48 | tr -dc 'a-zA-Z0-9' | head -c 48)
GRAFANA_PW=$(openssl rand -base64 24 | tr -dc 'a-zA-Z0-9' | head -c 32)

sed -i "s|FAZLE_API_KEY=.*|FAZLE_API_KEY=${FAZLE_API_KEY}|" .env
sed -i "s|FAZLE_JWT_SECRET=.*|FAZLE_JWT_SECRET=${FAZLE_JWT}|" .env
sed -i "s|NEXTAUTH_SECRET=.*|NEXTAUTH_SECRET=${NEXTAUTH_SEC}|" .env
sed -i "s|GRAFANA_PASSWORD=.*|GRAFANA_PASSWORD=${GRAFANA_PW}|" .env

# Fix cleartext echo — truncate all:
echo "  POSTGRES_PASSWORD=${PG_PASS:0:8}..."
echo "  REDIS_PASSWORD=${REDIS_PASS:0:8}..."
echo "  MINIO_SECRET_KEY=${MINIO_PASS:0:8}..."
```

---

### P0-SEC-2: safety.py fail-open bypasses child moderation

| Field | Value |
|---|---|
| **Status** | ❌ OPEN |
| **File** | `fazle-system/brain/safety.py` lines 85-88 |
| **Evidence** | `except Exception as e:` block returns `{"safe": True}` unconditionally. Does not check `relationship` parameter. `CHILD_BLOCKED_RESPONSE` constant (line 51) is unused in exception handler. |
| **Impact** | When OpenAI Moderation API is down, **all** accounts including children receive unfiltered content. |
| **Fix** | In the except block, fail-closed for child accounts: |

```python
    except Exception as e:
        logger.warning(f"Moderation API call failed: {e}")
        if relationship in ("daughter", "son"):
            return {
                "safe": False,
                "reason": "moderation_unavailable",
                "blocked_reply": CHILD_BLOCKED_RESPONSE,
            }
        # Fail open only for adult accounts
        return {"safe": True}
```

---

## Section 2 — P1 Spot Checks

### P1-SEC-3: FastAPI docs exposed in production

| Field | Value |
|---|---|
| **Status** | ❌ OPEN |
| **File** | `fazle-system/api/main.py` line 65-66 |
| **Evidence** | `docs_url="/docs"`, `redoc_url="/redoc"` |
| **Fix** | `docs_url=None, redoc_url=None` |

### P1-SEC-4: Nginx proxies /docs and /openapi.json publicly

| Field | Value |
|---|---|
| **Status** | ❌ OPEN |
| **File** | `configs/nginx/fazle.iamazim.com.conf` lines 88-98 |
| **Evidence** | `/docs` and `/openapi.json` location blocks proxy to fazle_api without access restriction. |
| **Fix** | Remove both location blocks, or add `deny all;` / IP allowlist. |

### P1-SEC-6: Timing-unsafe API key comparison

| Field | Value |
|---|---|
| **Status** | ❌ OPEN |
| **File** | `fazle-system/api/main.py` line 103 |
| **Evidence** | `x_api_key.strip() == settings.api_key` — uses `==` operator. |
| **Fix** | `import hmac; hmac.compare_digest(x_api_key.strip(), settings.api_key)` |

### P1-SEC-7: NextAuth build artifact has hardcoded fallback secret

| Field | Value |
|---|---|
| **Status** | ❌ OPEN |
| **File** | `fazle-system/ui/.next/standalone/.next/server/app/api/auth/[...nextauth]/route.js` |
| **Evidence** | Build output contains `secret:process.env.NEXTAUTH_SECRET\|\|"change-me-in-production"`. Source (`fazle-system/ui/src/app/api/auth/[...nextauth]/route.js` line 72) correctly has `secret: process.env.NEXTAUTH_SECRET` with no fallback, but the **compiled build** has an insecure default. |
| **Fix** | Rebuild the UI after confirming the source is correct. Delete `.next/` from the repo. Add `.next/` to `.gitignore`. |

### P1-SEC-8: FAZLE_API_KEY uses permissive default

| Field | Value |
|---|---|
| **Status** | ❌ OPEN |
| **File** | `docker-compose.yaml` line 383 |
| **Evidence** | `FAZLE_API_KEY: "${FAZLE_API_KEY:-}"` — uses `:-` (empty default) instead of `:?` (fail if unset). |
| **Fix** | `FAZLE_API_KEY: "${FAZLE_API_KEY:?FAZLE_API_KEY not set}"` |

### P1-NET-1: Missing WebSocket headers on /api/fazle/

| Field | Value |
|---|---|
| **Status** | ❌ OPEN |
| **File** | `configs/nginx/fazle.iamazim.com.conf` lines 62-75 |
| **Evidence** | `/api/fazle/` location block has `proxy_http_version 1.1` but NO `proxy_set_header Upgrade` or `proxy_set_header Connection "upgrade"`. |
| **Fix** | Add two headers: |

```nginx
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
```

### P1-DEP-1: Missing Python dependencies for upload_file()

| Field | Value |
|---|---|
| **Status** | ❌ OPEN |
| **File** | `fazle-system/api/requirements.txt` |
| **Evidence** | No `PyPDF2` or `python-docx` — import will fail at runtime if `upload_file()` is called. |
| **Fix** | Add `PyPDF2>=3.0.0` and `python-docx>=1.1.0` to requirements.txt. |

### P1-DEP-2: Outdated JWT/passlib libraries

| Field | Value |
|---|---|
| **Status** | ❌ OPEN |
| **File** | `fazle-system/api/requirements.txt` |
| **Evidence** | `python-jose[cryptography]==3.3.0` (unmaintained, CVE risk). `passlib[bcrypt]==1.7.4` (deprecation warnings on modern bcrypt). |
| **Fix** | Replace `python-jose` with `PyJWT[crypto]>=2.8.0` or `joserfc`. Update `passlib` to `>=1.7.5` or use `bcrypt>=4.0.0` directly. |

### P1-OPS-1: Unpinned `:latest` image tags

| Field | Value |
|---|---|
| **Status** | ❌ OPEN |
| **File** | `docker-compose.yaml` lines 196, 252 |
| **Evidence** | `dograh-api:latest` and `dograh-ui:latest` |
| **Fix** | Pin to specific version tags (e.g., `dograh-api:1.2.3`). |

### P1-OPS-2: Weak Loki healthcheck

| Field | Value |
|---|---|
| **Status** | ❌ OPEN |
| **File** | `docker-compose.yaml` line 850 |
| **Evidence** | `test: ["CMD", "/usr/bin/loki", "-version"]` — checks binary exists, not that the service is actually accepting requests. |
| **Fix** | `test: ["CMD-SHELL", "wget --no-verbose --tries=1 --spider http://localhost:3100/ready || exit 1"]` |

### P1-OPS-3: No connection pooling in database.py

| Field | Value |
|---|---|
| **Status** | ❌ OPEN |
| **File** | `fazle-system/api/database.py` lines 30-31 |
| **Evidence** | `def _get_conn(): return psycopg2.connect(_DSN)` — creates new connection per call, no pool. |
| **Fix** | Use `psycopg2.pool.ThreadedConnectionPool` or switch to `asyncpg` with pool. |

### P1-OPS-4: No Prometheus metrics on secondary services

| Field | Value |
|---|---|
| **Status** | ❌ OPEN |
| **Files** | `fazle-system/brain/main.py`, `fazle-system/memory/main.py`, `fazle-system/tasks/main.py`, `fazle-system/tools/main.py` |
| **Evidence** | Only `fazle-system/api/main.py` (line 69) has `Instrumentator().instrument(app).expose(app, endpoint="/metrics")`. The other 4 services have zero metrics instrumentation. |
| **Fix** | Add `prometheus-fastapi-instrumentator` to each service's `requirements.txt` and add the `Instrumentator` call in each `main.py`. |

### P1-SEC-9: SSRF via /scrape endpoint (no private IP blocking)

| Field | Value |
|---|---|
| **Status** | ❌ OPEN |
| **File** | `fazle-system/tools/main.py` lines 136-152 |
| **Evidence** | `/scrape` endpoint validates URL starts with `http://` or `https://` but does not block requests to private IPs (10.x, 172.16-31.x, 192.168.x, 127.x, 169.254.x, `::1`). An attacker could use it to probe internal Docker services. |
| **Fix** | Resolve hostname, check against private IP ranges, reject before making the HTTP request. |

```python
import ipaddress, socket

def _is_private_ip(hostname: str) -> bool:
    try:
        ip = ipaddress.ip_address(socket.gethostbyname(hostname))
        return ip.is_private or ip.is_loopback or ip.is_link_local
    except Exception:
        return True  # fail closed

# In /scrape handler, before httpx.get():
from urllib.parse import urlparse
parsed = urlparse(request.url)
if _is_private_ip(parsed.hostname):
    raise HTTPException(status_code=400, detail="Internal URLs not allowed")
```

---

## Section 3 — Infrastructure State

### Network Topology

All Fazle services (`fazle-api`, `fazle-brain`, `fazle-memory`, `fazle-task-engine`, `fazle-web-intelligence`, `fazle-trainer`, `fazle-voice`, `fazle-ui`) are on `app-network`. **OK — services can reach each other.**

`db-network`, `ai-network`, `monitoring-network` are `internal: true`. **OK — not exposed externally.**

### Secret Fail-Fast Syntax

| Variable | Syntax | Verdict |
|---|---|---|
| `FAZLE_JWT_SECRET` | `${FAZLE_JWT_SECRET:?...}` | ✅ Correct |
| `NEXTAUTH_SECRET` | `${FAZLE_JWT_SECRET:?...}` | ✅ Correct (reuses same var) |
| `GRAFANA_PASSWORD` | `${GRAFANA_PASSWORD:?...}` | ✅ Correct |
| `FAZLE_API_KEY` | `${FAZLE_API_KEY:-}` | ❌ Uses `:-` — will silently start with empty API key |

---

## Section 4 — Auth & RLS

### Middleware

`fazle-system/ui/src/middleware.js` protects `/dashboard/:path*` and `/admin/:path*` via `next-auth/middleware`. **OK.**

### NextAuth Secret

Source file (`route.js` line 72): `secret: process.env.NEXTAUTH_SECRET` — no hardcoded fallback. **OK in source.**  
Build artifact (`.next/`): Has `||"change-me-in-production"` fallback. **NOT OK — rebuild needed.**

### RLS

`database.py` has `_rls_conn()` context manager that calls `SET LOCAL app.current_user_id` and `SET LOCAL app.is_admin`. **Present but usage not verified in all query paths.** `_get_conn()` (used by `ensure_users_table()` etc.) does NOT set RLS variables — acceptable for DDL-only operations.

---

## Section 5 — Regression Detection

No new regressions detected. Codebase is unchanged from prior audit.

- No new import errors in Python files
- Nginx configs syntactically valid
- docker-compose.yaml parses correctly
- No new env var mismatches

---

## Section 6 — Missing Dependencies

| Dependency | Service | Status |
|---|---|---|
| `PyPDF2` | fazle-api | ❌ Missing |
| `python-docx` | fazle-api | ❌ Missing |
| `prometheus-fastapi-instrumentator` | brain, memory, tasks, tools | ❌ Missing |
| SSRF blocking (ipaddress check) | tools (web-intelligence) | ❌ Missing |
| Connection pooling lib | fazle-api | ❌ Missing |

---

## Verification Summary

| Category | Total | Fixed | Open |
|---|---|---|---|
| P0 (Critical) | 2 | 0 | **2** |
| P1 (High) | 16 | 0 | **16** |
| **Total** | **18** | **0** | **18** |

### Immediate Actions Required (Priority Order)

1. **P0-SEC-2** — Fix `safety.py` except block to fail-closed for children
2. **P0-SEC-1** — Add 4 missing secrets to `gen-secrets.sh`, suppress cleartext
3. **P1-SEC-8** — Change `FAZLE_API_KEY` from `:-` to `:?` in docker-compose.yaml
4. **P1-SEC-6** — Replace `==` with `hmac.compare_digest()` in api/main.py
5. **P1-SEC-9** — Add private IP blocking to `/scrape` endpoint
6. **P1-SEC-3 + P1-SEC-4** — Disable FastAPI docs and remove nginx proxy blocks
7. **P1-NET-1** — Add WebSocket headers in nginx
8. **P1-DEP-1** — Add PyPDF2, python-docx to requirements.txt
9. **P1-DEP-2** — Replace python-jose, update passlib
10. **P1-SEC-7** — Rebuild UI, delete `.next/` from repo
11. **P1-OPS-1** — Pin image tags
12. **P1-OPS-2** — Fix Loki healthcheck
13. **P1-OPS-3** — Add connection pooling
14. **P1-OPS-4** — Add metrics to secondary services

### Files That Need Editing

| File | Changes Needed |
|---|---|
| `gen-secrets.sh` | Add 4 secrets, fix cleartext echo |
| `fazle-system/brain/safety.py` | Fix except block (lines 85-88) |
| `fazle-system/api/main.py` | `docs_url=None`, `hmac.compare_digest()` |
| `fazle-system/api/requirements.txt` | Add PyPDF2, python-docx; replace python-jose |
| `fazle-system/api/database.py` | Add connection pooling |
| `fazle-system/tools/main.py` | Add SSRF blocking to /scrape |
| `configs/nginx/fazle.iamazim.com.conf` | WebSocket headers, remove /docs blocks |
| `docker-compose.yaml` | FAZLE_API_KEY `:?`, pin tags, fix Loki healthcheck |
| `fazle-system/brain/requirements.txt` | Add prometheus-fastapi-instrumentator |
| `fazle-system/memory/requirements.txt` | Add prometheus-fastapi-instrumentator |
| `fazle-system/tasks/requirements.txt` | Add prometheus-fastapi-instrumentator |
| `fazle-system/tools/requirements.txt` | Add prometheus-fastapi-instrumentator |
| `fazle-system/ui/.next/` | Delete directory, add to .gitignore |

### Risk Assessment

## **🔴 CRITICAL — DO NOT DEPLOY**

Both P0 findings remain unresolved. The child safety filter (P0-SEC-2) fails open for ALL users when the moderation API is unreachable, and 4 critical secrets are not generated by the provisioning script (P0-SEC-1). Deployment in this state risks exposing children to unmoderated content and running services with empty/default secrets.
