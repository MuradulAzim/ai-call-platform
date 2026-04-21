# ============================================================
# WBOM — Case Workflow Service
# Phase-2: complaint auto-case creation + workflow task bootstrap
# ============================================================
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from database import insert_row, execute_query

logger = logging.getLogger("wbom.case_workflow")


_COMPLAINT_KEYWORDS = (
    "complaint", "complain", "অভিযোগ", "সমস্যা", "issue", "problem",
    "চুরি", "theft", "absent", "আসে নাই", "নেই", "রূঢ়", "রুড", "ঝামেলা",
)

_CRITICAL_HINTS = (
    "চুরি", "theft", "মারামারি", "assault", "অরক্ষিত", "নেই", "no guard", "absent",
)


def is_complaint_text(message_body: str) -> bool:
    text = (message_body or "").lower()
    return any(word in text for word in _COMPLAINT_KEYWORDS)


def _detect_severity(message_body: str) -> str:
    text = (message_body or "").lower()
    if any(hint in text for hint in _CRITICAL_HINTS):
        return "critical"
    if any(h in text for h in ("urgent", "জরুরি", "তাড়াতাড়ি", "late", "দেরি")):
        return "high"
    return "medium"


def _sla_minutes_for_severity(severity: str) -> int:
    if severity == "critical":
        return 120
    if severity == "high":
        return 480
    return 1440


def create_complaint_case(
    message_id: int,
    sender_number: str,
    message_body: str,
    contact_id: Optional[int] = None,
    confidence: float = 0.5,
) -> dict:
    """Create a complaint case + initial event + investigation workflow task.

    Idempotency: if a case already exists for this message_id, return that one.
    """
    existing = execute_query(
        """
        SELECT case_id, status
        FROM wbom_cases
        WHERE case_type = 'complaint'
          AND metadata_json->>'source_message_id' = %s
        ORDER BY case_id DESC
        LIMIT 1
        """,
        (str(message_id),),
    )
    if existing:
        return dict(existing[0])

    severity = _detect_severity(message_body)
    priority = "urgent" if severity == "critical" else "high" if severity == "high" else "normal"
    due_at = datetime.now(timezone.utc) + timedelta(minutes=_sla_minutes_for_severity(severity))

    title = f"Client complaint from {sender_number}"
    snippet = (message_body or "").strip().replace("\n", " ")
    if snippet:
        title = (snippet[:120] + "...") if len(snippet) > 120 else snippet

    case_row = insert_row("wbom_cases", {
        "case_type": "complaint",
        "source_platform": "whatsapp",
        "source_channel": "inbound_message",
        "contact_id": contact_id,
        "title": title,
        "description": message_body,
        "priority": priority,
        "severity": severity,
        "status": "open",
        "owner_role": "operation_manager",
        "due_at": due_at.isoformat(),
        "metadata_json": {
            "source_message_id": str(message_id),
            "sender_number": sender_number,
            "intent_confidence": confidence,
        },
    })

    case_id = case_row["case_id"]

    insert_row("wbom_case_events", {
        "case_id": case_id,
        "event_type": "case_opened",
        "actor_type": "system",
        "actor_id": "wbom.message_processor",
        "event_source": "api",
        "message_id": message_id,
        "new_status": "open",
        "note": "Complaint case auto-created from inbound message",
        "payload_json": {
            "confidence": confidence,
            "severity": severity,
            "priority": priority,
        },
    })

    insert_row("wbom_workflow_tasks", {
        "case_id": case_id,
        "task_type": "complaint_review",
        "task_title": "Review and respond to complaint",
        "task_status": "pending",
        "approval_required": True,
        "assignee_role": "operation_manager",
        "requester": "system",
        "due_at": due_at.isoformat(),
        "correlation_key": f"complaint-review-msg-{message_id}",
        "payload_json": {
            "message_id": message_id,
            "sender_number": sender_number,
            "auto_created": True,
        },
    })

    logger.info("Created complaint case %s from message %s", case_id, message_id)
    return {"case_id": case_id, "status": "open", "severity": severity, "priority": priority}
