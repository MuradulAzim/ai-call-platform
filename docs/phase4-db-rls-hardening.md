# Phase 4 — DB RLS Hardening & Migration Safety

**Date:** 2026-03-12
**Scope:** Apply Row-Level Security policies to PostgreSQL, with pre-checks, transactional apply, and verification.

---

## What This Phase Changes

- **Enables RLS** (`ENABLE ROW LEVEL SECURITY` + `FORCE ROW LEVEL SECURITY`) on:
  - `fazle_conversations`
  - `fazle_messages`
  - `fazle_audit_log`
- **Creates RLS policies** (idempotent — safe to re-run):
  - `conversation_user_select`, `conversation_user_insert`, `conversation_user_delete`
  - `message_user_select`, `message_user_insert`
  - `audit_insert`, `audit_select`
- **Does NOT** change application code, credentials, or DB roles.

---

## Determine Your Database Name

The database name comes from your `.env` file (or compose defaults):

```bash
# On the VPS, check:
grep POSTGRES_DB .env
# If not set, the default is: postgres
```

The `docker-compose.yaml` uses `${POSTGRES_DB:-postgres}`.

---

## VPS Commands

Run these from the repo root on the VPS.

### 1. Pre-Check

```bash
chmod +x scripts/vps/db_precheck.sh
./scripts/vps/db_precheck.sh --db postgres
```

Validates: Docker available, container running, pg_isready, DB exists, disk space.

### 2. Dry Run (Optional)

```bash
chmod +x scripts/vps/db_apply_rls.sh
./scripts/vps/db_apply_rls.sh --db postgres --dry-run
```

Prints the SQL that would be applied without executing.

### 3. Apply RLS Policies

```bash
./scripts/vps/db_apply_rls.sh --db postgres
```

Applies `db/rls/rls_policies_idempotent.sql` in a single transaction.
If any statement fails, **nothing is committed**.

### 4. Verify

```bash
chmod +x scripts/vps/db_verify_rls.sh
./scripts/vps/db_verify_rls.sh --db postgres
```

Checks:
- RLS enabled + forced on expected tables
- All expected policies present in `pg_policies`

---

## Rollback Guidance

### If Apply Fails Mid-Execution

Nothing was committed — the script uses `--single-transaction`. No rollback needed.

### If You Need to Remove Policies After Successful Apply

Run manually inside the container:

```bash
docker exec -i ai-postgres psql -U postgres -d postgres -v ON_ERROR_STOP=1 <<'SQL'
-- Remove policies
DROP POLICY IF EXISTS conversation_user_select ON fazle_conversations;
DROP POLICY IF EXISTS conversation_user_insert ON fazle_conversations;
DROP POLICY IF EXISTS conversation_user_delete ON fazle_conversations;
DROP POLICY IF EXISTS message_user_select ON fazle_messages;
DROP POLICY IF EXISTS message_user_insert ON fazle_messages;
DROP POLICY IF EXISTS audit_insert ON fazle_audit_log;
DROP POLICY IF EXISTS audit_select ON fazle_audit_log;

-- Disable RLS (optional — only if you want to fully revert)
ALTER TABLE fazle_conversations DISABLE ROW LEVEL SECURITY;
ALTER TABLE fazle_messages DISABLE ROW LEVEL SECURITY;
ALTER TABLE fazle_audit_log DISABLE ROW LEVEL SECURITY;
SQL
```

> **Warning:** Disabling RLS removes all row-level restrictions. Only do this if you understand the security implications.

---

## Acceptance Checklist

- [ ] `db_precheck.sh` exits 0
- [ ] `db_apply_rls.sh` exits 0
- [ ] `db_verify_rls.sh` exits 0
- [ ] RLS enabled + forced on `fazle_conversations`, `fazle_messages`, `fazle_audit_log`
- [ ] All 7 policies visible in `pg_policies`
- [ ] Application health checks still pass after apply (`docker ps` shows all containers healthy)

---

## Optional: Role Hardening (Phase 4b — NOT Required Now)

The repo currently uses the `postgres` superuser for all app connections. Phase 4 does **not** change this.

If you want to harden DB roles later:

```bash
chmod +x scripts/vps/db_apply_roles.sh
./scripts/vps/db_apply_roles.sh --db postgres
```

This applies `db/hardening/roles_and_grants.sql` which:
- Revokes default public schema privileges
- Creates least-privilege roles (`fazle_app`, `dograh_app`, `fazle_readonly`)
- Grants minimal permissions per role

> **Warning:** Switching application credentials to these roles requires updating `DATABASE_URL` in `.env` / compose and restarting services. Coordinate carefully.

---

## Files Added in Phase 4

| File | Purpose |
|------|---------|
| `db/rls/rls_policies_idempotent.sql` | Idempotent RLS policy SQL |
| `scripts/vps/db_precheck.sh` | Pre-flight connectivity checks |
| `scripts/vps/db_apply_rls.sh` | Apply RLS with transaction safety |
| `scripts/vps/db_verify_rls.sh` | Post-apply verification |
| `docs/phase4-db-rls-hardening.md` | This document |
| `db/hardening/roles_and_grants.sql` | Optional role hardening SQL |
| `scripts/vps/db_apply_roles.sh` | Optional role apply script |
