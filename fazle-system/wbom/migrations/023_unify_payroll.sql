-- ============================================================
-- Migration 023 — Unify Payroll  (Sprint-5 S5-01)
-- Goal: make wbom_payroll_runs the single source of truth.
--
-- Actions:
--   1. Copy rows from wbom_salary_records that have no matching
--      payroll_run for the same (employee_id, month, year).
--   2. Mark copied salary records so they're traceable.
--   3. Add legacy_salary_id to payroll_runs for provenance.
--
-- IDEMPOTENT: safe to re-run.
-- ============================================================

-- ── 1. Add provenance column to payroll_runs ─────────────────
ALTER TABLE wbom_payroll_runs
    ADD COLUMN IF NOT EXISTS legacy_salary_id INT
    REFERENCES wbom_salary_records(salary_id);

-- ── 2. Copy unmatched salary records → payroll_runs ──────────
-- Insert one draft run per salary record that has no matching run
-- Use a status of 'paid' if the salary was paid; 'draft' otherwise.
INSERT INTO wbom_payroll_runs (
    employee_id,
    period_year,
    period_month,
    status,
    basic_salary,
    total_programs,
    per_program_rate,
    program_allowance,
    other_allowance,
    total_advances,
    total_deductions,
    gross_salary,
    net_salary,
    remarks,
    legacy_salary_id,
    created_at,
    updated_at
)
SELECT
    sr.employee_id,
    sr.year                                        AS period_year,
    sr.month                                       AS period_month,
    CASE WHEN sr.is_paid THEN 'paid' ELSE 'draft' END AS status,
    sr.basic_salary,
    COALESCE(sr.total_programs, 0)                 AS total_programs,
    0                                              AS per_program_rate,
    COALESCE(sr.program_allowance, 0)              AS program_allowance,
    COALESCE(sr.other_allowance, 0)                AS other_allowance,
    COALESCE(sr.total_advances, 0)                 AS total_advances,
    COALESCE(sr.total_deductions, 0)               AS total_deductions,
    -- gross = basic + allowances
    COALESCE(sr.basic_salary, 0)
        + COALESCE(sr.program_allowance, 0)
        + COALESCE(sr.other_allowance, 0)          AS gross_salary,
    COALESCE(sr.net_salary, 0)                     AS net_salary,
    COALESCE(sr.remarks, 'Migrated from wbom_salary_records') AS remarks,
    sr.salary_id                                   AS legacy_salary_id,
    sr.created_at,
    sr.updated_at
FROM wbom_salary_records sr
WHERE NOT EXISTS (
    SELECT 1
    FROM wbom_payroll_runs pr
    WHERE pr.employee_id  = sr.employee_id
      AND pr.period_year  = sr.year
      AND pr.period_month = sr.month
)
ON CONFLICT DO NOTHING;

-- ── 3. Index for fast lookups by provenance ──────────────────
CREATE INDEX IF NOT EXISTS idx_payroll_runs_legacy_salary
    ON wbom_payroll_runs (legacy_salary_id)
    WHERE legacy_salary_id IS NOT NULL;

-- ── 4. Verify migration (informational) ─────────────────────
-- SELECT COUNT(*) FROM wbom_salary_records;            -- source
-- SELECT COUNT(*) FROM wbom_payroll_runs;              -- destination
