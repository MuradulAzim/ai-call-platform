-- ============================================================
-- Migration 024 — Unify Complaint Storage  (Sprint-5 S5-02)
-- Goal: wbom_complaints is single source of truth.
--
-- Actions:
--   1. Add legacy_case_id to wbom_complaints for traceability.
--   2. Copy complaint-type rows from wbom_cases into wbom_complaints
--      (skip rows already linked via legacy_case_id).
--   3. Mark wbom_cases rows as migrated via metadata_json.
--
-- wbom_cases is KEPT for non-complaint workflows (HR, payroll, etc.)
-- IDEMPOTENT: safe to re-run.
-- ============================================================

-- ── 1. Add legacy_case_id column to wbom_complaints ─────────
ALTER TABLE wbom_complaints
    ADD COLUMN IF NOT EXISTS legacy_case_id BIGINT
    REFERENCES wbom_cases(case_id);

CREATE INDEX IF NOT EXISTS idx_complaints_legacy_case
    ON wbom_complaints (legacy_case_id)
    WHERE legacy_case_id IS NOT NULL;

-- ── 2. Copy complaint cases from wbom_cases → wbom_complaints ─
-- Map wbom_cases fields to wbom_complaints schema:
--   case_type='complaint' rows only.
--   severity/priority translate directly.
--   status: open→open, in_progress→investigating, resolved→resolved,
--           closed→closed, cancelled→closed, waiting_*→acknowledged.
INSERT INTO wbom_complaints (
    complaint_type,
    reporter_phone,
    reporter_name,
    category,
    description,
    priority,
    sla_hours,
    sla_due_at,
    sla_breached,
    status,
    assigned_to,
    assigned_at,
    resolved_at,
    resolution_notes,
    client_id,
    employee_id,
    source,
    legacy_case_id,
    created_at,
    updated_at
)
SELECT
    'client'                                              AS complaint_type,
    -- Extract phone from metadata_json if present, else from contact
    COALESCE(c.metadata_json->>'reporter_phone', '')      AS reporter_phone,
    COALESCE(c.metadata_json->>'reporter_name',  '')      AS reporter_name,
    'other'                                               AS category,   -- best-effort
    COALESCE(c.description, c.title)                      AS description,
    CASE c.priority
        WHEN 'urgent' THEN 'critical'
        WHEN 'high'   THEN 'high'
        WHEN 'normal' THEN 'medium'
        ELSE 'low'
    END                                                   AS priority,
    CASE c.severity
        WHEN 'critical' THEN 4
        WHEN 'high'     THEN 24
        WHEN 'medium'   THEN 72
        ELSE 168
    END                                                   AS sla_hours,
    c.due_at                                              AS sla_due_at,
    CASE WHEN c.due_at IS NOT NULL AND c.due_at < NOW()
             AND c.status NOT IN ('resolved','closed','cancelled')
         THEN TRUE ELSE FALSE
    END                                                   AS sla_breached,
    CASE c.status
        WHEN 'open'             THEN 'open'
        WHEN 'in_progress'      THEN 'investigating'
        WHEN 'waiting_customer' THEN 'acknowledged'
        WHEN 'waiting_internal' THEN 'acknowledged'
        WHEN 'resolved'         THEN 'resolved'
        WHEN 'closed'           THEN 'closed'
        WHEN 'cancelled'        THEN 'closed'
        ELSE 'open'
    END                                                   AS status,
    c.owner_user                                          AS assigned_to,
    c.opened_at                                           AS assigned_at,
    c.resolved_at,
    c.resolution_summary                                  AS resolution_notes,
    c.contact_id                                          AS client_id,
    c.employee_id,
    COALESCE(c.source_platform, 'whatsapp')               AS source,
    c.case_id                                             AS legacy_case_id,
    c.created_at,
    c.updated_at
FROM wbom_cases c
WHERE c.case_type = 'complaint'
  AND NOT EXISTS (
      SELECT 1
      FROM wbom_complaints wc
      WHERE wc.legacy_case_id = c.case_id
  );

-- ── 3. Mark migrated cases in wbom_cases ────────────────────
UPDATE wbom_cases
SET metadata_json = metadata_json || '{"migrated_to_complaints": true}'::jsonb
WHERE case_type = 'complaint'
  AND (metadata_json->>'migrated_to_complaints') IS DISTINCT FROM 'true';
