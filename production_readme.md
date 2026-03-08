# ============================================================
# Production Deployment Guide — AI Voice Agent SaaS Platform
# Domain: iamazim.com | VPS: 5.189.131.48
# ============================================================

## Architecture Overview

```
Internet (Caller / Browser)
        │
   ┌────┴────┐
   │ Twilio  │ (Phone calls via SIP)
   └────┬────┘
        │
        ▼
┌──────────────────────┐
│  Nginx (SSL)         │  ← Ports 80/443
│  Reverse Proxy       │
│                      │
│  iamazim.com         │ → Dograh UI (:3010)
│  api.iamazim.com     │ → Dograh API (:8000)
│  livekit.iamazim.com │ → LiveKit (:7880)
│  fazle.iamazim.com   │ → Fazle UI (:3020) + API (:8100)
└──────────┬───────────┘
           │
    ┌──────┴──────────────────────────────┐
    │           Docker Network            │
    ├──────────┬──────────┬───────────────┤
    │          │          │               │
    ▼          ▼          ▼               ▼
┌────────┐ ┌──────┐ ┌────────┐    ┌──────────┐
│Dograh  │ │Dograh│ │LiveKit │    │ Coturn   │
│  API   │ │  UI  │ │(WebRTC)│    │(TURN/STUN│
│ :8000  │ │:3010 │ │ :7880  │    │ :3478    │
└───┬────┘ └──────┘ └────────┘    └──────────┘
    │
    │  POST /fazle/decision
    ▼
┌──────────────────────────────────────────┐
│  Fazle Personal AI System                │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐  │
│  │ API GW   │ │ Brain    │ │ Memory   │  │
│  │ :8100    │ │ :8200    │ │ :8300    │  │
│  ├──────────┤ ├──────────┤ ├──────────┤  │
│  │ Tasks    │ │ Web Intel│ │ Trainer  │  │
│  │ :8400    │ │ :8500    │ │ :8600    │  │
│  ├──────────┤ ├──────────┤ ├──────────┤  │
│  │ Fazle UI │ │ Qdrant   │ │ Ollama   │  │
│  │ :3020    │ │ :6333    │ │ :11434   │  │
│  └──────────┘ └──────────┘ └──────────┘  │
└──────────────────────────────────────────┘
    │
┌───┴──────────────────┐
│   Internal Services  │
├──────────┬───────────┤
│PostgreSQL│   Redis   │
│(pgvector)│   MinIO   │
└──────────┴───────────┘
```

## Real-Time Call Flow

```
Phone Call → Twilio → Dograh API → LiveKit (audio stream)
                                       │
                                   ┌───┴───┐
                                   │  STT  │ (Speech-to-Text)
                                   └───┬───┘
                                       │
                                   ┌───┴───┐
                                   │  LLM  │ (AI Processing)
                                   └───┬───┘
                                       │
                                   ┌───┴───┐
                                   │  TTS  │ (Text-to-Speech)
                                   └───┬───┘
                                       │
                                Voice response → back to caller
```

## Services

| Service    | Container     | Internal Port | Exposed                  |
|------------|---------------|---------------|--------------------------|
| Dograh API | dograh-api    | 8000          | 127.0.0.1:8000 → Nginx  |
| Dograh UI  | dograh-ui     | 3010          | 127.0.0.1:3010 → Nginx  |
| LiveKit    | livekit       | 7880          | 127.0.0.1:7880 → Nginx  |
| LiveKit RTC| livekit       | 7881          | 0.0.0.0:7881 (direct)   |
| Coturn     | coturn        | 3478/5349     | 0.0.0.0:3478,5349       |
| PostgreSQL | ai-postgres   | 5432          | Internal only            |
| Redis      | ai-redis      | 6379          | Internal only            |
| MinIO      | minio         | 9000/9001     | Internal only            |
| Cloudflared| cloudflared   | —             | Tunnel to Cloudflare     |
| Fazle API  | fazle-api     | 8100          | 127.0.0.1:8100 → Nginx  |
| Fazle Brain| fazle-brain   | 8200          | Internal only            |
| Fazle Memory| fazle-memory | 8300          | Internal only            |
| Fazle Tasks| fazle-task-engine | 8400      | Internal only            |
| Fazle WebIntel| fazle-web-intelligence | 8500 | Internal only         |
| Fazle Trainer| fazle-trainer | 8600        | Internal only            |
| Fazle UI   | fazle-ui      | 3020          | 127.0.0.1:3020 → Nginx  |
| Qdrant     | qdrant        | 6333          | Internal only            |
| Ollama     | ollama        | 11434         | Internal only            |
| Prometheus | prometheus    | 9090          | Internal only            |
| Grafana    | grafana       | 3000          | 127.0.0.1:3030 → Nginx  |
| Node Exporter | node-exporter | 9100      | Internal only            |
| cAdvisor   | cadvisor      | 8080          | Internal only            |
| Loki       | loki          | 3100          | Internal only            |
| Promtail   | promtail      | 9080          | Internal only            |

