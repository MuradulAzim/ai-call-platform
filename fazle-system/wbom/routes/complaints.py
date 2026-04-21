"""
routes/complaints.py  —  Sprint-4 Complaint + Client Retention
--------------------------------------------------------------
Prefix:  /complaints  (mounted at /api/wbom in main.py)

Endpoints:
  POST   /complaints/intake           – WhatsApp/direct complaint submission
  GET    /complaints                  – list with filters
  GET    /complaints/{id}             – detail + event log
  POST   /complaints/{id}/acknowledge – move open→acknowledged
  POST   /complaints/{id}/assign      – assign staff member
  POST   /complaints/{id}/escalate    – force escalation
  POST   /complaints/{id}/advance     – generic status transition
  POST   /complaints/{id}/resolve     – resolve with notes
  POST   /complaints/sla-check        – sweep & mark SLA breaches
  GET    /complaints/metrics          – owner KPI aggregates
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from database import execute_query, get_row
from models import (
    ComplaintIntakeRequest,
    ComplaintIntakeResponse,
    ComplaintAssignRequest,
    ComplaintEscalateRequest,
    ComplaintAdvanceRequest,
    ComplaintResolveRequest,
    ComplaintMetricsResponse,
)
from services.complaints import (
    ingest_complaint,
    acknowledge_complaint,
    assign_complaint,
    escalate_complaint,
    advance_complaint_status,
    resolve_complaint,
    check_sla_breaches,
    get_complaint_metrics,
    VALID_CLIENT_CATEGORIES,
    VALID_EMPLOYEE_CATEGORIES,
)

router = APIRouter(prefix="/complaints", tags=["complaints"])


# ── Intake ────────────────────────────────────────────────────────────────────

@router.post("/intake", response_model=ComplaintIntakeResponse, status_code=201)
def intake(body: ComplaintIntakeRequest):
    valid_cats = (
        VALID_CLIENT_CATEGORIES
        if body.complaint_type == "client"
        else VALID_EMPLOYEE_CATEGORIES
    )
    if body.category not in valid_cats:
        raise HTTPException(
            status_code=422,
            detail=f"Category '{body.category}' invalid for type '{body.complaint_type}'. "
                   f"Valid: {sorted(valid_cats)}",
        )
    result = ingest_complaint(
        complaint_type=body.complaint_type,
        category=body.category,
        description=body.description,
        reporter_phone=body.reporter_phone,
        reporter_name=body.reporter_name,
        client_id=body.client_id,
        employee_id=body.employee_id,
        source=body.source,
    )
    return result


# ── List ──────────────────────────────────────────────────────────────────────

@router.get("/")
def list_complaints(
    complaint_type: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    priority: Optional[str] = Query(None),
    assigned_to: Optional[str] = Query(None),
    sla_breached: Optional[bool] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    where_clauses = ["1=1"]
    params: list = []
    if complaint_type:
        where_clauses.append("complaint_type = %s")
        params.append(complaint_type)
    if status:
        where_clauses.append("status = %s")
        params.append(status)
    if priority:
        where_clauses.append("priority = %s")
        params.append(priority)
    if assigned_to:
        where_clauses.append("assigned_to = %s")
        params.append(assigned_to)
    if sla_breached is not None:
        where_clauses.append("sla_breached = %s")
        params.append(sla_breached)

    where = " AND ".join(where_clauses)
    params.extend([limit, offset])

    rows = execute_query(
        f"""
        SELECT complaint_id, complaint_type, category, description,
               priority, status, sla_hours, sla_due_at, sla_breached,
               reporter_phone, reporter_name, assigned_to, assigned_at,
               resolved_at, source, created_at
        FROM wbom_complaints
        WHERE {where}
        ORDER BY
            CASE priority
                WHEN 'critical' THEN 1 WHEN 'high' THEN 2
                WHEN 'medium'   THEN 3 ELSE 4
            END,
            created_at DESC
        LIMIT %s OFFSET %s
        """,
        tuple(params),
    )

    count_row = execute_query(
        f"SELECT COUNT(*) AS cnt FROM wbom_complaints WHERE {where}",
        tuple(params[:-2]),
    )
    total = int(count_row[0]["cnt"]) if count_row else 0

    return {"items": [dict(r) for r in rows], "total": total}


# ── Detail ────────────────────────────────────────────────────────────────────

@router.get("/{complaint_id}")
def get_complaint(complaint_id: int):
    row = get_row("wbom_complaints", "complaint_id", complaint_id)
    if not row:
        raise HTTPException(status_code=404, detail="Complaint not found")

    events = execute_query(
        """
        SELECT event_id, event_type, actor, from_status, to_status, notes, created_at
        FROM   wbom_complaint_events
        WHERE  complaint_id = %s
        ORDER  BY created_at ASC
        """,
        (complaint_id,),
    )
    result = dict(row)
    result["events"] = [dict(e) for e in events]
    return result


# ── Acknowledge ───────────────────────────────────────────────────────────────

@router.post("/{complaint_id}/acknowledge")
def ack(complaint_id: int, actor: str = Query("system")):
    try:
        return acknowledge_complaint(complaint_id, actor=actor)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


# ── Assign ────────────────────────────────────────────────────────────────────

@router.post("/{complaint_id}/assign")
def assign(complaint_id: int, body: ComplaintAssignRequest):
    try:
        return assign_complaint(complaint_id, body.staff_name, actor=body.actor)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


# ── Escalate ──────────────────────────────────────────────────────────────────

@router.post("/{complaint_id}/escalate")
def escalate(complaint_id: int, body: ComplaintEscalateRequest):
    try:
        return escalate_complaint(complaint_id, body.reason, actor=body.actor)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


# ── Advance ───────────────────────────────────────────────────────────────────

@router.post("/{complaint_id}/advance")
def advance(complaint_id: int, body: ComplaintAdvanceRequest):
    try:
        return advance_complaint_status(
            complaint_id, body.to_status, actor=body.actor, notes=body.notes
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


# ── Resolve ───────────────────────────────────────────────────────────────────

@router.post("/{complaint_id}/resolve")
def resolve(complaint_id: int, body: ComplaintResolveRequest):
    try:
        return resolve_complaint(
            complaint_id, body.resolution_notes, actor=body.actor
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


# ── SLA sweep ─────────────────────────────────────────────────────────────────

@router.post("/sla-check")
def sla_check():
    breached = check_sla_breaches()
    return {"breached_count": len(breached), "complaints": breached}


# ── Metrics ───────────────────────────────────────────────────────────────────

@router.get("/metrics", response_model=ComplaintMetricsResponse)
def metrics():
    return get_complaint_metrics()
