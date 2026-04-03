-- ============================================================
-- Owner Knowledge Table Migration — 003
-- Stores structured life knowledge about the owner (Azim).
-- Categories: personal, business, political, family, daily,
--             social, religious, financial, health, tech
-- Idempotent: safe to run multiple times.
-- ============================================================

CREATE TABLE IF NOT EXISTS fazle_owner_knowledge (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    category VARCHAR(50) NOT NULL,
    subcategory VARCHAR(100) NOT NULL DEFAULT '',
    key VARCHAR(200) NOT NULL,
    value TEXT NOT NULL,
    language VARCHAR(10) NOT NULL DEFAULT 'en',
    confidence REAL NOT NULL DEFAULT 1.0,
    source VARCHAR(50) NOT NULL DEFAULT 'owner_chat',
    metadata JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(category, key)
);

-- Indexes for fast lookup
CREATE INDEX IF NOT EXISTS idx_owner_knowledge_category ON fazle_owner_knowledge (category);
CREATE INDEX IF NOT EXISTS idx_owner_knowledge_key ON fazle_owner_knowledge (key);
CREATE INDEX IF NOT EXISTS idx_owner_knowledge_lang ON fazle_owner_knowledge (language);
CREATE INDEX IF NOT EXISTS idx_owner_knowledge_meta ON fazle_owner_knowledge USING gin (metadata);

-- Upsert function for idempotent inserts
CREATE OR REPLACE FUNCTION upsert_owner_knowledge(
    p_category VARCHAR, p_subcategory VARCHAR, p_key VARCHAR,
    p_value TEXT, p_language VARCHAR DEFAULT 'en',
    p_confidence REAL DEFAULT 1.0, p_source VARCHAR DEFAULT 'owner_chat',
    p_metadata JSONB DEFAULT '{}'
) RETURNS UUID AS $$
DECLARE
    result_id UUID;
BEGIN
    INSERT INTO fazle_owner_knowledge (category, subcategory, key, value, language, confidence, source, metadata)
    VALUES (p_category, p_subcategory, p_key, p_value, p_language, p_confidence, p_source, p_metadata)
    ON CONFLICT (category, key)
    DO UPDATE SET
        value = EXCLUDED.value,
        subcategory = EXCLUDED.subcategory,
        language = EXCLUDED.language,
        confidence = EXCLUDED.confidence,
        source = EXCLUDED.source,
        metadata = fazle_owner_knowledge.metadata || EXCLUDED.metadata,
        updated_at = NOW()
    RETURNING id INTO result_id;
    RETURN result_id;
END;
$$ LANGUAGE plpgsql;
