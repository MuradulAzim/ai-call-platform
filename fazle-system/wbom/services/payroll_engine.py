# ============================================================
# WBOM — Payroll Run Engine  (Sprint-1 P0-01 / P0-02 / P0-03)
# ============================================================
# P0-01: Deterministic formula computation pipeline
# P0-02: Approval state machine + lock enforcement
# P0-03: Idempotency + duplicate payout guard
# ============================================================
from __future__ import annotations

import json
import logging
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Optional

import psycopg2.extras

from config import settings as _cfg
from database import (
    audit_log,
    execute_query,
    get_conn,
    get_row,
    update_row,
)

logger = logging.getLogger("wbom.payroll_engine")

# ── Status state machine ──────────────────────────────────────
# Maps action → required current status → new status
_TRANSITIONS: dict[str, tuple[str, str]] = {
    "submit":  ("draft",    "reviewed"),
    "approve": ("reviewed", "approved"),
    "lock":    ("approved", "locked"),
    "pay":     ("locked",   "paid"),
}

# 'paid' runs reject all further mutations (the run is final).
# 'locked' runs are intentionally NOT in this set: the only valid next
# action from 'locked' is 'pay', which the state machine handles normally.
_IMMUTABLE_STATUSES = frozenset({"paid"})


# ── P0-01: Pure formula computation (zero DB writes) ─────────

def compute_payroll(
    employee_id: int,
    month: int,
    year: int,
    per_program_rate: Optional[Decimal] = None,
) -> dict:
    """Deterministic payroll breakdown — no side effects.

    Same inputs always produce same output.
    Raises ValueError if employee does not exist.
    """
    if per_program_rate is None:
        per_program_rate = Decimal(str(_cfg.per_program_allowance))

    employee = get_row("wbom_employees", "employee_id", employee_id)
    if not employee:
        raise ValueError(f"Employee {employee_id} not found")

    basic_salary = Decimal(str(employee.get("basic_salary") or 0))

    # Count completed escort programs in period
    rows = execute_query(
        """
        SELECT COUNT(*) AS total
        FROM wbom_escort_programs
        WHERE escort_employee_id = %s
          AND EXTRACT(MONTH FROM program_date) = %s
          AND EXTRACT(YEAR  FROM program_date) = %s
          AND status = 'Completed'
        """,
        (employee_id, month, year),
    )
    total_programs: int = int(rows[0]["total"]) if rows else 0
    program_allowance = Decimal(str(total_programs)) * per_program_rate

    # Advances: Advance + Food + Conveyance transactions
    adv = execute_query(
        """
        SELECT COALESCE(SUM(amount), 0) AS total
        FROM wbom_cash_transactions
        WHERE employee_id = %s
          AND EXTRACT(MONTH FROM transaction_date) = %s
          AND EXTRACT(YEAR  FROM transaction_date) = %s
          AND transaction_type IN ('Advance', 'Food', 'Conveyance')
          AND status = 'Completed'
        """,
        (employee_id, month, year),
    )
    total_advances = Decimal(str(adv[0]["total"])) if adv else Decimal("0")

    # Deductions
    ded = execute_query(
        """
        SELECT COALESCE(SUM(amount), 0) AS total
        FROM wbom_cash_transactions
        WHERE employee_id = %s
          AND EXTRACT(MONTH FROM transaction_date) = %s
          AND EXTRACT(YEAR  FROM transaction_date) = %s
          AND transaction_type = 'Deduction'
          AND status = 'Completed'
        """,
        (employee_id, month, year),
    )
    total_deductions = Decimal(str(ded[0]["total"])) if ded else Decimal("0")

    other_allowance = Decimal("0")
    gross_salary = basic_salary + program_allowance + other_allowance
    net_salary = gross_salary - total_advances - total_deductions

    # Build traceable line items
    items: list[dict] = [
        {
            "component_type": "basic_salary",
            "component_label": "Basic Salary",
            "amount": basic_salary,
            "sign": "+",
        },
    ]
    if total_programs > 0:
        items.append({
            "component_type": "program_allowance",
            "component_label": f"Program Allowance ({total_programs} × {per_program_rate})",
            "amount": program_allowance,
            "sign": "+",
        })
    if total_advances > 0:
        items.append({
            "component_type": "advance",
            "component_label": "Advances (Advance + Food + Conveyance)",
            "amount": total_advances,
            "sign": "-",
        })
    if total_deductions > 0:
        items.append({
            "component_type": "deduction",
            "component_label": "Deductions",
            "amount": total_deductions,
            "sign": "-",
        })

    return {
        "employee_id": employee_id,
        "employee_name": employee.get("employee_name"),
        "period_year": year,
        "period_month": month,
        "basic_salary": basic_salary,
        "total_programs": total_programs,
        "per_program_rate": per_program_rate,
        "program_allowance": program_allowance,
        "other_allowance": other_allowance,
        "total_advances": total_advances,
        "total_deductions": total_deductions,
        "gross_salary": gross_salary,
        "net_salary": net_salary,
        "items": items,
    }


