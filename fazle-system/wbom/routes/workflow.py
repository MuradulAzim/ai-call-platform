# ============================================================
# WBOM — Workflow & Unified Approvals Routes
# Phase-2: unified approval queue + task actions
# ============================================================
from fastapi import APIRouter, HTTPException, Query

from database import execute_query, get_row, update_row, update_row_no_ts, insert_row, audit_log
from models import (
    WorkflowApprovalsListResponse,
    WorkflowCaseDetailResponse,
    WorkflowCaseListResponse,
    WorkflowCaseStatusTransitionRequest,
    WorkflowCaseStatusTransitionResponse,
    WorkflowEscalationActionRequest,
    WorkflowEscalationActionResponse,
    WorkflowEscalationMonitorResponse,
    WorkflowStagingPaymentApprovalResponse,
    WorkflowTaskApprovalResponse,
)
from services.wbom_logger import handle_errors

router = APIRouter(prefix="/workflow", tags=["workflow"])


_CASE_STATUS_TRANSITIONS = {
    "open": {"in_progress", "waiting_customer", "waiting_internal", "cancelled"},
    "in_progress": {"waiting_customer", "waiting_internal", "resolved", "cancelled"},
    "waiting_customer": {"in_progress", "resolved", "cancelled"},
    "waiting_internal": {"in_progress", "resolved", "cancelled"},
    "resolved": {"closed", "in_progress"},
    "closed": set(),
    "cancelled": set(),
}


@router.get("/cases", response_model=WorkflowCaseListResponse)
@handle_errors
def list_cases(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    status: str = Query(""),
    case_type: str = Query(""),
    severity: str = Query(""),
    priority: str = Query(""),
    owner_role: str = Query(""),
    contact_id: int = Query(0, ge=0),
    employee_id: int = Query(0, ge=0),
    q: str = Query("", description="Search in title or description"),
    include_closed: bool = False,
):
    """List cases with filters and pagination."""
    where_parts = ["1=1"]
    params = []

    if not include_closed:
        where_parts.append("c.status NOT IN ('resolved', 'closed', 'cancelled')")

    if status:
        where_parts.append("c.status = %s")
        params.append(status)
    if case_type:
        where_parts.append("c.case_type = %s")
        params.append(case_type)
    if severity:
        where_parts.append("c.severity = %s")
        params.append(severity)
    if priority:
        where_parts.append("c.priority = %s")
        params.append(priority)
    if owner_role:
        where_parts.append("c.owner_role = %s")
        params.append(owner_role)
    if contact_id:
        where_parts.append("c.contact_id = %s")
        params.append(contact_id)
    if employee_id:
        where_parts.append("c.employee_id = %s")
        params.append(employee_id)
    if q:
        where_parts.append("(c.title ILIKE %s OR COALESCE(c.description, '') ILIKE %s)")
        like = f"%{q}%"
        params.extend([like, like])

    where_sql = " AND ".join(where_parts)

    rows = execute_query(
        f"""
        SELECT
            c.case_id,
            c.case_type,
            c.source_platform,
            c.source_channel,
            c.contact_id,
            c.employee_id,
            c.related_program_id,
            c.title,
            c.description,
            c.priority,
            c.severity,
            c.status,
            c.owner_role,
            c.owner_user,
            c.opened_at,
            c.first_response_at,
            c.due_at,
            c.resolved_at,
            c.closed_at,
            c.metadata_json,
            c.created_at,
            c.updated_at,
            (
                SELECT COUNT(*)
                FROM wbom_workflow_tasks wt
                WHERE wt.case_id = c.case_id
                  AND wt.task_status IN ('pending', 'in_progress')
            ) AS pending_tasks,
            (
                SELECT COUNT(*)
                FROM wbom_case_events ev
                WHERE ev.case_id = c.case_id
            ) AS event_count
        FROM wbom_cases c
        WHERE {where_sql}
        ORDER BY c.opened_at DESC, c.case_id DESC
        LIMIT %s OFFSET %s
        """,
        tuple(params + [limit, offset]),
    )

    count_row = execute_query(
        f"SELECT COUNT(*) AS total FROM wbom_cases c WHERE {where_sql}",
        tuple(params),
    )
    total = count_row[0]["total"] if count_row else 0

    return {
        "success": True,
        "count": len(rows),
        "total": total,
        "limit": limit,
        "offset": offset,
        "items": rows,
    }