## Access Points

| Service        | URL                                    |
|----------------|----------------------------------------|
| Dashboard (UI) | https://iamazim.com                    |
| API (direct)   | https://api.iamazim.com/api/v1/health  |
| API (via main) | https://iamazim.com/api/               |
| LiveKit WS     | wss://livekit.iamazim.com              |
| TURN Server    | turn:turn.iamazim.com:3478             |
| Fazle UI       | https://fazle.iamazim.com              |
| Fazle API      | https://fazle.iamazim.com/api/fazle/   |
| Fazle API Docs | https://fazle.iamazim.com/docs         |
| Grafana        | https://iamazim.com/grafana/           |

---

## Deployment Guide

### Prerequisites

- Ubuntu VPS with Docker + Docker Compose V2
- DNS A records pointing to 5.189.131.48:
  - `iamazim.com`
  - `api.iamazim.com`
  - `livekit.iamazim.com`
  - `turn.iamazim.com`
  - `fazle.iamazim.com`

### Step 1: Upload Files to VPS

```bash
# From your local machine
scp -r . azim@5.189.131.48:/home/azim/ai-call-platform/
```

### Step 2: Configure Environment

```bash
ssh azim@5.189.131.48
cd /home/azim/ai-call-platform

# Create .env from template
cp .env.example .env

# Edit with real secrets
nano .env
```

**Required values in .env:**
- `POSTGRES_PASSWORD` — strong database password
- `REDIS_PASSWORD` — strong Redis password
- `MINIO_SECRET_KEY` — strong MinIO password
- `OSS_JWT_SECRET` — 32+ char JWT secret
- `LIVEKIT_API_KEY` — LiveKit API key (generate any string)
- `LIVEKIT_API_SECRET` — LiveKit secret (32+ chars)
- `TURN_SECRET` — shared TURN auth secret

### Step 3: Setup SSL Certificates

```bash
bash scripts/setup-ssl.sh admin@iamazim.com
```

### Step 4: Configure Firewall

```bash
bash scripts/setup-firewall.sh
```

### Step 5: Install Nginx Configs

```bash
# Copy Nginx configs
cp configs/nginx/iamazim.com.conf /etc/nginx/sites-available/
cp configs/nginx/api.iamazim.com.conf /etc/nginx/sites-available/
cp configs/nginx/livekit.iamazim.com.conf /etc/nginx/sites-available/
cp configs/nginx/fazle.iamazim.com.conf /etc/nginx/sites-available/

# Enable sites
ln -sf /etc/nginx/sites-available/iamazim.com.conf /etc/nginx/sites-enabled/
ln -sf /etc/nginx/sites-available/api.iamazim.com.conf /etc/nginx/sites-enabled/
ln -sf /etc/nginx/sites-available/livekit.iamazim.com.conf /etc/nginx/sites-enabled/
ln -sf /etc/nginx/sites-available/fazle.iamazim.com.conf /etc/nginx/sites-enabled/

# Remove old config if exists
rm -f /etc/nginx/sites-enabled/nginx-iamazim.conf

# Test and reload
nginx -t && systemctl reload nginx
```

### Step 6: Deploy Stack

```bash
bash scripts/deploy.sh
```

### Step 7: Verify

```bash
bash scripts/health-check.sh
```

---

## First-Time Platform Setup

### 1. Open Dashboard
- Go to https://iamazim.com
- Create admin account

### 2. Configure API Keys (Dashboard → Settings)
- **OpenAI API Key** — for LLM responses
- **Twilio credentials** — Account SID + Auth Token
- **ElevenLabs** (optional) — for voice cloning TTS

### 3. Configure LiveKit (Dashboard → Settings → Voice)
- LiveKit URL: `wss://livekit.iamazim.com`
- API Key: (from your .env `LIVEKIT_API_KEY`)
- API Secret: (from your .env `LIVEKIT_API_SECRET`)

### 4. Create AI Agent
1. Click "New Agent" → "Inbound"
2. Paste content from `personality/personality.md` as system prompt
3. Select LLM: GPT-4o / GPT-4o-mini
4. Select TTS: Deepgram / ElevenLabs
5. Select STT: Deepgram
6. Save and test with "Web Call"

