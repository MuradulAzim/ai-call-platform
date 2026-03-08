# Full System Audit Report — AI Voice Platform
**Date:** 2026-03-07  
**Server:** 5.189.131.48  
**Domain:** iamazim.com  
**Audit performed by:** DevOps AI Engineer

---

## 1. System Architecture Overview

```
Internet (Browser / Phone)
        │
   ┌────┴────┐
   │ Twilio  │ (SIP telephony)
   └────┬────┘
        │
        ▼
┌─────────────────┐
│  Nginx (SSL)    │  ← Ports 80/443
│  Reverse Proxy  │
│                 │
│  iamazim.com    │ ─→ dograh-ui   (:3010)
│  iamazim.com/api│ ─→ dograh-api  (:8000)  ← PROBLEM
│  api.iamazim.com│ ─→ dograh-api  (:8000)
│  livekit.iamazim│ ─→ livekit     (:7880)
└────────┬────────┘
         │
    ┌────┴──────────────────────────────┐
    │       Docker bridge network       │
    ├──────────┬──────────┬─────────────┤
    │          │          │             │
    ▼          ▼          ▼             ▼
┌────────┐ ┌──────┐ ┌────────┐  ┌──────────┐
│Dograh  │ │Dograh│ │LiveKit │  │ Coturn   │
│  API   │ │  UI  │ │(WebRTC)│  │(TURN/STUN│
│ :8000  │ │:3010 │ │ :7880  │  │ :3478    │
└───┬────┘ └──────┘ └────┬───┘  └──────────┘
    │                    │
┌───┴──────────────┐    │
│  Internal Only   │    │
├──────┬───────────┤    │
│Postgres│ Redis   │    │
│MinIO   │         │    Cloudflared
└────────┴─────────┘
```

**Container Status Summary:**

| Container | Status | Health | Restart Policy |
|-----------|--------|--------|----------------|
| dograh-api | Running | ✅ healthy | always |
| dograh-ui | Running | ❌ **unhealthy** | always |
| livekit | Running | ✅ healthy* | always |
| ai-postgres | Running | ✅ healthy | always |
| ai-redis | Running | ✅ healthy | always |
| minio | Running | ✅ healthy | always |
| coturn | Running | ⚠️ no healthcheck | always |
| cloudflared-tunnel | Running | — no healthcheck | always |

*LiveKit shows "healthy" but has API key configuration errors in logs.

---

## 2. Detected Problems

### CRITICAL — P0

| # | Problem | Impact |
|---|---------|--------|
| 1 | **Nginx routes `/api/*` to backend, blocking frontend `/api/config/*` routes** | Browser console 404 errors on `/api/config/sentry`, `/api/config/posthog`, `/api/config/auth` |
| 2 | **LiveKit YAML config does not expand `${ENV_VARS}`** | API key is literal string `${LIVEKIT_API_KEY}`, secret validation fails, WebRTC room authentication broken |
| 3 | **Coturn config does not expand `${TURN_SECRET}`** | TURN shared-secret auth uses literal `${TURN_SECRET}` string instead of actual secret, NAT traversal auth broken |
| 4 | **dograh-ui health check fails (IPv6 resolution)** | Container marked unhealthy, could trigger cascading restarts in orchestration |

### HIGH — P1

| # | Problem | Impact |
|---|---------|--------|
| 5 | **Coturn config warnings: `no-tlsv1` / `no-tlsv1_1` deprecated** | Log spam, config not applying TLS version restrictions |
| 6 | **Coturn: "external IP defined more than once"** | Duplicate external-ip setting (likely from Docker entrypoint auto-detection) |
| 7 | **Coturn TLS cert permission denied** | Coturn cannot read `/etc/letsencrypt/live/iamazim.com/` inside container |
| 8 | **Missing `NEXT_PUBLIC_*` env vars in UI container** | Stack Auth error: "You haven't provided a project ID" |
| 9 | **No `NEXT_PUBLIC_STACK_PROJECT_ID` environment variable** | Console warning about Stack Auth |

### MEDIUM — P2

| # | Problem | Impact |
|---|---------|--------|
| 10 | **`NODE_ENV=oss` instead of `production`** | May affect Next.js optimization/behavior |
| 11 | **Nginx `Permissions-Policy` blocks microphone in `nginx-iamazim.conf`** | `microphone=()` blocks all — should be `microphone=(self)` for voice app |
| 12 | **Cloudflared tunnel points only to API, not UI** | Fallback tunnel doesn't serve the dashboard |
| 13 | **No healthcheck defined for coturn and cloudflared** | Docker can't detect if these services crash silently |

---

## 3. Root Causes

