-- ============================================================
-- Migration 022 — Complaint + Client Retention (Sprint-4)
-- Tables: wbom_complaints, wbom_complaint_events
-- ============================================================

-- ── 1. Complaints table ──────────────────────────────────────
CREATE TABLE IF NOT EXISTS wbom_complaints (
    complaint_id      BIGSERIAL PRIMARY KEY,

    -- Who filed it
    complaint_type    VARCHAR(20)  NOT NULL,   -- client | employee
    reporter_phone    VARCHAR(20),
    reporter_name     VARCHAR(100),

    -- Category
    category          VARCHAR(50)  NOT NULL,
    -- client:   service_quality | replacement_request | payment_dispute | misconduct | other
    -- employee: salary_issue | supervisor_issue | harassment | duty_mismatch | other

    description       TEXT         NOT NULL,

    -- Priority & SLA
    priority          VARCHAR(10)  NOT NULL DEFAULT 'medium',
    -- critical | high | medium | low
    sla_hours         INT          NOT NULL DEFAULT 72,  -- from priority
    sla_due_at        TIMESTAMPTZ,
    sla_breached      BOOLEAN      NOT NULL DEFAULT FALSE,

    -- Workflow
    status            VARCHAR(20)  NOT NULL DEFAULT 'open',
    -- open | acknowledged | investigating | resolved | closed | escalated
    assigned_to       VARCHAR(80),
    assigned_at       TIMESTAMPTZ,

    -- Resolution
    resolved_at       TIMESTAMPTZ,
    resolution_notes  TEXT,

    -- Optional FK hints (not enforced — entities may not exist yet)
    client_id         INT,
    employee_id       INT,

    source            VARCHAR(20)  NOT NULL DEFAULT 'whatsapp',

    created_at        TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at        TIMESTAMPTZ  NOT NULL DEFAULT NOW(),

    CONSTRAINT chk_complaint_type CHECK (
        complaint_type IN ('client', 'employee')
    ),
    CONSTRAINT chk_complaint_priority CHECK (
        priority IN ('critical', 'high', 'medium', 'low')
    ),
    CONSTRAINT chk_complaint_status CHECK (
        status IN ('open','acknowledged','investigating',
                   'resolved','closed','escalated')
    )
);

CREATE INDEX IF NOT EXISTS idx_complaints_type
    ON wbom_complaints (complaint_type);
CREATE INDEX IF NOT EXISTS idx_complaints_status
    ON wbom_complaints (status);
CREATE INDEX IF NOT EXISTS idx_complaints_priority
    ON wbom_complaints (priority);
CREATE INDEX IF NOT EXISTS idx_complaints_sla_due
    ON wbom_complaints (sla_due_at)
    WHERE sla_breached = FALSE AND status NOT IN ('resolved', 'closed');
CREATE INDEX IF NOT EXISTS idx_complaints_reporter
    ON wbom_complaints (reporter_phone);
CREATE INDEX IF NOT EXISTS idx_complaints_assigned
    ON wbom_complaints (assigned_to)
    WHERE assigned_to IS NOT NULL;


-- ── 2. Complaint events (audit trail) ───────────────────────
CREATE TABLE IF NOT EXISTS wbom_complaint_events (
    event_id      BIGSERIAL PRIMARY KEY,
    complaint_id  BIGINT       NOT NULL
                  REFERENCES wbom_complaints(complaint_id) ON DELETE CASCADE,
    event_type    VARCHAR(40)  NOT NULL,
    -- created | acknowledged | assigned | escalated | status_changed | sla_breach | resolved
    actor         VARCHAR(80)  DEFAULT 'system',
    from_status   VARCHAR(20),
    to_status     VARCHAR(20),
    notes         TEXT,
    created_at    TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_cevents_complaint
    ON wbom_complaint_events (complaint_id);