# ── P0-01 + P0-03: Create payroll run (draft) ────────────────

def create_payroll_run(
    employee_id: int,
    month: int,
    year: int,
    computed_by: str = "system",
    per_program_rate: Optional[Decimal] = None,
    remarks: Optional[str] = None,
) -> dict:
    """Compute payroll and persist as a draft run.

    P0-03 guard: raises ValueError if a non-cancelled run already exists for
    this (employee_id, year, month) tuple.
    """
    # P0-03: duplicate run guard (also enforced by DB unique index)
    existing = execute_query(
        """
        SELECT run_id, status
        FROM wbom_payroll_runs
        WHERE employee_id = %s AND period_year = %s AND period_month = %s
          AND status != 'cancelled'
        LIMIT 1
        """,
        (employee_id, year, month),
    )
    if existing:
        raise ValueError(
            f"Run {existing[0]['run_id']} already exists for this period "
            f"(status={existing[0]['status']}). Cancel it before creating a new one."
        )

    breakdown = compute_payroll(employee_id, month, year, per_program_rate)

    # Payout target = 10th of the following month
    payout_year = year + 1 if month == 12 else year
    payout_month = 1 if month == 12 else month + 1
    payout_target = date(payout_year, payout_month, 10)

    run_payload = {
        "employee_id": employee_id,
        "period_year": year,
        "period_month": month,
        "status": "draft",
        "basic_salary": breakdown["basic_salary"],
        "total_programs": breakdown["total_programs"],
        "per_program_rate": breakdown["per_program_rate"],
        "program_allowance": breakdown["program_allowance"],
        "other_allowance": breakdown["other_allowance"],
        "total_advances": breakdown["total_advances"],
        "total_deductions": breakdown["total_deductions"],
        "gross_salary": breakdown["gross_salary"],
        "net_salary": breakdown["net_salary"],
        "payout_target_date": payout_target.isoformat(),
        "computed_by": computed_by,
        "remarks": remarks,
    }

    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            # Insert run
            cols = list(run_payload.keys())
            placeholders = ", ".join(["%s"] * len(cols))
            cur.execute(
                f"INSERT INTO wbom_payroll_runs ({', '.join(cols)}) "
                f"VALUES ({placeholders}) RETURNING *",
                list(run_payload.values()),
            )
            run = dict(cur.fetchone())
            run_id = run["run_id"]

            # Insert line items
            for item in breakdown["items"]:
                cur.execute(
                    """
                    INSERT INTO wbom_payroll_run_items
                        (run_id, component_type, component_label, amount, sign)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (
                        run_id,
                        item["component_type"],
                        item["component_label"],
                        item["amount"],
                        item["sign"],
                    ),
                )

            # Initial approval log entry
            cur.execute(
                """
                INSERT INTO wbom_payroll_approval_log
                    (run_id, action, actor, from_status, to_status, payload_json)
                VALUES (%s, 'created', %s, NULL, 'draft', %s)
                """,
                (
                    run_id,
                    computed_by,
                    json.dumps({"net_salary": str(breakdown["net_salary"])}, default=str),
                ),
            )
        conn.commit()

    run["items"] = breakdown["items"]
    audit_log(
        "payroll.run.created",
        actor=computed_by,
        entity_type="payroll_run",
        entity_id=run_id,
        payload={"employee_id": employee_id, "period": f"{year}-{month:02d}",
                 "net_salary": str(breakdown["net_salary"])},
    )
    logger.info("Created payroll run %d for employee %d period %d-%02d",
                run_id, employee_id, year, month)
    return run


# ── P0-01: Query helpers ──────────────────────────────────────

def get_payroll_run(run_id: int) -> Optional[dict]:
    """Fetch run with its line items."""
    run = get_row("wbom_payroll_runs", "run_id", run_id)
    if not run:
        return None
    items = execute_query(
        "SELECT * FROM wbom_payroll_run_items WHERE run_id = %s ORDER BY item_id",
        (run_id,),
    )
    run["items"] = items
    return run


def list_payroll_runs(
    employee_id: Optional[int] = None,
    period_year: Optional[int] = None,
    period_month: Optional[int] = None,
    status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> list[dict]:
    conditions = ["1=1"]
    params: list = []
    if employee_id:
        conditions.append("employee_id = %s")
        params.append(employee_id)
    if period_year:
        conditions.append("period_year = %s")
        params.append(period_year)
    if period_month:
        conditions.append("period_month = %s")
        params.append(period_month)
    if status:
        conditions.append("status = %s")
        params.append(status)
    params.extend([limit, offset])
    return execute_query(
        f"SELECT * FROM wbom_payroll_runs WHERE {' AND '.join(conditions)} "
        "ORDER BY period_year DESC, period_month DESC, run_id DESC "
        "LIMIT %s OFFSET %s",
        tuple(params),
    )


def get_payroll_run_approval_log(run_id: int) -> list[dict]:
    return execute_query(
        "SELECT * FROM wbom_payroll_approval_log WHERE run_id = %s ORDER BY created_at",
        (run_id,),
    )


# ── P0-02: Approval state machine ────────────────────────────

def transition_run(
    run_id: int,
    action: str,
    actor: str,
    reason: Optional[str] = None,
    extra: Optional[dict] = None,
) -> dict:
    """Apply action to a payroll run following the state machine.

    Valid actions: submit, approve, lock, pay, cancel
    Raises ValueError on invalid transitions or locked runs.
    Returns the updated run dict.
    """
    if action not in (*_TRANSITIONS, "cancel"):
        raise ValueError(
            f"Unknown action '{action}'. Valid: {sorted([*_TRANSITIONS, 'cancel'])}"
        )

    run = get_row("wbom_payroll_runs", "run_id", run_id)
    if not run:
        raise ValueError(f"Payroll run {run_id} not found")

    current = run["status"]

    # P0-02: paid run is final — no further mutations allowed
    if current in _IMMUTABLE_STATUSES and action != "cancel":
        raise ValueError(
            f"Run {run_id} is '{current}' — no mutations allowed. "
            "Use the correction flow to create an amended run."
        )

    # locked run rejects all actions except 'pay' and 'cancel'
    if current == "locked" and action not in ("pay", "cancel"):
        raise ValueError(
            f"Run {run_id} is 'locked' — only 'pay' or 'cancel' are permitted. "
            "Use the correction flow to amend the run."
        )

    if action == "cancel":
        if current == "paid":
            raise ValueError("Cannot cancel a paid payroll run")
        new_status = "cancelled"
    else:
        required_from, new_status = _TRANSITIONS[action]
        if current != required_from:
            raise ValueError(
                f"Action '{action}' requires status '{required_from}', "
                f"but run {run_id} is '{current}'"
            )

    # Build update payload
    update_fields: dict = {"status": new_status}
    if action == "submit":
        update_fields["submitted_by"] = actor
    elif action == "approve":
        update_fields["approved_by"] = actor
    elif action == "lock":
        update_fields["locked_by"] = actor
    elif action == "pay":
        update_fields["paid_by"] = actor
        update_fields["paid_at"] = datetime.now(timezone.utc).isoformat()
        if extra:
            if extra.get("payment_method"):
                update_fields["payment_method"] = extra["payment_method"]
            if extra.get("payment_reference"):
                update_fields["payment_reference"] = extra["payment_reference"]
            if extra.get("payout_idempotency_key"):
                # P0-03: store idempotency key — DB unique index prevents duplicates
                update_fields["payout_idempotency_key"] = extra["payout_idempotency_key"]
    elif action == "cancel" and reason:
        update_fields["correction_reason"] = reason

    updated = update_row("wbom_payroll_runs", "run_id", run_id, update_fields)

    # Append immutable audit log entry
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO wbom_payroll_approval_log
                    (run_id, action, actor, from_status, to_status, reason, payload_json)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    run_id,
                    action,
                    actor,
                    current,
                    new_status,
                    reason,
                    json.dumps(extra or {}, default=str),
                ),
            )
        conn.commit()

    audit_log(
        f"payroll.run.{action}",
        actor=actor,
        entity_type="payroll_run",
        entity_id=run_id,
        payload={"from": current, "to": new_status},
    )
    logger.info("Payroll run %d: %s → %s (actor=%s)", run_id, current, new_status, actor)
    # Structured domain audit events (S6-03)
    try:
        from services.audit_events import log_payroll_approved, log_payroll_paid
        if action == "approve":
            total = float(updated.get("total_net_pay") or 0)
            log_payroll_approved(run_id, actor, total)
        elif action == "pay":
            count = int(updated.get("employee_count") or 0)
            log_payroll_paid(run_id, actor, count)
    except Exception:
        pass  # never let logging break the caller
    return updated or {}


# ── P0-03: Correction flow ────────────────────────────────────

def correct_payroll_run(
    run_id: int,
    actor: str,
    reason: str,
    per_program_rate: Optional[Decimal] = None,
) -> dict:
    """Cancel an existing draft/reviewed run and recompute a fresh draft.

    Locked or paid runs cannot be corrected via this flow — they require
    a manual override with explicit approval.
    """
    run = get_row("wbom_payroll_runs", "run_id", run_id)
    if not run:
        raise ValueError(f"Payroll run {run_id} not found")

    if run["status"] in ("locked", "paid"):
        raise ValueError(
            f"Run {run_id} is '{run['status']}' — locked/paid runs cannot be "
            "corrected via this flow. Cancel the run first, then create a new draft."
        )

    # Cancel old run (preserves audit trail)
    transition_run(run_id, "cancel", actor=actor, reason=reason)

    # Create fresh recomputed draft
    new_run = create_payroll_run(
        employee_id=run["employee_id"],
        month=run["period_month"],
        year=run["period_year"],
        computed_by=actor,
        per_program_rate=per_program_rate,
        remarks=f"Correction of run #{run_id}: {reason}",
    )
    return new_run


# ── P0-03: Payout idempotency check ──────────────────────────

def check_payout_idempotency(payout_idempotency_key: str) -> Optional[dict]:
    """Return the existing run if this key was already used for payout.

    Returns None if the key is unused (safe to proceed).
    """
    rows = execute_query(
        "SELECT * FROM wbom_payroll_runs WHERE payout_idempotency_key = %s LIMIT 1",
        (payout_idempotency_key,),
    )
    return rows[0] if rows else None
