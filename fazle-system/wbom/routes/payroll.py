# ============================================================
# WBOM — Payroll Run Routes  (Sprint-1 P0-01 / P0-02 / P0-03)
# ============================================================
# P0-01:  POST  /payroll/compute          dry-run formula (no DB write)
#         POST  /payroll/runs             create draft run
#         GET   /payroll/runs             list runs
#         GET   /payroll/runs/{id}        run detail + items
#         GET   /payroll/runs/{id}/log    approval audit log
#
# P0-02:  POST  /payroll/runs/{id}/submit   draft → reviewed
#         POST  /payroll/runs/{id}/approve  reviewed → approved
#         POST  /payroll/runs/{id}/lock     approved → locked
#         POST  /payroll/runs/{id}/pay      locked → paid
#         POST  /payroll/runs/{id}/cancel   cancel any non-paid run
#         POST  /payroll/runs/{id}/correct  cancel + recompute new draft
#
# P0-03:  payout_idempotency_key guard enforced in /pay endpoint
# ============================================================
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from database import audit_log
from models import (
    PayrollActionRequest,
    PayrollApprovalLogEntry,
    PayrollComputeResponse,
    PayrollCorrectRequest,
    PayrollPayRequest,
    PayrollRunCreate,
    PayrollRunResponse,
)
from services.payroll_engine import (
    check_payout_idempotency,
    compute_payroll,
    correct_payroll_run,
    create_payroll_run,
    get_payroll_run,
    get_payroll_run_approval_log,
    list_payroll_runs,
    transition_run,
)

router = APIRouter(prefix="/payroll", tags=["payroll"])


# ── P0-01: Dry-run compute ────────────────────────────────────

@router.get("/compute", response_model=PayrollComputeResponse)
def dry_run_compute(
    employee_id: int = Query(...),
    period_year: int = Query(..., ge=2020, le=2099),
    period_month: int = Query(..., ge=1, le=12),
    per_program_rate: Optional[Decimal] = Query(None),
):
    """Deterministic formula preview — no database writes.

    Returns the full breakdown that *would* be stored if a run were created.
    Safe to call repeatedly with the same inputs.
    """
    try:
        result = compute_payroll(employee_id, period_month, period_year, per_program_rate)
    except ValueError as exc:
        raise HTTPException(404, str(exc))
    return result


# ── P0-01: Create draft run ───────────────────────────────────

@router.post("/runs", response_model=PayrollRunResponse, status_code=201)
def create_run(req: PayrollRunCreate):
    """Compute payroll and persist as a draft run.

    P0-03: Returns HTTP 409 if a non-cancelled run already exists for this
    employee + period.
    """
    try:
        run = create_payroll_run(
            employee_id=req.employee_id,
            month=req.period_month,
            year=req.period_year,
            computed_by=req.computed_by or "system",
            per_program_rate=req.per_program_rate,
            remarks=req.remarks,
        )
    except ValueError as exc:
        msg = str(exc)
        if "already exists" in msg:
            raise HTTPException(409, detail={"error": "duplicate_run", "message": msg})
        raise HTTPException(404, msg)
    return run


# ── P0-01: List runs ──────────────────────────────────────────

