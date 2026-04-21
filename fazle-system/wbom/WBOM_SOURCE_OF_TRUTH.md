# WBOM Source of Truth — Sprint-5 Consolidation

> **Last Updated:** Sprint-5 Consolidation (2026-04)  
> **Maintained by:** Engineering team. Update this document whenever a table is promoted or deprecated.

---

## Purpose

This document is the canonical record of which database table, service, and API endpoint is the **single authoritative source** for each data domain in the WBOM system. When two systems appear to store the same data, look here to determine which one is canonical.

---

## 1. Payroll

| Property | Value |
|---|---|
| **Canonical table** | `wbom_payroll_runs` |
| **Deprecated table** | `wbom_salary_records` |
| **Migration** | `migrations/023_unify_payroll.sql` |
| **Canonical service** | `services/payroll_engine.py` |
| **Deprecated service** | `services/salary_generator.py` (fallback only) |
| **Canonical API** | `GET/POST /api/wbom/payroll` |
| **Deprecated API** | `GET /api/wbom/salary` — returns HTTP 200 with `Deprecation: true` header, sunsets 2026-07-01 |
| **Report endpoint** | `GET /api/wbom/reports/salary` reads from `wbom_payroll_runs` first, falls back to `wbom_salary_records` with `source="legacy_salary_records"` in response |

### Column mapping (wbom_salary_records → wbom_payroll_runs)

| salary_records | payroll_runs |
|---|---|
| `salary_id` | — (stored as `legacy_salary_id` in payroll_runs) |
| `is_paid = True` | `status = 'paid'` |
| `is_paid = False` | `status = 'draft'` |
| `month` / `year` | `period_month` / `period_year` |
| `total_programs` | `total_programs` |

### Rule

> **Do NOT** write new payroll data to `wbom_salary_records`. All payroll operations go through `services/payroll_engine.py` → `wbom_payroll_runs`.

---

## 2. Complaints

| Property | Value |
|---|---|
| **Canonical table** | `wbom_complaints` |
| **Deprecated table** | `wbom_cases` (case_type = 'complaint') |
| **Migration** | `migrations/024_unify_complaints.sql` |
| **Canonical service** | `services/complaints.py` → `ingest_complaint()` |
| **Deprecated function** | `services/case_workflow.py` → `create_complaint_case()` |
| **Canonical API** | `GET /api/wbom/complaints`, `POST /api/wbom/complaints/ingest` |
| **WhatsApp path** | `POST /api/wbom/messages/dispatch` → `services/message_processor.py` → `ingest_complaint()` |

### Status mapping (wbom_cases → wbom_complaints)

| wbom_cases.status | wbom_complaints.status |
|---|---|
| `in_progress` | `investigating` |
| `waiting_*` | `acknowledged` |
| `cancelled` | `closed` |
| `open` | `open` |
| `resolved` | `resolved` |

### Priority mapping

| wbom_cases.priority | wbom_complaints.priority |
|---|---|
| `urgent` | `critical` |
| `high` | `high` |
| `normal` | `medium` |
| `low` | `low` |

### SLA hours

| Priority | SLA |
|---|---|
| critical | 4 h |
| high | 24 h |
| medium | 72 h |
| low | 168 h |

### Rule

> **Do NOT** call `create_complaint_case()` for new complaints. Use `ingest_complaint()` from `services/complaints.py`. `wbom_cases` is retained for non-complaint case types (operational incidents, HR cases, etc.).

---

## 3. WhatsApp Message Routing

| Property | Value |
|---|---|
| **Canonical endpoint** | `POST /api/wbom/messages/dispatch` |
| **Deprecated endpoints** | `POST /api/wbom/messages/process` (kept for backward compat) |
| **Routing logic** | Keyword-based: recruitment keywords → `services/recruitment.intake_message()`, all others → `services/message_processor.process_incoming_message()` |
| **Duplicate guard** | Checked against `wbom_whatsapp_messages.whatsapp_msg_id` |

### Recruitment keywords (case-insensitive)

```
job, কাজ, চাকরি, vacancy, apply, hire, recruit, নিয়োগ,
কাজের, চাই, interested, work, join, joining
```

### Rule

