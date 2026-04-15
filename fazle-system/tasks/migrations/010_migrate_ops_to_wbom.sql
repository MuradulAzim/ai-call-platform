-- ============================================================
-- Migration 010 — Migrate ops_employees/ops_payments → WBOM tables
-- Also auto-creates missing employees from orphan payments
-- ============================================================

BEGIN;

-- ────────────────────────────────────────────────────────────
-- Step 1: Normalize & insert ops_employees → wbom_employees
-- ────────────────────────────────────────────────────────────
INSERT INTO wbom_employees (
    employee_mobile, employee_name, designation,
    status, created_at, updated_at
)
SELECT
    mobile,
    name,
    'Escort',          -- all ops roles are 'escort'
    'Active',
    COALESCE(created_at, NOW()),
    COALESCE(updated_at, NOW())
FROM ops_employees
ON CONFLICT (employee_mobile) DO NOTHING;

-- Step 1b: Create employees from orphan payment records
-- (employee_id not in ops_employees but referenced in ops_payments)
INSERT INTO wbom_employees (
    employee_mobile, employee_name, designation,
    status, created_at, updated_at
)
SELECT DISTINCT
    CASE
        WHEN op.employee_id ~ '^0' THEN op.employee_id
        ELSE '0' || op.employee_id
    END,
    op.name,
    'Escort',
    'Active',
    NOW(),
    NOW()
FROM ops_payments op
WHERE op.employee_id NOT IN (SELECT employee_id FROM ops_employees)
  AND op.name IS NOT NULL
ON CONFLICT (employee_mobile) DO NOTHING;

-- ────────────────────────────────────────────────────────────
-- Step 2: Migrate ops_payments → wbom_cash_transactions
-- ────────────────────────────────────────────────────────────
INSERT INTO wbom_cash_transactions (
    employee_id, transaction_type, amount,
    payment_method, payment_mobile,
    transaction_date, transaction_time,
    status, remarks, created_by
)
SELECT
    we.employee_id,
    'Other',                    -- all ops categories are 'general' → 'Other'
    op.amount,
    CASE op.method
        WHEN 'B' THEN 'Bkash'
        WHEN 'N' THEN 'Nagad'
        ELSE 'Cash'
    END,
    op.payment_number,
    op.payment_date,
    COALESCE(op.created_at, NOW()),
    'Completed',                -- all ops status is 'running' but these are historical records
    op.remarks,
    op.paid_by
FROM ops_payments op
JOIN wbom_employees we
  ON we.employee_mobile = CASE
        WHEN op.employee_id ~ '^0' THEN op.employee_id
        ELSE '0' || op.employee_id
     END;

-- ────────────────────────────────────────────────────────────
-- Verify counts
-- ────────────────────────────────────────────────────────────
DO $$
DECLARE
    emp_count INT;
    txn_count INT;
BEGIN
    SELECT COUNT(*) INTO emp_count FROM wbom_employees;
    SELECT COUNT(*) INTO txn_count FROM wbom_cash_transactions;
    RAISE NOTICE 'Migration complete: % employees, % transactions', emp_count, txn_count;
END $$;

COMMIT;