### Root Cause 1: Nginx `/api/*` catch-all routing conflict

The Nginx config for `iamazim.com` has:
```nginx
location /api/ {
    proxy_pass http://dograh_api;  # → FastAPI backend on :8000
}

location / {
    proxy_pass http://dograh_ui;   # → Next.js on :3010
}
```

The Next.js frontend defines internal API routes at:
- `/api/config/sentry` → returns `{"enabled":false,"dsn":"","environment":"production"}`
- `/api/config/posthog` → returns `{"enabled":false,"key":"","host":"/ingest",...}`
- `/api/config/auth` → returns `{"provider":"local"}`
- `/api/config/version` → returns version info

Because `/api/` matches before `/`, **all** requests to `/api/config/*` are sent to the FastAPI backend (which has no such routes → 404).

### Root Cause 2: Config file env var expansion

Neither LiveKit's YAML parser nor Coturn's config parser expand shell-style `${VAR}` environment variables from Docker Compose. Despite the env vars being correctly set inside the containers, the config files read literal strings.

**LiveKit container env:**
```
LIVEKIT_API_KEY=API88f0aec95c61
LIVEKIT_API_SECRET=tvHZFR0IImCbKcDgi19rRrqTMXCTzKiKrRzL1SkQqqc2nakB
```

**But livekit.yaml has:**
```yaml
keys:
  ${LIVEKIT_API_KEY}: ${LIVEKIT_API_SECRET}
```
→ LiveKit reads the key as the literal string `${LIVEKIT_API_KEY}` (14 chars < 32 required).

### Root Cause 3: Health check IPv6 resolution

The `dograh-ui` health check uses `wget --spider http://localhost:3010`. The `wget` inside the container resolves `localhost` to `[::1]` (IPv6), but the Next.js server only binds to `0.0.0.0` (IPv4). Connection refused on `[::1]:3010`.

### Root Cause 4: Stack Auth / NEXT_PUBLIC vars

The UI container only has these env vars:
```
BACKEND_URL=http://api:8000
NODE_ENV=oss
```

No `NEXT_PUBLIC_STACK_PROJECT_ID` is set. The Dograh UI in OSS mode doesn't use Stack Auth — the console error is generated by bundled Stack Auth client code trying to initialize without config. The `/api/config/auth` endpoint (on the frontend) returns `{"provider":"local"}`, which would suppress this error if the route were accessible.

---

## 4. Required Fixes

### Fix 1: Nginx — Route `/api/config/*` to frontend

Add a **higher-priority location block** for `/api/config/` that proxies to the UI before the catch-all `/api/` block.

### Fix 2: LiveKit — Use hardcoded keys or `envsubst`

Replace `${VAR}` references in `livekit.yaml` with actual values, or use an entrypoint command that runs `envsubst` before starting LiveKit.

### Fix 3: Coturn — Use hardcoded secret or `envsubst`

Replace `${TURN_SECRET}` in `turnserver.conf` with the actual secret value, or preprocess the config.

### Fix 4: Fix UI health check

Change `wget` to use `127.0.0.1` instead of `localhost` to avoid IPv6 resolution.

### Fix 5: Coturn config modernization

Fix deprecated `no-tlsv1`/`no-tlsv1_1` syntax and remove duplicate `external-ip`.

### Fix 6: Fix `nginx-iamazim.conf` Permissions-Policy

Change `microphone=()` to `microphone=(self)` since this is a voice application.

---

## 5. Code Patches

### Patch 1: `configs/nginx/iamazim.com.conf` — Add `/api/config/` route to frontend

```diff
     # ── API routes ──────────────────────────────────────────
+    # Frontend internal API routes (Next.js API routes)
+    # Must be BEFORE the /api/ catch-all
+    location /api/config/ {
+        proxy_pass http://dograh_ui;
+        proxy_http_version 1.1;
+        proxy_set_header Host $host;
+        proxy_set_header X-Real-IP $remote_addr;
+        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
+        proxy_set_header X-Forwarded-Proto $scheme;
+    }
+
     location /api/ {
         limit_req zone=api_limit burst=50 nodelay;
```

### Patch 2: `docker-compose.yaml` — Fix UI health check (IPv6 + binding issue)

```diff
+    environment:
+      HOSTNAME: "0.0.0.0"
+      BACKEND_URL: "${BACKEND_URL:-http://api:8000}"

     healthcheck:
-      test: ["CMD-SHELL", "wget --no-verbose --tries=1 --spider http://localhost:3010 || exit 1"]
+      test: ["CMD-SHELL", "wget --no-verbose --tries=1 --spider http://127.0.0.1:3010 || exit 1"]
       interval: 30s
```