@router.get("/cases/{case_id}", response_model=WorkflowCaseDetailResponse)
@handle_errors
def get_case_detail(
    case_id: int,
    include_events: bool = True,
    include_tasks: bool = True,
    events_limit: int = Query(100, ge=1, le=500),
    tasks_limit: int = Query(100, ge=1, le=500),
):
    """Get case detail, optionally with event timeline and tasks."""
    case_row = get_row("wbom_cases", "case_id", case_id)
    if not case_row:
        raise HTTPException(404, "Case not found")

    events = []
    tasks = []

    if include_events:
        events = execute_query(
            """
            SELECT
                event_id,
                case_id,
                event_type,
                actor_type,
                actor_id,
                event_source,
                message_id,
                old_status,
                new_status,
                note,
                payload_json,
                created_at
            FROM wbom_case_events
            WHERE case_id = %s
            ORDER BY created_at DESC, event_id DESC
            LIMIT %s
            """,
            (case_id, events_limit),
        )

    if include_tasks:
        tasks = execute_query(
            """
            SELECT
                workflow_task_id,
                case_id,
                task_type,
                task_title,
                task_status,
                approval_required,
                assignee_role,
                assignee_user,
                requester,
                due_at,
                completed_at,
                completion_note,
                correlation_key,
                payload_json,
                created_at,
                updated_at
            FROM wbom_workflow_tasks
            WHERE case_id = %s
            ORDER BY created_at DESC, workflow_task_id DESC
            LIMIT %s
            """,
            (case_id, tasks_limit),
        )

    return {
        "success": True,
        "case": case_row,
        "events": events,
        "tasks": tasks,
        "event_count": len(events),
        "task_count": len(tasks),
    }


@router.get("/escalations/monitor", response_model=WorkflowEscalationMonitorResponse)
@handle_errors
def escalation_monitor(
    overdue_only: bool = False,
    window_minutes: int = Query(120, ge=1, le=1440),
    limit: int = Query(100, ge=1, le=500),
):
    """Monitor for SLA risk/overdue cases and overdue workflow tasks."""
    case_filter = "c.status NOT IN ('resolved', 'closed', 'cancelled')"
    if overdue_only:
        case_filter += " AND c.due_at IS NOT NULL AND c.due_at < NOW()"

    cases = execute_query(
        f"""
        SELECT
            c.case_id,
            c.case_type,
            c.title,
            c.status,
            c.priority,
            c.severity,
            c.owner_role,
            c.owner_user,
            c.opened_at,
            c.due_at,
            CASE
                WHEN c.due_at IS NULL THEN 'no_due'
                WHEN c.due_at < NOW() THEN 'overdue'
                WHEN c.due_at <= NOW() + (%s || ' minutes')::interval THEN 'due_soon'
                ELSE 'within_sla'
            END AS sla_state,
            CASE
                WHEN c.due_at IS NULL THEN NULL
                ELSE CAST(EXTRACT(EPOCH FROM (NOW() - c.due_at)) / 60 AS INT)
            END AS overdue_minutes,
            CASE
                WHEN c.due_at IS NULL THEN NULL
                ELSE CAST(EXTRACT(EPOCH FROM (c.due_at - NOW())) / 60 AS INT)
            END AS minutes_to_due,
            (
                SELECT COUNT(*)
                FROM wbom_workflow_tasks wt
                WHERE wt.case_id = c.case_id
                  AND wt.task_status IN ('pending', 'in_progress')
            ) AS pending_tasks,
            (
                SELECT COALESCE(MAX(er.escalation_level), 0)
                FROM wbom_escalation_rules er
                WHERE er.active = TRUE
                  AND er.case_type = c.case_type
                  AND er.severity = c.severity
            ) AS max_escalation_level
        FROM wbom_cases c
        WHERE {case_filter}
        ORDER BY
            CASE
                WHEN c.due_at IS NULL THEN 3
                WHEN c.due_at < NOW() THEN 0
                WHEN c.due_at <= NOW() + (%s || ' minutes')::interval THEN 1
                ELSE 2
            END,
            c.due_at NULLS LAST,
            c.opened_at DESC
        LIMIT %s
        """,
        (window_minutes, window_minutes, limit),
    )

    tasks = execute_query(
        """
        SELECT
            wt.workflow_task_id,
            wt.case_id,
            wt.task_type,
            wt.task_title,
            wt.task_status,
            wt.assignee_role,
            wt.assignee_user,
            wt.due_at,
            wt.created_at,
            CAST(EXTRACT(EPOCH FROM (NOW() - wt.due_at)) / 60 AS INT) AS overdue_minutes,
            c.case_type,
            c.severity,
            c.priority,
            c.status AS case_status,
            c.title AS case_title
        FROM wbom_workflow_tasks wt
        LEFT JOIN wbom_cases c ON c.case_id = wt.case_id
        WHERE wt.task_status IN ('pending', 'in_progress')
          AND wt.due_at IS NOT NULL
          AND wt.due_at < NOW()
        ORDER BY wt.due_at ASC, wt.workflow_task_id DESC
        LIMIT %s
        """,
        (limit,),
    )

    summary = {
        "open_cases": sum(1 for c in cases if c.get("sla_state") != "overdue"),
        "overdue_cases": sum(1 for c in cases if c.get("sla_state") == "overdue"),
        "due_soon_cases": sum(1 for c in cases if c.get("sla_state") == "due_soon"),
        "overdue_tasks": len(tasks),
    }

    return {
        "success": True,
        "window_minutes": window_minutes,
        "summary": summary,
        "cases": cases,
        "tasks": tasks,
    }


