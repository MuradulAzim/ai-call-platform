# WBOM — WhatsApp Business Operations Manager

> **Sprint-6 — Production Ready** | Version `wbom-v1.6.0`

WBOM is an internal FastAPI microservice (port 9900) that manages the core business operations for a seafarer placement agency: payroll, client complaints, WhatsApp recruitment funnel, employee management, and financial reporting.

---

## Architecture

```
                Next.js Frontend (port 3000)
                       │  (X-INTERNAL-KEY header)
                       ▼
              FastAPI (wbom) — port 9900
                       │
              PostgreSQL (wbom_* tables)
              Redis (session cache)
```

All routes are protected by `InternalAuthMiddleware`. Only the frontend server (same Docker network) can reach the API — it is **never** exposed directly to the internet.

---

## Quick Start (Docker)

```bash
# From repo root
cp fazle-system/wbom/.env.example .env   # fill in values
docker compose -f fazle-ai/docker-compose.yaml --env-file .env up -d fazle-wbom
curl http://localhost:9900/health         # → {"status":"ok","db_ok":true,...}
```

---

## Configuration

All config lives in `.env` (root of repo). See `wbom/.env.example` for the full list.

| Variable | Required | Notes |
|---|---|---|
| `WBOM_DATABASE_URL` | ✅ | PostgreSQL DSN |
| `WBOM_INTERNAL_KEY` | ✅ | Shared secret for internal auth |
| `WBOM_WHATSAPP_TOKEN` | Required for WhatsApp | Meta Cloud API token |
| `WBOM_WHATSAPP_PHONE_ID` | Required for WhatsApp | Sender phone ID |
| `WBOM_CORE_BASE_URL` | Required | URL of fazle-core service |
| `WBOM_PORT` | Optional | Default: `9900` |
| `WBOM_LOG_LEVEL` | Optional | Default: `INFO` |

---

## Key Endpoints

### System

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | DB-checked health (returns `{"db_ok": true/false}`) |
| `GET` | `/ready` | 503 when DB unreachable — used by load balancers |
| `GET` | `/version` | Current version and build date |
| `GET` | `/metrics` | Prometheus metrics |

### Business APIs (all prefixed `/api/wbom/`)

| Domain | Path | Notes |
|---|---|---|
| Payroll | `/payroll` | Canonical: `wbom_payroll_runs` |
| Payroll action | `/payroll/{id}/approve` `/{id}/pay` | Triggers audit event log |
| Complaints | `/complaints` | SLA-tracked, priority queued |
| Recruitment | `/recruitment/candidates` | WhatsApp funnel with scoring |
| Dashboard | `/dashboard/summary` | KPI summary for UI |
| Employees | `/employees` | Staff roster |
| Clients | `/clients` | Client accounts |
| Transactions | `/transactions` | Cash flow ledger |
| Audit | `/audit` | Immutable audit trail |

---

## Data Sources

See [WBOM_SOURCE_OF_TRUTH.md](WBOM_SOURCE_OF_TRUTH.md) for the canonical table per domain.

**Deprecated APIs** (sunset 2026-07-01):
- `GET /api/wbom/salary` — use `/api/wbom/payroll` instead

---

## Logging

All logs are JSON-structured (`setup_structured_logging("wbom")`). Business-critical events are emitted via `services/audit_events.py`:

- `payroll.approved` / `payroll.paid`
- `complaint.created` / `complaint.sla_breach` / `complaint.resolved`
- `candidate.converted` / `candidate.hired`
- `whatsapp.dispatch_ok` / `whatsapp.dispatch_failed`
- `report.sent` / `admin.action`

---

## Backup & Restore

```bash
# Backup (run from repo root; stores to backups/wbom_YYYYMMDD_HHMMSS.sql.gz)
bash fazle-system/wbom/scripts/backup.sh

# Restore
bash fazle-system/wbom/scripts/restore.sh backups/wbom_20260421_120000.sql.gz
```

---

## Deploy

```bash
# Full deploy (backup → test → build → restart → health check)
bash fazle-system/wbom/scripts/deploy.sh

# Skip tests (e.g. hotfix)
bash fazle-system/wbom/scripts/deploy.sh --skip-tests
```

Rollback: the script auto-restarts the container if the health check fails. For a hard rollback, use `git checkout` to the previous tag and redeploy.

---

## Tests

```bash
cd fazle-system/wbom
python -m pytest tests/ -v
```

Test coverage includes: payroll engine, complaint ingestion, dashboard summary, recruitment funnel, audit trail, SLA computation, error handling, and integration smoke tests.

---

## Sprint History

| Tag | Description |
|---|---|
| `wbom-v1.1-sprint1-payroll-stable` | Payroll engine (45 tests) |
| `wbom-v1.2-sprint2-dashboard-stable` | Owner dashboard + reports (60 tests) |
| `wbom-v1.3-sprint3-recruitment-stable` | WhatsApp recruiting funnel (84 tests) |
| `wbom-v1.4-sprint4-complaints-stable` | Complaint + client retention (124 tests) |
| `wbom-v1.5-sprint5-consolidation-stable` | Consolidation + legacy cleanup |
| `wbom-v1.6-production-ready` | **Production hardening + UX polish (this release)** |

---

## Security Notes

- API is **not** internet-exposed — only reachable inside the Docker network
- All routes require `X-INTERNAL-KEY` header (set via `WBOM_INTERNAL_KEY`)
- No stack traces in error responses — only opaque `error_id` references
- CORS is `allow_origins=["*"]` (safe: service is internal-only)
- Run `scripts/backup.sh` nightly via cron

---

*Maintained by the WBOM engineering team. For schema details see [WBOM_SOURCE_OF_TRUTH.md](WBOM_SOURCE_OF_TRUTH.md).*