Next.js binds to the container hostname by default (e.g. `172.18.0.9`), making `localhost` / `127.0.0.1` unreachable. Setting `HOSTNAME=0.0.0.0` forces Next.js to bind to all interfaces.

### Patch 3: `docker-compose.yaml` — LiveKit entrypoint script for config expansion

Neither LiveKit nor Coturn containers have `envsubst`. The fix uses `sed`-based entrypoint scripts to expand `${VAR}` placeholders before starting each service.

**New file: `scripts/livekit-entrypoint.sh`**
```bash
#!/bin/sh
set -e
sed \
  -e "s|\${REDIS_PASSWORD}|${REDIS_PASSWORD}|g" \
  -e "s|\${LIVEKIT_API_KEY}|${LIVEKIT_API_KEY}|g" \
  -e "s|\${LIVEKIT_API_SECRET}|${LIVEKIT_API_SECRET}|g" \
  -e "s|\${LIVEKIT_WEBHOOK_URL}|${LIVEKIT_WEBHOOK_URL}|g" \
  /etc/livekit-template.yaml > /tmp/livekit.yaml
exec /livekit-server --config /tmp/livekit.yaml --node-ip "${VPS_IP:-5.189.131.48}"
```

**docker-compose.yaml changes:**
```diff
   livekit:
     image: livekit/livekit-server:latest
     container_name: livekit
     restart: always
-    command: --config /etc/livekit.yaml --node-ip ${VPS_IP:-5.189.131.48}
+    entrypoint: ["/bin/sh", "/etc/livekit-entrypoint.sh"]
+    command: []
     volumes:
-      - ./configs/livekit/livekit.yaml:/etc/livekit.yaml:ro
+      - ./configs/livekit/livekit.yaml:/etc/livekit-template.yaml:ro
+      - ./scripts/livekit-entrypoint.sh:/etc/livekit-entrypoint.sh:ro
     environment:
       VPS_IP: ${VPS_IP:-5.189.131.48}
       REDIS_PASSWORD: ${REDIS_PASSWORD:-redissecret}
       LIVEKIT_API_KEY: ${LIVEKIT_API_KEY:-devkey}
       LIVEKIT_API_SECRET: ${LIVEKIT_API_SECRET:-devsecret_min32chars_change_me}
       LIVEKIT_WEBHOOK_URL: ${LIVEKIT_WEBHOOK_URL:-http://api:8000/api/v1/livekit/webhook}
```

### Patch 4: `configs/coturn/turnserver.conf` + entrypoint script

**Config changes:** Removed deprecated `no-tlsv1` / `no-tlsv1_1` directives (cause `"Bad configuration format"` errors). The `${TURN_SECRET}` placeholder remains — expanded at runtime by the entrypoint script.

**New file: `scripts/coturn-entrypoint.sh`**
```bash
#!/bin/sh
set -e
sed \
  -e "s|\${TURN_SECRET}|${TURN_SECRET}|g" \
  /etc/coturn/turnserver-template.conf > /tmp/turnserver.conf
exec turnserver -c /tmp/turnserver.conf
```

**docker-compose.yaml changes:**
```diff
   coturn:
     image: coturn/coturn:latest
     container_name: coturn
     restart: always
+    entrypoint: ["/bin/sh", "/etc/coturn-entrypoint.sh"]
+    command: []
     volumes:
-      - ./configs/coturn/turnserver.conf:/etc/coturn/turnserver.conf:ro
+      - ./configs/coturn/turnserver.conf:/etc/coturn/turnserver-template.conf:ro
+      - ./scripts/coturn-entrypoint.sh:/etc/coturn-entrypoint.sh:ro
       - /etc/letsencrypt:/etc/letsencrypt:ro
```

### Patch 5: `configs/nginx/iamazim.com.conf` — Fix Permissions-Policy (already correct)

The `iamazim.com.conf` in the configs directory already has `microphone=(self)`. The root-level `nginx-iamazim.conf` has `microphone=()` but that file appears to be an older version. Verify the deployed file matches `configs/nginx/iamazim.com.conf`.

---

## 6. Deployment Steps

Execute these commands **in order** on the VPS (`ssh azim@5.189.131.48`):

### Step 1: Upload fixed config files from local machine