@router.post("/cases/{case_id}/status", response_model=WorkflowCaseStatusTransitionResponse)
@handle_errors
def transition_case_status(
    case_id: int,
    req: WorkflowCaseStatusTransitionRequest,
):
    """Transition a case status with guardrails and timeline logging."""
    new_status = req.new_status
    changed_by = req.changed_by
    reason = req.reason

    case_row = get_row("wbom_cases", "case_id", case_id)
    if not case_row:
        raise HTTPException(404, "Case not found")

    old_status = str(case_row.get("status") or "")
    if new_status not in _CASE_STATUS_TRANSITIONS:
        raise HTTPException(400, "Invalid new_status")

    if old_status == new_status:
        return {
            "success": True,
            "case_id": case_id,
            "old_status": old_status,
            "new_status": new_status,
            "message": "Case already in requested status",
        }

    allowed = _CASE_STATUS_TRANSITIONS.get(old_status, set())
    if new_status not in allowed:
        raise HTTPException(400, f"Invalid transition: {old_status} -> {new_status}")

    update_row("wbom_cases", "case_id", case_id, {
        "status": new_status,
    })

    if new_status == "in_progress" and not case_row.get("first_response_at"):
        execute_query(
            "UPDATE wbom_cases SET first_response_at = NOW(), updated_at = NOW() WHERE case_id = %s",
            (case_id,),
        )
    if new_status == "resolved":
        execute_query(
            "UPDATE wbom_cases SET resolved_at = NOW(), updated_at = NOW() WHERE case_id = %s",
            (case_id,),
        )
    if new_status == "closed":
        execute_query(
            "UPDATE wbom_cases SET closed_at = NOW(), updated_at = NOW() WHERE case_id = %s",
            (case_id,),
        )

    insert_row("wbom_case_events", {
        "case_id": case_id,
        "event_type": "status_changed",
        "actor_type": "user",
        "actor_id": changed_by,
        "event_source": "api",
        "old_status": old_status,
        "new_status": new_status,
        "note": reason or f"Case status changed to {new_status}",
        "payload_json": {
            "changed_by": changed_by,
            "reason": reason,
        },
    })

    audit_log(
        "workflow.case_status_changed",
        actor=changed_by,
        entity_type="case",
        entity_id=case_id,
        payload={
            "old_status": old_status,
            "new_status": new_status,
            "reason": reason,
        },
    )

    updated_case = get_row("wbom_cases", "case_id", case_id)
    return {
        "success": True,
        "case_id": case_id,
        "old_status": old_status,
        "new_status": new_status,
        "case": updated_case,
    }


