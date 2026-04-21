# ============================================================
# WBOM — Message Processing Routes
# WhatsApp message ingestion + classification + extraction
# Sprint-5 S5-03: /messages/dispatch is the single inbound
#                 entry point for all WhatsApp messages.
# ============================================================
import logging

from fastapi import APIRouter, HTTPException, Query
from typing import Optional

from database import insert_row, get_row, list_rows, delete_row, update_row_no_ts, search_rows, execute_query
from models import (
    MessageCreate, MessageProcessRequest, MessageProcessResponse,
    ValidationRequest, ValidationResponse, ValidationItem,
    QuickActionResponse,
    OrderProcessRequest, OrderProcessResponse, SaveProgramRequest,
    PaymentProcessRequest, PaymentProcessResponse,
    ConversationRequest, ConversationResponse,
    MultiLighterProcessRequest, MultiLighterProcessResponse,
    MultiLighterSaveRequest,
)
from services.message_processor import process_incoming_message
from services.wbom_logger import handle_errors

logger = logging.getLogger("wbom.messages")

router = APIRouter(prefix="/messages", tags=["messages"])

# ── Recruitment keyword set (Sprint-5 S5-03) ─────────────────
_RECRUITMENT_KEYWORDS: frozenset[str] = frozenset({
    "job", "কাজ", "চাকরি", "vacancy", "apply", "hire",
    "recruit", "নিয়োগ", "কাজের", "চাই", "interested",
    "work", "join", "joining",
})


def _is_recruitment_message(text: str) -> bool:
    lower = (text or "").lower()
    return any(kw in lower for kw in _RECRUITMENT_KEYWORDS)


def _message_already_processed(whatsapp_msg_id: str) -> bool:
    """Return True if a message with this whatsapp_msg_id was already processed."""
    if not whatsapp_msg_id:
        return False
    rows = execute_query(
        "SELECT message_id FROM wbom_whatsapp_messages "
        "WHERE whatsapp_msg_id = %s AND is_processed = TRUE LIMIT 1",
        (whatsapp_msg_id,),
    )
    return bool(rows)


# ── Sprint-5 S5-03: Single unified dispatcher ─────────────────

@router.post("/dispatch", response_model=MessageProcessResponse)
@handle_errors
def dispatch_message(req: MessageProcessRequest):
    """
    Single inbound entry point for all WhatsApp messages (Sprint-5 S5-03).

    Routing logic:
      - If message contains recruitment keywords → recruitment.intake_message()
      - Otherwise → message_processor.process_incoming_message()

    Duplicate guard: messages with the same whatsapp_msg_id that were already
    processed are rejected with HTTP 409 to prevent double-processing.
    """
    # Duplicate guard
    if req.whatsapp_msg_id and _message_already_processed(req.whatsapp_msg_id):
        raise HTTPException(
            status_code=409,
            detail=f"Message {req.whatsapp_msg_id!r} already processed.",
        )

    if _is_recruitment_message(req.message_body):
        logger.info(
            "dispatch → recruitment.intake_message | phone=%s", req.sender_number
        )
        from services.recruitment import intake_message
        result = intake_message(phone=req.sender_number, message=req.message_body)
        # Normalise to MessageProcessResponse shape
        return {
            "message_id":        result.get("message_id", 0),
            "classification":    "recruitment",
            "confidence":        1.0,
            "is_multi_lighter":  False,
            "extracted_data":    {},
            "suggested_template": None,
            "draft_reply":       result.get("reply", ""),
            "requires_admin_input": False,
            "missing_fields":    [],
            "unfilled_fields":   [],
            "confidence_scores": {},
        }

    logger.info(
        "dispatch → message_processor.process_incoming_message | phone=%s",
        req.sender_number,
    )
    return process_incoming_message(
        req.sender_number, req.message_body, req.whatsapp_msg_id,
    )


@router.post("/process", response_model=MessageProcessResponse)
@handle_errors
def process_message(req: MessageProcessRequest):
    result = process_incoming_message(req.sender_number, req.message_body)
    return result


# ── Processor Endpoints (Phase 5) ─────────────────────────────

@router.post("/process-order", response_model=OrderProcessResponse)
@handle_errors
def process_order(req: OrderProcessRequest):
    """Phase 5 §5.1: Process escort order message through EscortOrderProcessor."""
    from services.escort_processor import EscortOrderProcessor
    processor = EscortOrderProcessor()
    return processor.process_order(
        req.message_id, req.sender_number, req.message_body, req.contact_id,
    )


@router.post("/save-program")
@handle_errors
def save_program(req: SaveProgramRequest):
    """Phase 5 §5.1: Save escort program after admin review."""
    from services.escort_processor import EscortOrderProcessor
    processor = EscortOrderProcessor()
    return processor.save_escort_program(
        req.message_id, req.extracted_data, req.contact_id, req.admin_overrides,
    )


@router.post("/process-payment", response_model=PaymentProcessResponse)
@handle_errors
def process_payment(req: PaymentProcessRequest):
    """Phase 5 §5.2: Process payment message through PaymentProcessor."""
    from services.payment_processor import PaymentProcessor
    processor = PaymentProcessor()
    return processor.process_payment(
        req.message_id, req.sender_number, req.message_body, req.contact_id,
    )


@router.post("/handle-conversation", response_model=ConversationResponse)
@handle_errors
def handle_conversation(req: ConversationRequest):
    """Phase 5 §5.3: Handle general/query messages through ConversationHandler."""
    from services.conversation_handler import ConversationHandler
    handler = ConversationHandler()
    return handler.handle_general_message(
        req.message_id, req.sender_number, req.message_body, req.contact_id,
    )