### 5. Connect Twilio Phone Number
1. Dashboard → Settings → Telephony → Add Twilio
2. Enter Account SID + Auth Token
3. Purchase/assign phone number
4. Dograh auto-configures the webhook

---

## Management Commands

```bash
cd /home/azim/ai-call-platform

# ── Deploy & Status ────────────────────────────────────────
bash scripts/deploy.sh              # Full deploy
bash scripts/deploy.sh status       # Service status + resource usage
bash scripts/deploy.sh restart      # Restart all services
bash scripts/deploy.sh update fazle # Rolling update Fazle only
bash scripts/deploy.sh update monitoring  # Update monitoring stack
bash scripts/deploy.sh update fazle-brain # Update single service
bash scripts/deploy.sh logs         # Tail all logs
bash scripts/deploy.sh logs fazle-api  # Tail specific service

# ── Monitoring & Logs ──────────────────────────────────────
# Grafana dashboards (change admin password on first login!)
# URL: https://iamazim.com/grafana/
# Default: admin / admin

# View container resource usage
docker stats --no-stream

# ── Backups (auto-scheduled via cron) ──────────────────────
bash scripts/backup.sh              # Manual backup
# Setup daily cron: add to crontab
# 0 2 * * * /home/azim/ai-call-platform/scripts/backup.sh >> /var/log/backup.log 2>&1

# ── Health check ───────────────────────────────────────────
bash scripts/health-check.sh

# ── SSL certificates ──────────────────────────────────────
certbot certificates
```

## Network Architecture

```
┌──────────────────────────────────────────────────────┐
│ app-network (bridge)                                 │
│   Nginx → Dograh API, Dograh UI, Fazle API, Fazle UI│
│   LiveKit, Coturn, Cloudflared, Task Engine          │
├──────────────────────────────────────────────────────┤
│ db-network (internal)                                │
│   PostgreSQL, Redis, MinIO, Qdrant                   │
│   Dograh API, LiveKit, Fazle Brain, Fazle Memory     │
├──────────────────────────────────────────────────────┤
│ ai-network (internal)                                │
│   Ollama, Fazle Brain, Fazle Memory, Fazle API       │
│   Fazle Tasks, Fazle Web Intel, Fazle Trainer        │
├──────────────────────────────────────────────────────┤
│ monitoring-network (internal)                        │
│   Prometheus, Grafana, Node Exporter, cAdvisor       │
│   Loki, Promtail                                     │
└──────────────────────────────────────────────────────┘
```

## Resource Limits

| Service          | CPU  | Memory | Reserved |
|------------------|------|--------|----------|
| PostgreSQL       | 2    | 2 GB   | 512 MB   |
| Redis            | 1    | 768 MB | 256 MB   |
| MinIO            | 1    | 1 GB   | 256 MB   |
| LiveKit          | 2    | 1 GB   | 256 MB   |
| Coturn           | 1    | 512 MB | 128 MB   |
| Ollama           | 4    | 6 GB   | 2 GB     |
| Qdrant           | 1    | 1 GB   | 256 MB   |
| Fazle Brain      | 2    | 1 GB   | 256 MB   |
| Fazle API        | 1    | 512 MB | 128 MB   |
| Fazle Memory     | 1    | 512 MB | 128 MB   |
| Fazle Tasks      | 0.5  | 512 MB | 128 MB   |
| Fazle Web Intel  | 0.5  | 512 MB | 128 MB   |
| Fazle Trainer    | 1    | 512 MB | 128 MB   |
| Fazle UI         | 0.5  | 256 MB | 128 MB   |
| Prometheus       | 0.5  | 512 MB | 256 MB   |
| Grafana          | 0.5  | 256 MB | 128 MB   |
| Loki             | 0.5  | 512 MB | 256 MB   |

## File Structure