@router.post("/cases/{case_id}/escalate", response_model=WorkflowEscalationActionResponse)
@handle_errors
def case_escalation_action(
    case_id: int,
    req: WorkflowEscalationActionRequest,
):
    """Take escalation action for a case: acknowledge, escalate, or snooze."""
    action = req.action
    actor = req.actor
    note = req.note
    snooze_minutes = req.snooze_minutes

    case_row = get_row("wbom_cases", "case_id", case_id)
    if not case_row:
        raise HTTPException(404, "Case not found")

    metadata = dict(case_row.get("metadata_json") or {})

    if action == "acknowledge":
        metadata["escalation_ack_by"] = actor
        metadata["escalation_ack_note"] = note
        update_row("wbom_cases", "case_id", case_id, {
            "metadata_json": metadata,
        })

        insert_row("wbom_case_events", {
            "case_id": case_id,
            "event_type": "escalation_acknowledged",
            "actor_type": "user",
            "actor_id": actor,
            "event_source": "api",
            "old_status": case_row.get("status"),
            "new_status": case_row.get("status"),
            "note": note or "Escalation acknowledged",
            "payload_json": {
                "action": action,
                "actor": actor,
            },
        })

        audit_log(
            "workflow.case_escalation_acknowledged",
            actor=actor,
            entity_type="case",
            entity_id=case_id,
            payload={"note": note},
        )

        return {
            "success": True,
            "case_id": case_id,
            "action": action,
            "message": "Escalation acknowledged",
        }

    if action == "snooze":
        execute_query(
            "UPDATE wbom_cases SET due_at = NOW() + (%s || ' minutes')::interval, updated_at = NOW() WHERE case_id = %s",
            (snooze_minutes, case_id),
        )

        metadata["snoozed_by"] = actor
        metadata["snoozed_minutes"] = snooze_minutes
        metadata["snooze_note"] = note
        update_row("wbom_cases", "case_id", case_id, {
            "metadata_json": metadata,
        })

        insert_row("wbom_case_events", {
            "case_id": case_id,
            "event_type": "escalation_snoozed",
            "actor_type": "user",
            "actor_id": actor,
            "event_source": "api",
            "old_status": case_row.get("status"),
            "new_status": case_row.get("status"),
            "note": note or f"Escalation snoozed for {snooze_minutes} minutes",
            "payload_json": {
                "action": action,
                "actor": actor,
                "snooze_minutes": snooze_minutes,
            },
        })

        audit_log(
            "workflow.case_escalation_snoozed",
            actor=actor,
            entity_type="case",
            entity_id=case_id,
            payload={"snooze_minutes": snooze_minutes, "note": note},
        )

        updated = get_row("wbom_cases", "case_id", case_id)
        return {
            "success": True,
            "case_id": case_id,
            "action": action,
            "due_at": updated.get("due_at") if updated else None,
            "message": "Escalation snoozed",
        }

    # action == escalate
    current_level = int(metadata.get("escalation_level", 0) or 0)
    next_level = current_level + 1
    rule_rows = execute_query(
        """
        SELECT escalation_rule_id, escalation_level, target_role, target_user, notify_channel
        FROM wbom_escalation_rules
        WHERE active = TRUE
          AND case_type = %s
          AND severity = %s
          AND escalation_level = %s
        ORDER BY escalation_rule_id DESC
        LIMIT 1
        """,
        (case_row.get("case_type"), case_row.get("severity"), next_level),
    )

    if not rule_rows:
        return {
            "success": True,
            "case_id": case_id,
            "action": action,
            "message": "No further escalation rule configured",
            "current_level": current_level,
        }

    rule = rule_rows[0]
    metadata["escalation_level"] = next_level
    metadata["last_escalated_by"] = actor
    metadata["last_escalation_note"] = note
    metadata["last_escalation_target_role"] = rule.get("target_role")
    metadata["last_escalation_target_user"] = rule.get("target_user")

    update_row("wbom_cases", "case_id", case_id, {
        "owner_role": rule.get("target_role"),
        "owner_user": rule.get("target_user"),
        "metadata_json": metadata,
    })

    insert_row("wbom_case_events", {
        "case_id": case_id,
        "event_type": "case_escalated",
        "actor_type": "user",
        "actor_id": actor,
        "event_source": "api",
        "old_status": case_row.get("status"),
        "new_status": case_row.get("status"),
        "note": note or f"Escalated to level {next_level}",
        "payload_json": {
            "action": action,
            "from_level": current_level,
            "to_level": next_level,
            "target_role": rule.get("target_role"),
            "target_user": rule.get("target_user"),
            "notify_channel": rule.get("notify_channel"),
        },
    })

    audit_log(
        "workflow.case_escalated",
        actor=actor,
        entity_type="case",
        entity_id=case_id,
        payload={
            "from_level": current_level,
            "to_level": next_level,
            "target_role": rule.get("target_role"),
            "target_user": rule.get("target_user"),
            "note": note,
        },
    )

    return {
        "success": True,
        "case_id": case_id,
        "action": action,
        "from_level": current_level,
        "to_level": next_level,
        "target_role": rule.get("target_role"),
        "target_user": rule.get("target_user"),
        "message": "Case escalated",
    }


