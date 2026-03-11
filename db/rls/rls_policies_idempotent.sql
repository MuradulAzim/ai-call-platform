-- ============================================================
-- Fazle — PostgreSQL Row-Level Security (RLS) Policies
-- IDEMPOTENT VERSION — safe to re-run at any time
-- Generated from: fazle-system/api/rls_policies.sql
-- ============================================================
--
-- The application sets: SET LOCAL app.current_user_id = '<uuid>';
-- on each request via psycopg2 before querying.
--
-- Run with: psql -v ON_ERROR_STOP=1 --single-transaction

-- ── Enable RLS (safe to re-run) ────────────────────────────

ALTER TABLE IF EXISTS fazle_conversations ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS fazle_conversations FORCE ROW LEVEL SECURITY;

ALTER TABLE IF EXISTS fazle_messages ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS fazle_messages FORCE ROW LEVEL SECURITY;

ALTER TABLE IF EXISTS fazle_audit_log ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS fazle_audit_log FORCE ROW LEVEL SECURITY;

-- ── Conversation policies ──────────────────────────────────

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE schemaname = 'public'
      AND tablename  = 'fazle_conversations'
      AND policyname = 'conversation_user_select'
  ) THEN
    CREATE POLICY conversation_user_select ON public.fazle_conversations
      FOR SELECT
      USING (user_id = current_setting('app.current_user_id', true)::UUID);
  END IF;
END $$;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE schemaname = 'public'
      AND tablename  = 'fazle_conversations'
      AND policyname = 'conversation_user_insert'
  ) THEN
    CREATE POLICY conversation_user_insert ON public.fazle_conversations
      FOR INSERT
      WITH CHECK (user_id = current_setting('app.current_user_id', true)::UUID);
  END IF;
END $$;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE schemaname = 'public'
      AND tablename  = 'fazle_conversations'
      AND policyname = 'conversation_user_delete'
  ) THEN
    CREATE POLICY conversation_user_delete ON public.fazle_conversations
      FOR DELETE
      USING (user_id = current_setting('app.current_user_id', true)::UUID);
  END IF;
END $$;

-- ── Message policies ───────────────────────────────────────

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE schemaname = 'public'
      AND tablename  = 'fazle_messages'
      AND policyname = 'message_user_select'
  ) THEN
    CREATE POLICY message_user_select ON public.fazle_messages
      FOR SELECT
      USING (
        conversation_id IN (
          SELECT id FROM fazle_conversations
          WHERE user_id = current_setting('app.current_user_id', true)::UUID
        )
      );
  END IF;
END $$;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE schemaname = 'public'
      AND tablename  = 'fazle_messages'
      AND policyname = 'message_user_insert'
  ) THEN
    CREATE POLICY message_user_insert ON public.fazle_messages
      FOR INSERT
      WITH CHECK (
        conversation_id IN (
          SELECT id FROM fazle_conversations
          WHERE user_id = current_setting('app.current_user_id', true)::UUID
        )
      );
  END IF;
END $$;

-- ── Audit log — append-only ────────────────────────────────

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE schemaname = 'public'
      AND tablename  = 'fazle_audit_log'
      AND policyname = 'audit_insert'
  ) THEN
    CREATE POLICY audit_insert ON public.fazle_audit_log
      FOR INSERT
      WITH CHECK (true);
  END IF;
END $$;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE schemaname = 'public'
      AND tablename  = 'fazle_audit_log'
      AND policyname = 'audit_select'
  ) THEN
    CREATE POLICY audit_select ON public.fazle_audit_log
      FOR SELECT
      USING (current_setting('app.is_admin', true) = 'true');
  END IF;
END $$;

-- No UPDATE or DELETE policies on fazle_audit_log:
-- denied by default when RLS is enabled (append-only).

-- ── Done ────────────────────────────────────────────────────
-- All policies are idempotent. Re-running this file is safe.
