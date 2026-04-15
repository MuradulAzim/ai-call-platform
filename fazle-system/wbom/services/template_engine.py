# ============================================================
# WBOM — Template Engine
# Template selection, population, and completion
# Phase 3: AI Processing Logic §3.3 + §3.4
# ============================================================
import logging
import re
from datetime import datetime
from typing import Optional

from database import get_conn, get_row, insert_row, list_rows, update_row_no_ts
import psycopg2.extras

logger = logging.getLogger("wbom.template_engine")


# ── Template Selection (Phase 3 §3.3) ────────────────────────

def select_template_for_contact(
    contact_id: Optional[int], message_classification: str
) -> Optional[dict]:
    """Select appropriate template based on contact assignment and message type.

    Priority:
    1. Contact-specific assigned template (if contact exists)
    2. Default template for the classification type

    Returns: template dict or None
    """
    # Map classification names to template_type values
    type_map = {
        "escort_order": "escort_order",
        "order": "escort_order",
        "payment": "payment",
        "query": "query_response",
        "general": "general_reply",
    }
    template_type = type_map.get(message_classification, "general_reply")

    # 1. Get contact-specific templates
    if contact_id:
        try:
            with get_conn() as conn:
                with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                    cur.execute(
                        """
                        SELECT t.* FROM wbom_message_templates t
                        JOIN wbom_contact_templates ct ON t.template_id = ct.template_id
                        WHERE ct.contact_id = %s
                        AND t.template_type = %s
                        AND t.is_active = TRUE
                        ORDER BY ct.priority DESC, ct.is_default DESC
                        LIMIT 1
                        """,
                        (contact_id, template_type),
                    )
                    row = cur.fetchone()
                    if row:
                        return dict(row)
        except Exception as e:
            logger.debug(f"Contact template lookup failed: {e}")

    # 2. Fallback to default template for message type
    templates = list_rows(
        "wbom_message_templates",
        {"template_type": template_type, "is_active": True},
        limit=1,
    )
    return templates[0] if templates else None


# ── Template Population (Phase 3 §3.4) ───────────────────────

def generate_template(
    template_obj: dict, extracted_data: dict, message_metadata: dict = None
) -> dict:
    """Generate filled template from extracted data (Phase 3 §3.4).

    Returns dict with:
        - template: str (populated body)
        - unfilled_fields: list[str]
        - confidence_scores: dict[str, float]
    """
    template_body = template_obj["template_body"]

    # Auto-fill available fields
    for field_name, field_data in extracted_data.items():
        value = field_data.get("value") if isinstance(field_data, dict) else field_data
        if value:
            placeholder = "{" + field_name + "}"
            template_body = template_body.replace(placeholder, str(value))

    # Add date/time based fields
    current_time = datetime.now()
    shift = "D" if 6 <= current_time.hour < 18 else "N"
    date_str = current_time.strftime("%d.%m.%Y")

    template_body = template_body.replace("{date}", date_str)
    template_body = template_body.replace("{shift}", shift)

    # Highlight unfilled fields for admin
    unfilled_fields = re.findall(r"\{([^}]+)\}", template_body)

    return {
        "template": template_body,
        "unfilled_fields": unfilled_fields,
        "confidence_scores": {
            k: v.get("confidence", 0.0) if isinstance(v, dict) else 0.0
            for k, v in extracted_data.items()
        },
    }


# ── Legacy helpers (used by routes) ──────────────────────────


def suggest_template(
    classification: str, contact: Optional[dict] = None
) -> Optional[dict]:
    """Convenience wrapper around select_template_for_contact."""
    contact_id = contact["contact_id"] if contact else None
    return select_template_for_contact(contact_id, classification)


def generate_draft(
    template: dict, extracted_data: dict
) -> tuple[str, list[str]]:
    """Convenience wrapper that returns (draft_text, missing_fields)."""
    result = generate_template(template, extracted_data)
    return result["template"], result["unfilled_fields"]


def complete_template(
    message_id: int, template_id: int, field_values: dict
) -> str:
    """Complete a template with admin-provided field values.

    Returns the fully formatted message.
    """
    template = get_row("wbom_message_templates", "template_id", template_id)
    if not template:
        raise ValueError(f"Template {template_id} not found")

    body = template["template_body"]

    # Fill all fields
    for field, value in field_values.items():
        body = body.replace(f"{{{field}}}", str(value))

    # Log the generation
    insert_row(
        "wbom_template_generation_log",
        {
            "message_id": message_id,
            "template_id": template_id,
            "generated_content": body,
            "admin_modified_content": body,
        },
    )

    return body


# ── Multi-lighter template generation (Phase 8 §Scenario 3) ─

def generate_multi_lighter_template(
    template_obj: dict,
    mother_vessel_data: dict,
    date_data: dict,
    lighters: list[dict],
) -> str:
    """Generate a combined template for multiple lighter entries.

    Produces a header section with the mother vessel and date,
    followed by a numbered block for each lighter.

    Args:
        template_obj: The base template dict.
        mother_vessel_data: {"value": str, "confidence": float}
        date_data: {"value": str, "confidence": float}
        lighters: list of per-lighter extracted field dicts.

    Returns:
        Combined template string.
    """
    mv = mother_vessel_data.get("value", "{mother_vessel}")
    current_time = datetime.now()
    date_str = date_data.get("value") or current_time.strftime("%d.%m.%Y")
    shift = "D" if 6 <= current_time.hour < 18 else "N"

    # Header section
    header = f"MV: {mv}\nDate: {date_str}\nShift: {shift}\n"

    # Build per-lighter blocks using the base template body
    template_body = template_obj.get("template_body", "")
    blocks = []

    for idx, lighter in enumerate(lighters, 1):
        # Start from template body for each lighter
        block = template_body

        # Remove mother_vessel / date / shift placeholders
        # (they are in the shared header)
        for shared_field in ("mother_vessel", "date", "shift"):
            block = block.replace(f"{{{shared_field}}}", "")

        # Fill per-lighter fields
        for field_name, field_info in lighter.items():
            value = field_info.get("value") if isinstance(field_info, dict) else field_info
            if value:
                block = block.replace(f"{{{field_name}}}", str(value))

        # Clean up remaining unfilled placeholders → highlight them
        # Strip any leading MV: or Date: lines since those are in header
        lines = []
        for line in block.strip().splitlines():
            stripped = line.strip().lower()
            if stripped.startswith("mv:") or stripped.startswith("date:") or stripped.startswith("shift:"):
                continue
            if line.strip():
                lines.append(line)
        block = "\n".join(lines)

        blocks.append(f"{idx:02d}) {block}")

    return header + "\n" + "\n\n".join(blocks)


def mark_template_sent(log_id: int, sent_message_id: str = None):
    """Mark a template generation log as sent."""
    update_row_no_ts(
        "wbom_template_generation_log",
        "log_id",
        log_id,
        {"is_sent": True, "sent_at": datetime.utcnow()},
    )