> **All new WhatsApp integrations must use** `POST /api/wbom/messages/dispatch`. Do not route messages directly to `/messages/process` or `/recruitment/intake`.

---

## 4. Candidate Tracking

| Property | Value |
|---|---|
| **Canonical table** | `wbom_candidates` |
| **Deprecated table** | `wbom_job_applications` |
| **Migration** | `migrations/025_merge_candidates.sql` |
| **Canonical service** | `services/recruitment.py` |
| **Canonical API (write)** | `POST /api/wbom/recruitment/intake`, `PUT /api/wbom/recruitment/candidates/:id` |
| **Deprecated API (write)** | `POST /api/wbom/job-applications` → HTTP 410 Gone |
| **Historical read** | `GET /api/wbom/job-applications` (read-only, with deprecation note) |

### Funnel stage mapping (wbom_job_applications → wbom_candidates)

| job_applications.status | candidates.funnel_stage |
|---|---|
| Applied | new |
| Screened | collecting |
| Interviewed | interviewed |
| Hired | hired |
| Rejected | rejected |

### Rule

> **Do NOT** write to `wbom_job_applications`. Use `POST /api/wbom/recruitment/intake` for inbound candidates. Historical data in `wbom_job_applications` is available read-only.

---

## 5. Frontend Pages

| Domain | Page route | API endpoint |
|---|---|---|
| Dashboard | `/dashboard/wbom` | `GET /api/wbom/dashboard/summary` |
| Employees | `/dashboard/wbom/employees` | `GET /api/wbom/employees` |
| Transactions | `/dashboard/wbom/transactions` | `GET /api/wbom/transactions` |
| Payments | `/dashboard/wbom/payments` | `GET /api/wbom/payment/pending` |
| Clients | `/dashboard/wbom/clients` | `GET /api/wbom/clients` |
| **Payroll** | `/dashboard/wbom/payroll` | `GET /api/wbom/payroll` |
| **Complaints** | `/dashboard/wbom/complaints` | `GET /api/wbom/complaints` |
| **Recruitment** | `/dashboard/wbom/recruitment` | `GET /api/wbom/recruitment/candidates` |
| Applications (archive) | `/dashboard/wbom/applications` | `GET /api/wbom/job-applications` (read-only) |
| Audit Log | `/dashboard/wbom/audit` | `GET /api/wbom/audit` |

---

## 6. Migration Inventory

| File | Purpose | Status |
|---|---|---|
| `migrations/001–015` | Schema foundation | Applied |
| `migrations/016_payroll_engine.sql` | `wbom_payroll_runs` table | Applied |
| `migrations/017_complaints.sql` | `wbom_complaints` table | Applied |
| `migrations/021_candidates.sql` | `wbom_candidates` table | Applied |
| `migrations/023_unify_payroll.sql` | Copy `wbom_salary_records` → `wbom_payroll_runs` | **Run on deploy** |
| `migrations/024_unify_complaints.sql` | Copy complaint-type rows `wbom_cases` → `wbom_complaints` | **Run on deploy** |
| `migrations/025_merge_candidates.sql` | Copy `wbom_job_applications` → `wbom_candidates` | **Run on deploy** |

---

## 7. Deprecation Timeline

| Endpoint / Table | Deprecated since | Sunset date | Action |
|---|---|---|---|
| `GET /api/wbom/salary/*` | Sprint-5 | 2026-07-01 | Returns data + `Deprecation: true` header |
| `POST /api/wbom/job-applications` | Sprint-5 | Immediate | Returns HTTP 410 Gone |
| `PUT /api/wbom/job-applications/:id` | Sprint-5 | Immediate | Returns HTTP 410 Gone |
| `wbom_salary_records` writes | Sprint-5 | 2026-07-01 | No new writes |
| `create_complaint_case()` calls | Sprint-5 | 2026-07-01 | Use `ingest_complaint()` |

---

## 8. Non-negotiable Rules

1. **Additive only** — migrations add columns/rows, never drop.
2. **No data deletion** — deprecated tables are preserved for audit.
3. **Backward compat** — all deprecated endpoints return data until sunset date.
4. **Single truth** — each domain has exactly one canonical table and service.
5. **Tests first** — every consolidation merge path must have a monkeypatched test.
