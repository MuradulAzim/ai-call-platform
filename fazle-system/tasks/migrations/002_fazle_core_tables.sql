-- ============================================================
-- Fazle Core Tables Migration — 002
-- Creates users, conversations, messages, and audit tables.
-- Idempotent: safe to run multiple times.
-- ============================================================

-- ── Users ──────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS fazle_users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    hashed_password VARCHAR(255) NOT NULL,
    name VARCHAR(100) NOT NULL,
    relationship_to_azim VARCHAR(50) NOT NULL DEFAULT 'self',
    role VARCHAR(20) NOT NULL DEFAULT 'member',
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_fazle_users_email ON fazle_users (email);

-- ── Conversations ──────────────────────────────────────────
CREATE TABLE IF NOT EXISTS fazle_conversations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES fazle_users(id) ON DELETE CASCADE,
    conversation_id VARCHAR(100) NOT NULL,
    title VARCHAR(200) DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(conversation_id)
);
CREATE INDEX IF NOT EXISTS idx_fazle_conv_user ON fazle_conversations (user_id);

-- ── Messages ───────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS fazle_messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id UUID NOT NULL REFERENCES fazle_conversations(id) ON DELETE CASCADE,
    role VARCHAR(20) NOT NULL,
    content TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_fazle_msg_conv ON fazle_messages (conversation_id);

-- ── Audit Log (append-only) ────────────────────────────────
CREATE TABLE IF NOT EXISTS fazle_audit_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    actor_id VARCHAR(100) NOT NULL,
    actor_email VARCHAR(255) NOT NULL DEFAULT '',
    action VARCHAR(100) NOT NULL,
    target_type VARCHAR(50) NOT NULL DEFAULT '',
    target_id VARCHAR(100) DEFAULT '',
    detail TEXT DEFAULT '',
    ip_address VARCHAR(45) DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_audit_actor ON fazle_audit_log (actor_id);
CREATE INDEX IF NOT EXISTS idx_audit_action ON fazle_audit_log (action);
CREATE INDEX IF NOT EXISTS idx_audit_created ON fazle_audit_log (created_at);

-- ── Row-Level Security ─────────────────────────────────────
-- Enable RLS on data tables (superuser bypasses by default)
ALTER TABLE fazle_conversations ENABLE ROW LEVEL SECURITY;
ALTER TABLE fazle_messages ENABLE ROW LEVEL SECURITY;
ALTER TABLE fazle_audit_log ENABLE ROW LEVEL SECURITY;

-- Conversation policies
DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = 'conversation_user_select') THEN
        CREATE POLICY conversation_user_select ON fazle_conversations
            FOR SELECT USING (user_id = current_setting('app.current_user_id', true)::UUID);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = 'conversation_user_insert') THEN
        CREATE POLICY conversation_user_insert ON fazle_conversations
            FOR INSERT WITH CHECK (user_id = current_setting('app.current_user_id', true)::UUID);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = 'conversation_user_delete') THEN
        CREATE POLICY conversation_user_delete ON fazle_conversations
            FOR DELETE USING (user_id = current_setting('app.current_user_id', true)::UUID);
    END IF;
END $$;

-- Message policies
DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = 'message_user_select') THEN
        CREATE POLICY message_user_select ON fazle_messages
            FOR SELECT USING (conversation_id IN (
                SELECT id FROM fazle_conversations
                WHERE user_id = current_setting('app.current_user_id', true)::UUID
            ));
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = 'message_user_insert') THEN
        CREATE POLICY message_user_insert ON fazle_messages
            FOR INSERT WITH CHECK (conversation_id IN (
                SELECT id FROM fazle_conversations
                WHERE user_id = current_setting('app.current_user_id', true)::UUID
            ));
    END IF;
END $$;

-- Audit log: append-only (insert yes, select admin only, no update/delete)
DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = 'audit_insert') THEN
        CREATE POLICY audit_insert ON fazle_audit_log FOR INSERT WITH CHECK (true);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = 'audit_select') THEN
        CREATE POLICY audit_select ON fazle_audit_log FOR SELECT
            USING (current_setting('app.is_admin', true) = 'true');
    END IF;
END $$;