@router.get("/approvals/pending", response_model=WorkflowApprovalsListResponse)
@handle_errors
def list_pending_approvals(
    limit: int = Query(50, ge=1, le=200),
    include_payments: bool = True,
    include_tasks: bool = True,
):
    """Unified approval queue: workflow tasks + staged payments."""
    items = []

    if include_tasks:
        task_rows = execute_query(
            """
            SELECT
                wt.workflow_task_id AS id,
                wt.case_id,
                wt.task_type,
                wt.task_title,
                wt.task_status,
                wt.assignee_role,
                wt.due_at,
                wt.created_at,
                wt.payload_json,
                c.case_type,
                c.severity,
                c.priority,
                c.status AS case_status,
                c.title AS case_title
            FROM wbom_workflow_tasks wt
            LEFT JOIN wbom_cases c ON c.case_id = wt.case_id
            WHERE wt.approval_required = TRUE
              AND wt.task_status IN ('pending', 'in_progress')
            ORDER BY wt.due_at NULLS LAST, wt.created_at ASC
            LIMIT %s
            """,
            (limit,),
        )
        for row in task_rows:
            row["source"] = "workflow_task"
            items.append(row)

    if include_payments:
        payment_rows = execute_query(
            """
            SELECT
                id,
                employee_id,
                employee_name,
                amount,
                payment_method,
                status,
                reviewed_by,
                created_at,
                idempotency_key
            FROM wbom_staging_payments
            WHERE status IN ('pending', 'approved')
            ORDER BY created_at ASC
            LIMIT %s
            """,
            (limit,),
        )
        for row in payment_rows:
            items.append({
                "source": "staging_payment",
                "id": row["id"],
                "task_status": row["status"],
                "task_type": "payment_approval",
                "task_title": f"Approve payment for {row.get('employee_name', 'employee')}",
                "created_at": row["created_at"],
                "due_at": None,
                "payload_json": {
                    "employee_id": row.get("employee_id"),
                    "employee_name": row.get("employee_name"),
                    "amount": str(row.get("amount")),
                    "payment_method": row.get("payment_method"),
                    "idempotency_key": row.get("idempotency_key"),
                },
            })

    items.sort(key=lambda x: (x.get("due_at") is None, x.get("due_at") or x.get("created_at")))

    return {
        "success": True,
        "count": len(items),
        "items": items[:limit],
    }


