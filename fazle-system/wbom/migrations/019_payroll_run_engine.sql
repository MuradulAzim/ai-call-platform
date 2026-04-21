-- ============================================================
-- 019: WBOM Payroll Run Engine
-- Sprint-1  P0-01 / P0-02 / P0-03
--
-- Adds:
--   wbom_payroll_runs        — one row per employee per period
--   wbom_payroll_run_items   — traceable line-item breakdown
--   wbom_payroll_approval_log — immutable approval audit trail
--
-- All statements are idempotent (CREATE … IF NOT EXISTS).
-- Additive only — no existing tables are altered or dropped.
-- ============================================================

-- ── Payroll run ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS wbom_payroll_runs (
    run_id              BIGSERIAL PRIMARY KEY,
    employee_id         INT NOT NULL REFERENCES wbom_employees(employee_id),
    period_year         INT NOT NULL,
    period_month        INT NOT NULL,

    -- Lifecycle status
    status  VARCHAR(20) NOT NULL DEFAULT 'draft',

    -- Formula components stored verbatim for full traceability
    basic_salary        DECIMAL(12,2) NOT NULL DEFAULT 0,
    total_programs      INT          NOT NULL DEFAULT 0,
    per_program_rate    DECIMAL(10,2) NOT NULL DEFAULT 0,
    program_allowance   DECIMAL(12,2) NOT NULL DEFAULT 0,
    other_allowance     DECIMAL(12,2) NOT NULL DEFAULT 0,
    total_advances      DECIMAL(12,2) NOT NULL DEFAULT 0,
    total_deductions    DECIMAL(12,2) NOT NULL DEFAULT 0,
    gross_salary        DECIMAL(12,2) NOT NULL DEFAULT 0,
    net_salary          DECIMAL(12,2) NOT NULL DEFAULT 0,

    -- Payout metadata
    payout_target_date      DATE,
    payment_method          VARCHAR(20),
    payment_reference       VARCHAR(80),
    payout_idempotency_key  VARCHAR(80),
    paid_at                 TIMESTAMPTZ,

    -- Workflow actors
    computed_by     VARCHAR(80),
    submitted_by    VARCHAR(80),
    approved_by     VARCHAR(80),
    locked_by       VARCHAR(80),
    paid_by         VARCHAR(80),
    correction_reason TEXT,
    remarks         TEXT,

    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT chk_payroll_run_status CHECK (
        status IN ('draft', 'reviewed', 'approved', 'locked', 'paid', 'cancelled')
    ),
    CONSTRAINT chk_payroll_run_month CHECK (period_month BETWEEN 1 AND 12),
    CONSTRAINT chk_payroll_run_year  CHECK (period_year  BETWEEN 2020 AND 2099)
);

-- One non-cancelled run per employee per period (P0-03 duplicate guard)
CREATE UNIQUE INDEX IF NOT EXISTS idx_payroll_runs_unique_active
    ON wbom_payroll_runs (employee_id, period_year, period_month)
    WHERE status != 'cancelled';

-- Prevent duplicate payout execution (P0-03)
CREATE UNIQUE INDEX IF NOT EXISTS idx_payroll_runs_payout_idem
    ON wbom_payroll_runs (payout_idempotency_key)
    WHERE payout_idempotency_key IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_payroll_runs_employee ON wbom_payroll_runs (employee_id);
CREATE INDEX IF NOT EXISTS idx_payroll_runs_period   ON wbom_payroll_runs (period_year, period_month);
CREATE INDEX IF NOT EXISTS idx_payroll_runs_status   ON wbom_payroll_runs (status);

-- ── Payroll line items ────────────────────────────────────────
CREATE TABLE IF NOT EXISTS wbom_payroll_run_items (
    item_id         BIGSERIAL PRIMARY KEY,
    run_id          BIGINT NOT NULL REFERENCES wbom_payroll_runs(run_id) ON DELETE CASCADE,
    component_type  VARCHAR(40)   NOT NULL,
    component_label VARCHAR(100)  NOT NULL,
    amount          DECIMAL(12,2) NOT NULL,
    sign            VARCHAR(1)    NOT NULL DEFAULT '+',
    source_table    VARCHAR(60),
    source_id       BIGINT,
    notes           TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT chk_payroll_item_sign CHECK (sign IN ('+', '-'))
);

CREATE INDEX IF NOT EXISTS idx_payroll_run_items_run  ON wbom_payroll_run_items (run_id);
CREATE INDEX IF NOT EXISTS idx_payroll_run_items_type ON wbom_payroll_run_items (component_type);

-- ── Immutable approval audit log ─────────────────────────────
CREATE TABLE IF NOT EXISTS wbom_payroll_approval_log (
    log_id      BIGSERIAL PRIMARY KEY,
    run_id      BIGINT NOT NULL REFERENCES wbom_payroll_runs(run_id),
    action      VARCHAR(30) NOT NULL,
    actor       VARCHAR(80) NOT NULL,
    from_status VARCHAR(20),
    to_status   VARCHAR(20),
    reason      TEXT,
    payload_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_payroll_approval_log_run   ON wbom_payroll_approval_log (run_id);
CREATE INDEX IF NOT EXISTS idx_payroll_approval_log_actor ON wbom_payroll_approval_log (actor);
CREATE INDEX IF NOT EXISTS idx_payroll_approval_log_ts    ON wbom_payroll_approval_log (created_at DESC);