@router.get("/runs")
def list_runs(
    employee_id: Optional[int] = Query(None),
    period_year: Optional[int] = Query(None, ge=2020, le=2099),
    period_month: Optional[int] = Query(None, ge=1, le=12),
    status: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    rows = list_payroll_runs(
        employee_id=employee_id,
        period_year=period_year,
        period_month=period_month,
        status=status,
        limit=limit,
        offset=offset,
    )
    return {"count": len(rows), "offset": offset, "limit": limit, "items": rows}


# ── P0-01: Get run detail with items ─────────────────────────

@router.get("/runs/{run_id}", response_model=PayrollRunResponse)
def get_run(run_id: int):
    run = get_payroll_run(run_id)
    if not run:
        raise HTTPException(404, f"Payroll run {run_id} not found")
    return run


# ── P0-02: Approval audit log ────────────────────────────────

@router.get("/runs/{run_id}/log")
def get_run_log(run_id: int):
    entries = get_payroll_run_approval_log(run_id)
    if not entries and not get_payroll_run(run_id):
        raise HTTPException(404, f"Payroll run {run_id} not found")
    return {"run_id": run_id, "entries": entries}


# ── P0-02: State transitions ──────────────────────────────────

@router.post("/runs/{run_id}/submit")
def submit_run(run_id: int, req: PayrollActionRequest):
    """draft → reviewed"""
    try:
        updated = transition_run(run_id, "submit", actor=req.actor, reason=req.reason)
    except ValueError as exc:
        _raise_transition_error(exc)
    return {"run_id": run_id, "status": updated.get("status"), "actor": req.actor}


@router.post("/runs/{run_id}/approve")
def approve_run(run_id: int, req: PayrollActionRequest):
    """reviewed → approved"""
    try:
        updated = transition_run(run_id, "approve", actor=req.actor, reason=req.reason)
    except ValueError as exc:
        _raise_transition_error(exc)
    return {"run_id": run_id, "status": updated.get("status"), "actor": req.actor}


@router.post("/runs/{run_id}/lock")
def lock_run(run_id: int, req: PayrollActionRequest):
    """approved → locked.

    Once locked the run is immutable. Edits require the /correct endpoint.
    """
    try:
        updated = transition_run(run_id, "lock", actor=req.actor, reason=req.reason)
    except ValueError as exc:
        _raise_transition_error(exc)
    return {"run_id": run_id, "status": updated.get("status"), "actor": req.actor}


@router.post("/runs/{run_id}/pay")
def pay_run(run_id: int, req: PayrollPayRequest):
    """locked → paid.

    P0-03: If payout_idempotency_key is provided and was already used,
    returns HTTP 409 with the existing run instead of creating a duplicate.
    """
    # P0-03: idempotency pre-check (before any DB mutation)
    if req.payout_idempotency_key:
        existing = check_payout_idempotency(req.payout_idempotency_key)
        if existing:
            return {
                "duplicate": True,
                "existing_run_id": existing["run_id"],
                "existing_status": existing["status"],
                "message": "Duplicate payout attempt blocked — idempotency key already used",
            }

    extra = {
        "payment_method": req.payment_method,
        "payment_reference": req.payment_reference,
        "payout_idempotency_key": req.payout_idempotency_key,
    }
    try:
        updated = transition_run(
            run_id, "pay", actor=req.actor, reason=req.reason, extra=extra
        )
    except ValueError as exc:
        _raise_transition_error(exc)
    return {"run_id": run_id, "status": updated.get("status"), "actor": req.actor,
            "payment_method": updated.get("payment_method"),
            "paid_at": updated.get("paid_at")}


@router.post("/runs/{run_id}/cancel")
def cancel_run(run_id: int, req: PayrollActionRequest):
    """Cancel a non-paid run."""
    try:
        updated = transition_run(run_id, "cancel", actor=req.actor, reason=req.reason)
    except ValueError as exc:
        _raise_transition_error(exc)
    return {"run_id": run_id, "status": updated.get("status"), "actor": req.actor}


# ── P0-03: Correction flow ────────────────────────────────────

@router.post("/runs/{run_id}/correct", status_code=201)
def correct_run(run_id: int, req: PayrollCorrectRequest):
    """Cancel a draft/reviewed run and create a recomputed draft.

    Locked/paid runs are rejected — escalate to admin for manual override.
    An immutable audit trail is written for both the cancellation and the new run.
    """
    try:
        new_run = correct_payroll_run(
            run_id=run_id,
            actor=req.actor,
            reason=req.reason,
            per_program_rate=req.per_program_rate,
        )
    except ValueError as exc:
        msg = str(exc)
        if "locked" in msg or "paid" in msg:
            raise HTTPException(409, detail={"error": "immutable_run", "message": msg})
        raise HTTPException(404, msg)
    return {
        "cancelled_run_id": run_id,
        "new_run_id": new_run.get("run_id"),
        "status": new_run.get("status"),
        "actor": req.actor,
        "run": new_run,
    }


# ── Helper ────────────────────────────────────────────────────

def _raise_transition_error(exc: ValueError) -> None:
    msg = str(exc)
    if "not found" in msg:
        raise HTTPException(404, msg)
    if "locked" in msg or "paid" in msg or "immutable" in msg:
        raise HTTPException(409, detail={"error": "immutable_run", "message": msg})
    raise HTTPException(422, detail={"error": "invalid_transition", "message": msg})