```
/home/azim/ai-call-platform/
├── docker-compose.yaml          # Main orchestration (all services)
├── .env                         # Secrets (never commit)
├── .env.example                 # Template
├── personality/
│   └── personality.md           # AI personality blueprint
├── configs/
│   ├── nginx/
│   │   ├── iamazim.com.conf     # Main domain + Grafana proxy
│   │   ├── api.iamazim.com.conf # API subdomain
│   │   ├── livekit.iamazim.com.conf  # LiveKit subdomain
│   │   └── fazle.iamazim.com.conf    # Fazle AI subdomain
│   ├── livekit/
│   │   └── livekit.yaml         # LiveKit config (latency-tuned)
│   ├── coturn/
│   │   └── turnserver.conf      # TURN server config
│   ├── prometheus/
│   │   └── prometheus.yml       # Prometheus scrape targets
│   ├── grafana/
│   │   └── provisioning/
│   │       └── datasources/
│   │           └── datasources.yml  # Auto-provision Prometheus + Loki
│   ├── loki/
│   │   └── loki.yml             # Log aggregation config (14d retention)
│   └── promtail/
│       └── promtail.yml         # Docker log shipper config
├── scripts/
│   ├── deploy.sh                # Full deploy + status/update/logs/restart
│   ├── rollback.sh              # Rollback to previous version
│   ├── backup.sh                # Full backup (Postgres+Qdrant+Redis+MinIO+configs)
│   ├── health-check.sh          # Health monitoring
│   ├── setup-ssl.sh             # SSL certificate setup
│   └── setup-firewall.sh        # UFW firewall rules
├── fazle-system/                    # Fazle Personal AI System
│   ├── api/                         # API gateway service
│   ├── brain/                       # Reasoning engine
│   ├── memory/                      # Vector memory (Qdrant)
│   ├── tasks/                       # Task scheduler
│   ├── tools/                       # Web intelligence + plugins
│   ├── trainer/                     # Knowledge extraction
│   ├── ui/                          # Next.js dashboard
│   ├── .env.example                 # Fazle env template
│   └── README.md                    # Fazle documentation
└── production_readme.md             # This file
```

## Security Checklist

- [x] UFW firewall: only SSH, HTTP, HTTPS, RTC, TURN ports open
- [x] PostgreSQL: no public port, isolated on `db-network`
- [x] Redis: no public port, password required, memory-limited (512MB)
- [x] MinIO: no public port, isolated on `db-network`
- [x] API/UI: bound to 127.0.0.1 only (Nginx fronted)
- [x] LiveKit HTTP: bound to 127.0.0.1 (Nginx fronted)
- [x] HTTPS enforced with HSTS
- [x] Security headers on all domains
- [x] Rate limiting on API endpoints
- [x] TURN server uses shared-secret auth
- [x] Log rotation on all containers
- [x] Docker restart policies set
- [x] .env file kept secure (never shared)
- [x] Fazle services: internal-only (no public ports except via Nginx)
- [x] Fazle API: optional API key authentication
- [x] Qdrant: no public port, isolated on `db-network`
- [x] Ollama: no public port, isolated on `ai-network`
- [x] Network segmentation: db-network, ai-network, monitoring-network (all internal)
- [x] Resource limits on all containers (prevents resource exhaustion)
- [x] Grafana: IP-restricted access via Nginx
- [x] Monitoring stack: isolated on internal network only
- [x] Centralized logging with 14-day retention

## Troubleshooting

### LiveKit not connecting
```bash
# Check LiveKit logs
docker logs livekit --tail 50

# Verify port 7881 is reachable
ss -tlnp | grep 7881

# Test WebSocket from outside
curl -i https://livekit.iamazim.com
```

### TURN server issues
```bash
# Check coturn logs
docker logs coturn --tail 50

# Test STUN
stun turn.iamazim.com:3478

# Verify certificates
openssl s_client -connect turn.iamazim.com:5349
```

### Call quality problems
- Check API response time: `curl -w "%{time_total}" https://api.iamazim.com/api/v1/health`
- Check LiveKit connectivity: Browser DevTools → Network → WS tab
- Check TURN relay: LiveKit dashboard → Room details
- Monitor resources: `docker stats --no-stream`

---

## Manual Deployment

### How to Deploy

1. SSH into the VPS:
   ```bash
   ssh azim@5.189.131.48
   ```

2. Navigate to the project directory:
   ```bash
   cd /home/azim/ai-call-platform
   ```

3. Upload updated files from your local machine (run from your PC):
   ```bash
   scp -r . azim@5.189.131.48:/home/azim/ai-call-platform/
   ```

4. Deploy the stack:
   ```bash
   bash scripts/deploy.sh
   ```

   Or manually:
   ```bash
   docker compose up -d --build
   ```

5. Verify health:
   ```bash
   bash scripts/health-check.sh
   ```

### Rollback

```bash
ssh azim@5.189.131.48
cd /home/azim/ai-call-platform
bash scripts/rollback.sh
```

### Deploy Logs

```bash
ls -lt /home/azim/ai-call-platform/logs/deploy-*.log | head -5
```

### What Gets Rebuilt

`docker compose up -d` only recreates containers whose:
- Image has changed (pulled or rebuilt)
- Configuration has changed in `docker-compose.yaml`
- Environment variables have changed

Unchanged containers continue running without interruption.
Docker volumes are **always preserved** across deployments.
