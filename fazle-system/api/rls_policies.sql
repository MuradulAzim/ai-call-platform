-- ============================================================
-- Fazle — PostgreSQL Row-Level Security (RLS) Policies
-- Ensures users can only access their own data at the DB level,
-- independent of application-layer checks
-- ============================================================

-- Run this after tables are created.
-- The application sets: SET LOCAL app.current_user_id = '<uuid>';
-- on each request via psycopg2 before querying.

-- ── Enable RLS ─────────────────────────────────────────────

ALTER TABLE fazle_conversations ENABLE ROW LEVEL SECURITY;
ALTER TABLE fazle_messages ENABLE ROW LEVEL SECURITY;

-- ── Admin bypass ───────────────────────────────────────────
-- The 'postgres' superuser bypasses RLS by default.
-- Application-level admin checks remain in the API layer.

-- ── Conversation policies ──────────────────────────────────

-- Users can only see their own conversations
CREATE POLICY conversation_user_select ON fazle_conversations
    FOR SELECT
    USING (user_id = current_setting('app.current_user_id', true)::UUID);

-- Users can only insert their own conversations
CREATE POLICY conversation_user_insert ON fazle_conversations
    FOR INSERT
    WITH CHECK (user_id = current_setting('app.current_user_id', true)::UUID);

-- Users can only delete their own conversations
CREATE POLICY conversation_user_delete ON fazle_conversations
    FOR DELETE
    USING (user_id = current_setting('app.current_user_id', true)::UUID);

-- ── Message policies ───────────────────────────────────────

-- Users can only see messages in their own conversations
CREATE POLICY message_user_select ON fazle_messages
    FOR SELECT
    USING (
        conversation_id IN (
            SELECT id FROM fazle_conversations
            WHERE user_id = current_setting('app.current_user_id', true)::UUID
        )
    );

-- Users can only insert messages into their own conversations
CREATE POLICY message_user_insert ON fazle_messages
    FOR INSERT
    WITH CHECK (
        conversation_id IN (
            SELECT id FROM fazle_conversations
            WHERE user_id = current_setting('app.current_user_id', true)::UUID
        )
    );

-- ── Audit log — append-only ────────────────────────────────

ALTER TABLE fazle_audit_log ENABLE ROW LEVEL SECURITY;

-- Anyone can INSERT audit records
CREATE POLICY audit_insert ON fazle_audit_log
    FOR INSERT
    WITH CHECK (true);

-- Only the postgres superuser can SELECT (admin reads via application layer)
-- Non-superusers get no rows unless the app explicitly sets a session var
CREATE POLICY audit_select ON fazle_audit_log
    FOR SELECT
    USING (current_setting('app.is_admin', true) = 'true');

-- No UPDATE or DELETE allowed on audit log
-- (no policies = denied by default when RLS is enabled)