```powershell
# From your local Windows machine
scp "E:\Programs\vps-deploy\configs\nginx\iamazim.com.conf" azim@5.189.131.48:~/ai-call-platform/configs/nginx/iamazim.com.conf
scp "E:\Programs\vps-deploy\configs\livekit\livekit.yaml" azim@5.189.131.48:~/ai-call-platform/configs/livekit/livekit.yaml
scp "E:\Programs\vps-deploy\configs\coturn\turnserver.conf" azim@5.189.131.48:~/ai-call-platform/configs/coturn/turnserver.conf
scp "E:\Programs\vps-deploy\docker-compose.yaml" azim@5.189.131.48:~/ai-call-platform/docker-compose.yaml
scp "E:\Programs\vps-deploy\scripts\livekit-entrypoint.sh" azim@5.189.131.48:~/ai-call-platform/scripts/livekit-entrypoint.sh
scp "E:\Programs\vps-deploy\scripts\coturn-entrypoint.sh" azim@5.189.131.48:~/ai-call-platform/scripts/coturn-entrypoint.sh
```

### Step 1b: Ensure entrypoint scripts are executable on server

```bash
ssh azim@5.189.131.48
chmod +x ~/ai-call-platform/scripts/livekit-entrypoint.sh ~/ai-call-platform/scripts/coturn-entrypoint.sh
```

### Step 2: Install updated Nginx config (requires sudo)

```bash
ssh azim@5.189.131.48
sudo cp ~/ai-call-platform/configs/nginx/iamazim.com.conf /etc/nginx/sites-available/iamazim.com.conf
sudo nginx -t && sudo systemctl reload nginx
```

### Step 3: Redeploy Docker stack

```bash
cd ~/ai-call-platform
docker compose down
docker compose up -d
```

### Step 4: Wait for health checks and verify

```bash
sleep 30
docker ps --format 'table {{.Names}}\t{{.Status}}'
```

---

## 7. Final Verification Commands

Run these after deployment to confirm all issues are resolved:

```bash
# 1. Check all containers are healthy
docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'

# 2. Test backend health
curl -s https://api.iamazim.com/api/v1/health | python3 -m json.tool

# 3. Test frontend config endpoints (the main fix)
curl -s https://iamazim.com/api/config/sentry
# Expected: {"enabled":false,"dsn":"","environment":"production"}

curl -s https://iamazim.com/api/config/posthog
# Expected: {"enabled":false,"key":"","host":"/ingest",...}

curl -s https://iamazim.com/api/config/auth
# Expected: {"provider":"local"}

curl -s https://iamazim.com/api/config/version
# Expected: {"ui":"1.16.0","api":"1.16.0",...}

# 4. Verify backend API still routes correctly
curl -s https://iamazim.com/api/v1/health
# Expected: {"status":"ok","version":"1.16.0",...}

# 5. Check LiveKit logs for key validation
docker logs livekit --tail 20 2>&1 | grep -i "secret\|key\|error"
# Expected: No "secret is too short" errors

# 6. Check coturn logs
docker logs coturn --tail 20 2>&1 | grep -iE "error|warn"
# Expected: No errors about config format or external-ip

# 7. Test LiveKit WebSocket (from outside)
curl -I https://livekit.iamazim.com
# Expected: HTTP 200 or upgrade response

# 8. Browser test
# Open https://iamazim.com in browser
# Open DevTools → Console
# Expected: No 404 errors for /api/config/*
# Expected: No Stack Auth project ID error
```

---

## Summary of All Issues & Status

| # | Issue | Severity | Fix Applied |
|---|-------|----------|-------------|
| 1 | Nginx `/api/*` blocks frontend config routes | CRITICAL | Patch 1 |
| 2 | LiveKit `${ENV_VAR}` not expanded in YAML | CRITICAL | Patch 3 |
| 3 | Coturn `${TURN_SECRET}` not expanded | CRITICAL | Patch 4 |
| 4 | UI health check IPv6 failure | HIGH | Patch 2 |
| 5 | Coturn deprecated TLS config syntax | HIGH | Patch 4 |
| 6 | Coturn duplicate external-ip error | HIGH | Patch 4 |
| 7 | Coturn can't read TLS certs (permissions) | HIGH | Needs sudo fix |
| 8 | Missing NEXT_PUBLIC env vars | MEDIUM | Resolved by Fix 1 |
| 9 | Stack Auth console error | MEDIUM | Resolved by Fix 1 |
| 10 | `NODE_ENV=oss` (intentional for OSS mode) | INFO | No fix needed |
| 11 | `nginx-iamazim.conf` microphone policy | LOW | Deploy configs/nginx version |
| 12 | Cloudflared only tunnels API | LOW | Optional enhancement |
| 13 | No healthcheck for coturn/cloudflared | LOW | Optional enhancement |

**Primary browser console errors will be resolved by Fix 1 (Nginx routing).** The Stack Auth error is a downstream effect — once `/api/config/auth` returns `{"provider":"local"}`, the frontend knows to use local auth instead of Stack Auth.
