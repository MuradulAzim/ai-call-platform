"""
services/complaints.py  —  Sprint-4 Complaint + Client Retention
-----------------------------------------------------------------
Functions:
  auto_tag_priority()       – deterministic priority from type+category
  ingest_complaint()        – create complaint, set SLA, log event, return reply
  acknowledge_complaint()   – move open → acknowledged
  assign_complaint()        – assign staff, log event
  escalate_complaint()      – force escalation, log event
  resolve_complaint()       – close with notes, compute resolution time
  check_sla_breaches()      – mark overdue complaints, return list
  get_complaint_metrics()   – owner KPI aggregates
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from database import execute_query, insert_row, get_row, update_row

# ── SLA hours by priority ────────────────────────────────────────────────────

SLA_HOURS: dict[str, int] = {
    "critical": 4,
    "high":     24,
    "medium":   72,
    "low":      168,   # 7 days
}

# ── Priority auto-tag rules ──────────────────────────────────────────────────

_CLIENT_PRIORITY: dict[str, str] = {
    "harassment":           "critical",
    "misconduct":           "critical",
    "replacement_request":  "high",
    "payment_dispute":      "high",
    "service_quality":      "medium",
    "other":                "low",
}

_EMPLOYEE_PRIORITY: dict[str, str] = {
    "harassment":       "critical",
    "salary_issue":     "high",
    "supervisor_issue": "medium",
    "duty_mismatch":    "low",
    "other":            "low",
}

VALID_CLIENT_CATEGORIES = set(_CLIENT_PRIORITY.keys())
VALID_EMPLOYEE_CATEGORIES = set(_EMPLOYEE_PRIORITY.keys())

# WhatsApp auto-reply messages
_INTAKE_REPLY: dict[str, str] = {
    "critical": (
        "আপনার অভিযোগ জরুরি হিসেবে নথিভুক্ত হয়েছে। 🚨\n"
        "আমাদের টিম ৪ ঘণ্টার মধ্যে যোগাযোগ করবে।\n"
        "(Your complaint is registered as CRITICAL. We will contact you within 4 hours.)"
    ),
    "high": (
        "আপনার অভিযোগ নথিভুক্ত হয়েছে। ⚠️\n"
        "আমাদের টিম ২৪ ঘণ্টার মধ্যে যোগাযোগ করবে।\n"
        "(Your complaint is registered. We will contact you within 24 hours.)"
    ),
    "medium": (
        "আপনার অভিযোগ নথিভুক্ত হয়েছে। ✅\n"
        "আমাদের টিম ৩ কার্যদিবসের মধ্যে যোগাযোগ করবে।\n"
        "(Your complaint is registered. We will contact you within 3 business days.)"
    ),
    "low": (
        "আপনার অভিযোগ নথিভুক্ত হয়েছে। ✅\n"
        "আমাদের টিম শীঘ্রই যোগাযোগ করবে।\n"
        "(Your complaint is registered. Our team will follow up soon.)"
    ),
}

VALID_STATUSES = (
    "open", "acknowledged", "investigating",
    "resolved", "closed", "escalated",
)

VALID_TRANSITIONS: dict[str, list[str]] = {
    "open":           ["acknowledged", "escalated"],
    "acknowledged":   ["investigating", "escalated"],
    "investigating":  ["resolved", "escalated"],
    "escalated":      ["investigating", "resolved"],
    "resolved":       ["closed"],
}


# ── Helpers ──────────────────────────────────────────────────────────────────

def _now() -> datetime:
    return datetime.now(timezone.utc)


def _get_complaint(complaint_id: int) -> Optional[dict]:
    row = get_row("wbom_complaints", "complaint_id", complaint_id)
    return dict(row) if row else None


def _log_event(complaint_id: int, event_type: str, actor: str = "system",
               from_status: Optional[str] = None, to_status: Optional[str] = None,
               notes: Optional[str] = None) -> None:
    insert_row("wbom_complaint_events", {
        "complaint_id": complaint_id,
        "event_type":   event_type,
        "actor":        actor,
        "from_status":  from_status,
        "to_status":    to_status,
        "notes":        notes,
    })


# ── Priority + SLA ───────────────────────────────────────────────────────────

def auto_tag_priority(complaint_type: str, category: str) -> str:
    """Return deterministic priority string for a complaint type+category pair."""
    if complaint_type == "client":
        return _CLIENT_PRIORITY.get(category, "medium")
    elif complaint_type == "employee":
        return _EMPLOYEE_PRIORITY.get(category, "medium")
    return "medium"


# ── Category auto-detection from free text ───────────────────────────────────

_CLIENT_CATEGORY_KEYWORDS: dict[str, tuple[str, ...]] = {
    "harassment":          ("harassment", "harass", "abuse", "abusive", "রূঢ়", "রুড", "অপমান"),
    "misconduct":          ("misconduct", "misbehav", "misbehave", "theft", "চুরি", "অসদাচরণ"),
    "replacement_request": ("replace", "change", "বদল", "পরিবর্তন", "new guard"),
    "payment_dispute":     ("payment", "bill", "charge", "টাকা", "বিল", "পেমেন্ট"),
    "service_quality":     ("quality", "late", "absent", "দেরি", "আসে নাই", "নেই", "no guard"),
}

_EMPLOYEE_CATEGORY_KEYWORDS: dict[str, tuple[str, ...]] = {
    "harassment":       ("harassment", "harass", "abuse", "হয়রানি"),
    "salary_issue":     ("salary", "pay", "বেতন", "পাইনি", "দেয় নাই"),
    "supervisor_issue": ("supervisor", "boss", "সুপারভাইজার", "অফিসার"),
    "duty_mismatch":    ("duty", "shift", "schedule", "ডিউটি", "পোস্ট"),
}


def _detect_category_from_text(text: str, complaint_type: str) -> str:
    """Best-effort category detection from free text.

    Returns the best-matching category key, or 'other' if no match.
    Used by message_processor when creating complaints from WhatsApp messages.
    """
    lower = (text or "").lower()
    keywords_map = (
        _CLIENT_CATEGORY_KEYWORDS
        if complaint_type == "client"
        else _EMPLOYEE_CATEGORY_KEYWORDS
    )
    for category, keywords in keywords_map.items():
        if any(kw in lower for kw in keywords):
            return category
    return "other"


# ── Ingest (WhatsApp entry point) ────────────────────────────────────────────

def ingest_complaint(
    complaint_type: str,
    category: str,
    description: str,
    reporter_phone: Optional[str] = None,
    reporter_name: Optional[str] = None,
    client_id: Optional[int] = None,
    employee_id: Optional[int] = None,
    source: str = "whatsapp",
) -> dict:
    """
    Create a new complaint, compute SLA, log the creation event.
    Returns the created complaint dict + WhatsApp reply text.
    """
    priority = auto_tag_priority(complaint_type, category)
    sla_hours = SLA_HOURS[priority]
    now = _now()
    sla_due_at = now + timedelta(hours=sla_hours)

    fields: dict = {
        "complaint_type":  complaint_type,
        "category":        category,
        "description":     description[:2000],
        "priority":        priority,
        "sla_hours":       sla_hours,
        "sla_due_at":      sla_due_at.isoformat(),
        "status":          "open",
        "source":          source,
    }
    if reporter_phone:
        fields["reporter_phone"] = reporter_phone[:20]
    if reporter_name:
        fields["reporter_name"] = reporter_name[:100]
    if client_id:
        fields["client_id"] = client_id
    if employee_id:
        fields["employee_id"] = employee_id

    complaint_row = insert_row("wbom_complaints", fields)
    complaint_id: int = complaint_row["complaint_id"]
    _log_event(complaint_id, "created", actor=reporter_phone or "system",
               to_status="open",
               notes=f"Auto-priority: {priority}. SLA: {sla_hours}h.")

    reply = _INTAKE_REPLY[priority]
    return {
        "complaint_id": complaint_id,
        "priority":     priority,
        "sla_due_at":   sla_due_at.isoformat(),
        "reply":        reply,
    }


# ── Acknowledge ──────────────────────────────────────────────────────────────

def acknowledge_complaint(complaint_id: int, actor: str = "system") -> dict:
    c = _get_complaint(complaint_id)
    if not c:
        raise ValueError(f"Complaint {complaint_id} not found")
    if c["status"] not in ("open",):
        raise ValueError(f"Cannot acknowledge complaint in status '{c['status']}'")

    update_row("wbom_complaints", "complaint_id", complaint_id, {
        "status":     "acknowledged",
        "updated_at": _now().isoformat(),
    })
    _log_event(complaint_id, "acknowledged", actor=actor,
               from_status="open", to_status="acknowledged")
    return {"complaint_id": complaint_id, "status": "acknowledged"}


# ── Assign ───────────────────────────────────────────────────────────────────

def assign_complaint(complaint_id: int, staff_name: str,
                     actor: str = "system") -> dict:
    c = _get_complaint(complaint_id)
    if not c:
        raise ValueError(f"Complaint {complaint_id} not found")

    now = _now()
    # Auto-acknowledge if still open
    new_status = c["status"] if c["status"] != "open" else "acknowledged"
    update_row("wbom_complaints", "complaint_id", complaint_id, {
        "assigned_to":  staff_name[:80],
        "assigned_at":  now.isoformat(),
        "status":       new_status,
        "updated_at":   now.isoformat(),
    })
    _log_event(complaint_id, "assigned", actor=actor,
               from_status=c["status"], to_status=new_status,
               notes=f"Assigned to {staff_name}")
    return {"complaint_id": complaint_id, "assigned_to": staff_name, "status": new_status}


# ── Escalate ─────────────────────────────────────────────────────────────────

def escalate_complaint(complaint_id: int, reason: str,
                       actor: str = "system") -> dict:
    c = _get_complaint(complaint_id)
    if not c:
        raise ValueError(f"Complaint {complaint_id} not found")
    if c["status"] in ("resolved", "closed"):
        raise ValueError(f"Cannot escalate a {c['status']} complaint")

    prev = c["status"]
    update_row("wbom_complaints", "complaint_id", complaint_id, {
        "status":     "escalated",
        "priority":   "critical",         # upgrade priority on escalation
        "updated_at": _now().isoformat(),
    })
    _log_event(complaint_id, "escalated", actor=actor,
               from_status=prev, to_status="escalated", notes=reason)
    return {"complaint_id": complaint_id, "status": "escalated"}


# ── Status advance ────────────────────────────────────────────────────────────

def advance_complaint_status(complaint_id: int, to_status: str,
                              actor: str = "system",
                              notes: Optional[str] = None) -> dict:
    c = _get_complaint(complaint_id)
    if not c:
        raise ValueError(f"Complaint {complaint_id} not found")

    from_status = c["status"]
    allowed = VALID_TRANSITIONS.get(from_status, [])
    if to_status not in allowed:
        raise ValueError(
            f"Cannot move from '{from_status}' to '{to_status}'. Allowed: {allowed}"
        )

    update_fields: dict = {"status": to_status, "updated_at": _now().isoformat()}
    update_row("wbom_complaints", "complaint_id", complaint_id, update_fields)
    _log_event(complaint_id, "status_changed", actor=actor,
               from_status=from_status, to_status=to_status, notes=notes)
    return {"complaint_id": complaint_id, "from_status": from_status, "to_status": to_status}


# ── Resolve ───────────────────────────────────────────────────────────────────

def resolve_complaint(complaint_id: int, resolution_notes: str,
                      actor: str = "system") -> dict:
    c = _get_complaint(complaint_id)
    if not c:
        raise ValueError(f"Complaint {complaint_id} not found")
    if c["status"] in ("resolved", "closed"):
        raise ValueError(f"Complaint {complaint_id} already {c['status']}")

    now = _now()
    update_row("wbom_complaints", "complaint_id", complaint_id, {
        "status":           "resolved",
        "resolved_at":      now.isoformat(),
        "resolution_notes": resolution_notes[:2000],
        "updated_at":       now.isoformat(),
    })
    _log_event(complaint_id, "resolved", actor=actor,
               from_status=c["status"], to_status="resolved",
               notes=resolution_notes[:200])

    # Compute resolution hours
    created_raw = c.get("created_at")
    resolution_hours: Optional[float] = None
    if created_raw:
        if hasattr(created_raw, "timestamp"):
            resolution_hours = round((now - created_raw).total_seconds() / 3600, 2)
        else:
            try:
                dt = datetime.fromisoformat(str(created_raw))
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                resolution_hours = round((now - dt).total_seconds() / 3600, 2)
            except ValueError:
                pass

    return {
        "complaint_id":      complaint_id,
        "status":            "resolved",
        "resolution_hours":  resolution_hours,
    }


# ── SLA breach sweep ──────────────────────────────────────────────────────────

def check_sla_breaches() -> list[dict]:
    """
    Mark all overdue open/acknowledged/investigating complaints as sla_breached=TRUE.
    Returns the list of newly breached complaints.
    """
    now = _now().isoformat()
    rows = execute_query(
        """
        UPDATE wbom_complaints
        SET    sla_breached = TRUE, updated_at = NOW()
        WHERE  sla_breached = FALSE
          AND  sla_due_at  < %s
          AND  status NOT IN ('resolved', 'closed')
        RETURNING complaint_id, complaint_type, category, priority,
                  reporter_phone, reporter_name, assigned_to, sla_due_at
        """,
        (now,),
    )
    breached = [dict(r) for r in rows]
    for b in breached:
        _log_event(b["complaint_id"], "sla_breach", actor="system",
                   notes=f"SLA exceeded. Due: {b['sla_due_at']}")
    return breached


# ── Owner metrics ─────────────────────────────────────────────────────────────

def get_complaint_metrics(ref_date=None) -> dict:
    """
    Returns owner KPI aggregates:
      unresolved_total, critical_open, sla_breaches_total,
      repeat_complaint_clients, fastest_resolvers, recent_by_category
    """
    from datetime import date as _date

    if ref_date is None:
        ref_date = _date.today()

    # Unresolved totals by type
    rows = execute_query(
        """
        SELECT complaint_type,
               COUNT(*) AS total,
               SUM(CASE WHEN priority = 'critical' THEN 1 ELSE 0 END) AS critical_count,
               SUM(CASE WHEN sla_breached = TRUE   THEN 1 ELSE 0 END) AS breached_count
        FROM wbom_complaints
        WHERE status NOT IN ('resolved', 'closed')
        GROUP BY complaint_type
        """,
        (),
    )
    unresolved: dict = {}
    total_critical = 0
    total_breached = 0
    for r in rows:
        unresolved[r["complaint_type"]] = int(r["total"])
        total_critical += int(r["critical_count"] or 0)
        total_breached += int(r["breached_count"] or 0)

    # Repeat complaint clients (filed 2+ complaints this month, not resolved)
    from datetime import datetime as _dt
    month_start = _dt.combine(ref_date.replace(day=1),
                              _dt.min.time()).replace(tzinfo=timezone.utc)
    rows = execute_query(
        """
        SELECT reporter_phone, reporter_name, COUNT(*) AS complaint_count
        FROM wbom_complaints
        WHERE complaint_type = 'client'
          AND created_at >= %s
        GROUP BY reporter_phone, reporter_name
        HAVING COUNT(*) >= 2
        ORDER BY COUNT(*) DESC
        LIMIT 20
        """,
        (month_start.isoformat(),),
    )
    repeat_clients = [
        {
            "reporter_phone": r["reporter_phone"],
            "reporter_name":  r["reporter_name"],
            "complaint_count": int(r["complaint_count"]),
        }
        for r in rows
    ]

    # Fastest resolvers (avg resolution hours, min 3 resolved)
    rows = execute_query(
        """
        SELECT assigned_to,
               COUNT(*)  AS resolved_count,
               ROUND(AVG(EXTRACT(EPOCH FROM (resolved_at - created_at)) / 3600)::numeric, 1)
                         AS avg_hours
        FROM wbom_complaints
        WHERE status IN ('resolved', 'closed')
          AND assigned_to IS NOT NULL
          AND resolved_at IS NOT NULL
        GROUP BY assigned_to
        HAVING COUNT(*) >= 3
        ORDER BY avg_hours ASC
        LIMIT 10
        """,
        (),
    )
    fastest_resolvers = [
        {
            "staff":          r["assigned_to"],
            "resolved_count": int(r["resolved_count"]),
            "avg_hours":      float(r["avg_hours"] or 0),
        }
        for r in rows
    ]

    # Category breakdown (open only)
    rows = execute_query(
        """
        SELECT category, COUNT(*) AS cnt
        FROM wbom_complaints
        WHERE status NOT IN ('resolved', 'closed')
        GROUP BY category
        ORDER BY cnt DESC
        """,
        (),
    )
    category_breakdown = {r["category"]: int(r["cnt"]) for r in rows}

    return {
        "ref_date":             str(ref_date),
        "unresolved_by_type":   unresolved,
        "unresolved_total":     sum(unresolved.values()),
        "critical_open":        total_critical,
        "sla_breaches_total":   total_breached,
        "repeat_complaint_clients": repeat_clients,
        "fastest_resolvers":    fastest_resolvers,
        "category_breakdown":   category_breakdown,
    }
