# ============================================================
# WBOM — Domain Audit Event Helpers  (Sprint-6 S6-03)
# Structured log entries for all critical business actions.
# Import and call from route handlers / service functions.
# ============================================================
import logging
from datetime import datetime, timezone
from typing import Any, Optional

_log = logging.getLogger("wbom.audit")


def _emit(event: str, severity: str, fields: dict) -> None:
    """Emit one structured JSON log line."""
    record = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "service": "wbom",
        "event": event,
        "severity": severity,
        **fields,
    }
    lvl = {
        "info": logging.INFO,
        "warning": logging.WARNING,
        "critical": logging.CRITICAL,
    }.get(severity, logging.INFO)
    _log.log(lvl, record, extra={"action": event})


# ── Payroll ───────────────────────────────────────────────────

def log_payroll_approved(run_id: int, approved_by: str, total_amount: float) -> None:
    _emit("payroll_approved", "info", {
        "run_id": run_id,
        "approved_by": approved_by,
        "total_amount": total_amount,
    })


def log_payroll_paid(run_id: int, paid_by: str, employee_count: int) -> None:
    _emit("payroll_paid", "info", {
        "run_id": run_id,
        "paid_by": paid_by,
        "employee_count": employee_count,
    })


# ── Complaints ────────────────────────────────────────────────

def log_complaint_created(complaint_id: int, priority: str, contact_id: Optional[int]) -> None:
    _emit("complaint_created", "info", {
        "complaint_id": complaint_id,
        "priority": priority,
        "contact_id": contact_id,
    })


def log_complaint_sla_breach(complaint_id: int, sla_due: str, priority: str) -> None:
    _emit("complaint_sla_breach", "critical", {
        "complaint_id": complaint_id,
        "sla_due": sla_due,
        "priority": priority,
    })


def log_complaint_resolved(complaint_id: int, resolved_by: str, minutes_open: int) -> None:
    _emit("complaint_resolved", "info", {
        "complaint_id": complaint_id,
        "resolved_by": resolved_by,
        "minutes_open": minutes_open,
    })


# ── Recruitment ───────────────────────────────────────────────

def log_candidate_converted(candidate_id: int, stage: str, recruiter: Optional[str]) -> None:
    _emit("candidate_converted", "info", {
        "candidate_id": candidate_id,
        "new_stage": stage,
        "recruiter": recruiter,
    })


def log_candidate_hired(candidate_id: int, position: str) -> None:
    _emit("candidate_hired", "info", {
        "candidate_id": candidate_id,
        "position": position,
    })


# ── WhatsApp Dispatch ─────────────────────────────────────────

def log_whatsapp_dispatch_ok(wa_msg_id: str, routed_to: str, sender: str) -> None:
    _emit("whatsapp_dispatch_ok", "info", {
        "wa_msg_id": wa_msg_id,
        "routed_to": routed_to,
        "sender": sender,
    })


def log_whatsapp_dispatch_failed(wa_msg_id: Optional[str], sender: str, error: str) -> None:
    _emit("whatsapp_dispatch_failed", "warning", {
        "wa_msg_id": wa_msg_id,
        "sender": sender,
        "error": error[:200],
    })


def log_whatsapp_duplicate(wa_msg_id: str, sender: str) -> None:
    _emit("whatsapp_duplicate_blocked", "info", {
        "wa_msg_id": wa_msg_id,
        "sender": sender,
    })


# ── Reports ───────────────────────────────────────────────────

def log_report_sent(report_type: str, recipient: str, period: str) -> None:
    _emit("report_sent", "info", {
        "report_type": report_type,
        "recipient": recipient,
        "period": period,
    })


# ── Admin / Login ─────────────────────────────────────────────

def log_admin_action(action: str, actor: str, target: Optional[Any] = None) -> None:
    _emit("admin_action", "info", {
        "action": action,
        "actor": actor,
        "target": str(target) if target is not None else None,
    })