@router.post("/approvals/task/{workflow_task_id}/approve", response_model=WorkflowTaskApprovalResponse)
@handle_errors
def approve_workflow_task(workflow_task_id: int, approved_by: str = Query(..., min_length=1)):
    """Approve a workflow task and append case event."""
    task = get_row("wbom_workflow_tasks", "workflow_task_id", workflow_task_id)
    if not task:
        raise HTTPException(404, "Workflow task not found")

    if task.get("task_status") in ("approved", "completed", "rejected", "cancelled"):
        return {
            "success": True,
            "workflow_task_id": workflow_task_id,
            "status": task.get("task_status"),
            "message": "Task already finalized",
        }

    update_row("wbom_workflow_tasks", "workflow_task_id", workflow_task_id, {
        "task_status": "approved",
        "assignee_user": approved_by,
    })

    # update_row writes literal values; set completed_at with explicit SQL update for timestamp correctness
    execute_query(
        "UPDATE wbom_workflow_tasks SET completed_at = NOW(), updated_at = NOW() WHERE workflow_task_id = %s",
        (workflow_task_id,),
    )

    case_id = task.get("case_id")
    if case_id:
        insert_row("wbom_case_events", {
            "case_id": case_id,
            "event_type": "task_approved",
            "actor_type": "user",
            "actor_id": approved_by,
            "event_source": "api",
            "old_status": task.get("task_status"),
            "new_status": "approved",
            "note": f"Workflow task {workflow_task_id} approved",
            "payload_json": {"workflow_task_id": workflow_task_id},
        })

    audit_log(
        "workflow.task_approved",
        actor=approved_by,
        entity_type="workflow_task",
        entity_id=workflow_task_id,
        payload={"case_id": case_id},
    )

    return {
        "success": True,
        "workflow_task_id": workflow_task_id,
        "status": "approved",
        "case_id": case_id,
    }


@router.post("/approvals/task/{workflow_task_id}/reject", response_model=WorkflowTaskApprovalResponse)
@handle_errors
def reject_workflow_task(
    workflow_task_id: int,
    rejected_by: str = Query(..., min_length=1),
    reason: str = Query("", max_length=500),
):
    """Reject a workflow task and append case event."""
    task = get_row("wbom_workflow_tasks", "workflow_task_id", workflow_task_id)
    if not task:
        raise HTTPException(404, "Workflow task not found")

    if task.get("task_status") in ("approved", "completed", "rejected", "cancelled"):
        return {
            "success": True,
            "workflow_task_id": workflow_task_id,
            "status": task.get("task_status"),
            "message": "Task already finalized",
        }

    update_row("wbom_workflow_tasks", "workflow_task_id", workflow_task_id, {
        "task_status": "rejected",
        "assignee_user": rejected_by,
        "completion_note": reason,
    })
    execute_query(
        "UPDATE wbom_workflow_tasks SET completed_at = NOW(), updated_at = NOW() WHERE workflow_task_id = %s",
        (workflow_task_id,),
    )

    case_id = task.get("case_id")
    if case_id:
        insert_row("wbom_case_events", {
            "case_id": case_id,
            "event_type": "task_rejected",
            "actor_type": "user",
            "actor_id": rejected_by,
            "event_source": "api",
            "old_status": task.get("task_status"),
            "new_status": "rejected",
            "note": reason or f"Workflow task {workflow_task_id} rejected",
            "payload_json": {"workflow_task_id": workflow_task_id},
        })

    audit_log(
        "workflow.task_rejected",
        actor=rejected_by,
        entity_type="workflow_task",
        entity_id=workflow_task_id,
        payload={"case_id": case_id, "reason": reason},
    )

    return {
        "success": True,
        "workflow_task_id": workflow_task_id,
        "status": "rejected",
        "case_id": case_id,
    }


@router.post("/approvals/payment/{staging_id}/approve", response_model=WorkflowStagingPaymentApprovalResponse)
@handle_errors
def approve_staging_payment(staging_id: int, approved_by: str = Query(..., min_length=1)):
    """Unified approval endpoint for staging payments."""
    row = get_row("wbom_staging_payments", "id", staging_id)
    if not row:
        raise HTTPException(404, "Staging payment not found")

    if row.get("status") != "pending":
        return {
            "success": True,
            "staging_id": staging_id,
            "status": row.get("status"),
            "message": "Payment already processed",
        }

    update_row_no_ts("wbom_staging_payments", "id", staging_id, {
        "status": "approved",
        "reviewed_by": approved_by,
    })

    audit_log(
        "payment.approved",
        actor=approved_by,
        entity_type="staging_payment",
        entity_id=staging_id,
        payload={"amount": str(row.get("amount", 0)), "employee_id": row.get("employee_id")},
    )

    return {
        "success": True,
        "staging_id": staging_id,
        "status": "approved",
        "message": "Payment approved. Ready to execute.",
    }
