-- ============================================================
-- Migration 025 — Merge Job Applications → Candidates (Sprint-5 S5-04)
-- Goal: wbom_candidates is single candidate source of truth.
--
-- Actions:
--   1. Copy rows from wbom_job_applications into wbom_candidates,
--      deduplicating by phone (existing candidate wins).
--   2. Status mapping:
--        Applied      → new
--        Screened     → collecting
--        Interviewed  → interviewed
--        Hired        → hired
--        Rejected     → rejected
--   3. Mark migrated rows in wbom_job_applications.
--
-- wbom_job_applications table is KEPT (read-only historical access).
-- IDEMPOTENT: safe to re-run.
-- ============================================================

-- ── 1. Add legacy_application_id to wbom_candidates ─────────
ALTER TABLE wbom_candidates
    ADD COLUMN IF NOT EXISTS legacy_application_id INT
    REFERENCES wbom_job_applications(application_id);

CREATE INDEX IF NOT EXISTS idx_candidates_legacy_app
    ON wbom_candidates (legacy_application_id)
    WHERE legacy_application_id IS NOT NULL;

-- ── 2. Copy unmatched applications → candidates ──────────────
-- Skip phone numbers that already exist in wbom_candidates.
INSERT INTO wbom_candidates (
    phone,
    full_name,
    job_preference,
    funnel_stage,
    score,
    score_bucket,
    source,
    source_message,
    notes,
    legacy_application_id,
    created_at,
    updated_at
)
SELECT
    ja.phone,
    ja.applicant_name                               AS full_name,
    ja.position                                     AS job_preference,
    CASE ja.status
        WHEN 'Applied'      THEN 'new'
        WHEN 'Screened'     THEN 'collecting'
        WHEN 'Interviewed'  THEN 'interviewed'
        WHEN 'Hired'        THEN 'hired'
        WHEN 'Rejected'     THEN 'rejected'
        ELSE 'new'
    END                                             AS funnel_stage,
    0                                               AS score,
    'cold'                                          AS score_bucket,
    COALESCE(ja.source, 'whatsapp')                 AS source,
    ja.experience                                   AS source_message,
    COALESCE(ja.notes, 'Migrated from wbom_job_applications') AS notes,
    ja.application_id                               AS legacy_application_id,
    ja.created_at,
    ja.updated_at
FROM wbom_job_applications ja
WHERE NOT EXISTS (
    SELECT 1
    FROM wbom_candidates wc
    WHERE wc.phone = ja.phone
)
ON CONFLICT (phone) DO NOTHING;

-- ── 3. Mark migrated rows in source table ────────────────────
-- Add a column to track migration status (idempotent)
ALTER TABLE wbom_job_applications
    ADD COLUMN IF NOT EXISTS migrated_to_candidates BOOLEAN NOT NULL DEFAULT FALSE;

UPDATE wbom_job_applications ja
SET migrated_to_candidates = TRUE
WHERE EXISTS (
    SELECT 1
    FROM wbom_candidates wc
    WHERE wc.phone = ja.phone
)
  AND migrated_to_candidates = FALSE;