@router.post("")
def store_message(data: MessageCreate):
    row = insert_row("wbom_whatsapp_messages", data.model_dump(exclude_none=True))
    return row


@router.get("/{message_id}")
def get_message(message_id: int):
    row = get_row("wbom_whatsapp_messages", "message_id", message_id)
    if not row:
        raise HTTPException(404, "Message not found")
    return row


@router.get("", response_model=list)
def list_messages(
    contact_id: Optional[int] = None,
    message_type: Optional[str] = None,
    direction: Optional[str] = None,
    limit: int = Query(50, le=200),
    offset: int = 0,
):
    filters = {}
    if contact_id:
        filters["contact_id"] = contact_id
    if message_type:
        filters["message_type"] = message_type
    if direction:
        filters["direction"] = direction
    return list_rows("wbom_whatsapp_messages", filters, "received_at DESC", limit, offset)


@router.get("/by-contact/{contact_id}")
def messages_by_contact(contact_id: int, limit: int = Query(50, le=200)):
    return list_rows(
        "wbom_whatsapp_messages", {"contact_id": contact_id}, "received_at DESC", limit, 0
    )


# ── Validation (Phase 4 §4.3) ────────────────────────────────

@router.post("/validate", response_model=ValidationResponse)
def validate_message_data(req: ValidationRequest):
    """Pre-send validation checklist."""
    import re

    items = []

    # Mobile number validation: 0 + 10 digits
    if req.mobile_number is not None:
        valid = bool(re.match(r"^0\d{10}$", req.mobile_number))
        items.append(ValidationItem(
            field="mobile_number",
            value=req.mobile_number,
            valid=valid,
            message="Valid mobile" if valid else "Must be 0 followed by 10 digits",
        ))

    # Employee existence check
    if req.employee_name is not None:
        found = search_rows("wbom_employees", "employee_name", req.employee_name, 1)
        items.append(ValidationItem(
            field="employee_name",
            value=req.employee_name,
            valid=bool(found),
            message="Employee found" if found else "Employee not found in database",
        ))

    # Vessel name validation: reasonable chars
    for vessel_field in ("mother_vessel", "lighter_vessel"):
        val = getattr(req, vessel_field, None)
        if val is not None:
            valid = bool(re.match(r"^[A-Za-z0-9\s\.\-]{2,100}$", val))
            items.append(ValidationItem(
                field=vessel_field,
                value=val,
                valid=valid,
                message="Valid vessel name" if valid else "Invalid characters or length",
            ))

    # Amount validation: positive number, reasonable range
    if req.amount is not None:
        try:
            amt = float(req.amount)
            valid = 0 < amt <= 10_000_000
            items.append(ValidationItem(
                field="amount",
                value=req.amount,
                valid=valid,
                message="Valid amount" if valid else "Amount out of range (1 - 10,000,000)",
            ))
        except (ValueError, TypeError):
            items.append(ValidationItem(
                field="amount",
                value=req.amount,
                valid=False,
                message="Amount must be a valid number",
            ))

    all_valid = all(item.valid for item in items) if items else True
    return ValidationResponse(all_valid=all_valid, items=items)


# ── Quick Actions (Phase 4 §4.2) ─────────────────────────────

@router.post("/{message_id}/mark-processed", response_model=QuickActionResponse)
def mark_processed(message_id: int):
    """Mark a message as processed."""
    msg = get_row("wbom_whatsapp_messages", "message_id", message_id)
    if not msg:
        raise HTTPException(404, "Message not found")
    update_row_no_ts("wbom_whatsapp_messages", "message_id", message_id, {
        "is_processed": True,
    })
    return QuickActionResponse(success=True, message="Marked as processed", message_id=message_id)


@router.post("/{message_id}/flag", response_model=QuickActionResponse)
def flag_message(message_id: int):
    """Flag a message for review."""
    msg = get_row("wbom_whatsapp_messages", "message_id", message_id)
    if not msg:
        raise HTTPException(404, "Message not found")
    update_row_no_ts("wbom_whatsapp_messages", "message_id", message_id, {
        "is_flagged": True,
    })
    return QuickActionResponse(success=True, message="Flagged for review", message_id=message_id)


@router.delete("/{message_id}", response_model=QuickActionResponse)
def delete_message(message_id: int):
    """Delete a message."""
    if not delete_row("wbom_whatsapp_messages", "message_id", message_id):
        raise HTTPException(404, "Message not found")
    return QuickActionResponse(success=True, message="Message deleted", message_id=message_id)


# ── Multi-lighter endpoints (Phase 8 §Scenario 3) ────────────

@router.post("/process-multi-lighter", response_model=MultiLighterProcessResponse)
@handle_errors
def process_multi_lighter(req: MultiLighterProcessRequest):
    """Process a message with multiple lighter entries.

    Detects numbered lighter entries, extracts per-lighter data,
    generates a combined template, and returns all data for admin review.
    """
    from services.escort_processor import EscortOrderProcessor
    processor = EscortOrderProcessor()
    return processor.process_multi_lighter_order(
        req.message_id, req.sender_number, req.message_body, req.contact_id,
    )


@router.post("/save-multi-lighter-programs")
@handle_errors
def save_multi_lighter_programs(req: MultiLighterSaveRequest):
    """Save N separate program records from a multi-lighter message.

    Creates one program per lighter, all sharing the same mother vessel.
    """
    from services.escort_processor import EscortOrderProcessor
    processor = EscortOrderProcessor()
    programs = processor.save_multi_lighter_programs(
        req.message_id, req.multi_data, req.contact_id, req.admin_overrides,
    )
    return {
        "saved_count": len(programs),
        "programs": programs,
    }
