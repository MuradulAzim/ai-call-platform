-- ============================================================
-- OPTIONAL — DB Role Hardening for Dograh + Fazle
-- Creates least-privilege application roles
-- IDEMPOTENT — safe to re-run
-- ============================================================
--
-- WARNING: This does NOT switch app credentials automatically.
-- After running this, you must update DATABASE_URL in .env
-- to use the new roles and restart services.
--
-- Run with: psql -v ON_ERROR_STOP=1 --single-transaction

-- ── Revoke default public privileges ────────────────────────
-- Prevent any new role from inheriting broad access
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
-- Keep USAGE so existing queries work; CREATE is the dangerous one

-- ── Create roles (idempotent) ───────────────────────────────

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'fazle_app') THEN
    CREATE ROLE fazle_app LOGIN;
  END IF;
END $$;

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'dograh_app') THEN
    CREATE ROLE dograh_app LOGIN;
  END IF;
END $$;

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'fazle_readonly') THEN
    CREATE ROLE fazle_readonly LOGIN;
  END IF;
END $$;

-- NOTE: Passwords are NOT set here. Set them manually:
--   ALTER ROLE fazle_app PASSWORD 'secure_password_here';
-- Or use environment-based auth (pg_hba.conf trust on Docker network).

-- ── Grant schema usage ─────────────────────────────────────

GRANT USAGE ON SCHEMA public TO fazle_app;
GRANT USAGE ON SCHEMA public TO dograh_app;
GRANT USAGE ON SCHEMA public TO fazle_readonly;

-- ── Fazle app role grants ──────────────────────────────────
-- Full DML on Fazle tables (conversations, messages, audit)

GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE fazle_conversations TO fazle_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE fazle_messages TO fazle_app;
GRANT INSERT ON TABLE fazle_audit_log TO fazle_app;

-- Grant on sequences used by Fazle tables (if any)
DO $$
DECLARE
  seq_rec RECORD;
BEGIN
  FOR seq_rec IN
    SELECT sequence_name FROM information_schema.sequences
    WHERE sequence_schema = 'public'
      AND sequence_name LIKE 'fazle_%'
  LOOP
    EXECUTE format('GRANT USAGE, SELECT ON SEQUENCE %I TO fazle_app;', seq_rec.sequence_name);
  END LOOP;
END $$;

-- ── Dograh app role grants ─────────────────────────────────
-- Grant on all current tables in public schema that are NOT fazle-prefixed
-- (Dograh owns the rest of the schema)

DO $$
DECLARE
  tbl_rec RECORD;
BEGIN
  FOR tbl_rec IN
    SELECT tablename FROM pg_tables
    WHERE schemaname = 'public'
      AND tablename NOT LIKE 'fazle_%'
  LOOP
    EXECUTE format('GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE %I TO dograh_app;', tbl_rec.tablename);
  END LOOP;
END $$;

DO $$
DECLARE
  seq_rec RECORD;
BEGIN
  FOR seq_rec IN
    SELECT sequence_name FROM information_schema.sequences
    WHERE sequence_schema = 'public'
      AND sequence_name NOT LIKE 'fazle_%'
  LOOP
    EXECUTE format('GRANT USAGE, SELECT ON SEQUENCE %I TO dograh_app;', seq_rec.sequence_name);
  END LOOP;
END $$;

-- ── Read-only role grants ──────────────────────────────────

GRANT SELECT ON ALL TABLES IN SCHEMA public TO fazle_readonly;

-- ── Default privileges for future tables ────────────────────
-- So new tables created by postgres also get grants

ALTER DEFAULT PRIVILEGES IN SCHEMA public
  GRANT SELECT ON TABLES TO fazle_readonly;

-- ============================================================
-- IMPORTANT: After running this SQL, you must:
-- 1. Set passwords for the new roles
-- 2. Update DATABASE_URL / FAZLE_DATABASE_URL in .env
-- 3. Restart affected services
-- ============================================================
