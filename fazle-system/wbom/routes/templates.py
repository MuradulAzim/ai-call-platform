# ============================================================
# WBOM — Template Routes
# Message template management + draft generation
# ============================================================
from fastapi import APIRouter, HTTPException, Query
from typing import Optional

from database import insert_row, get_row, delete_row, list_rows
from models import TemplateCreate, TemplateResponse, TemplateCompleteRequest, TemplateCompleteResponse
from services.template_engine import select_template_for_contact, generate_draft, complete_template

router = APIRouter(prefix="/templates", tags=["templates"])


@router.post("", response_model=TemplateResponse, status_code=201)
def create_template(data: TemplateCreate):
    row = insert_row("wbom_message_templates", data.model_dump(exclude_none=True))
    return row


@router.get("/{template_id}", response_model=TemplateResponse)
def get_template(template_id: int):
    row = get_row("wbom_message_templates", "template_id", template_id)
    if not row:
        raise HTTPException(404, "Template not found")
    return row


@router.delete("/{template_id}")
def remove_template(template_id: int):
    if not delete_row("wbom_message_templates", "template_id", template_id):
        raise HTTPException(404, "Template not found")
    return {"deleted": True}


@router.get("", response_model=list[TemplateResponse])
def list_templates(
    message_type: Optional[str] = None,
    limit: int = Query(50, le=200),
    offset: int = 0,
):
    filters = {}
    if message_type:
        filters["message_type"] = message_type
    return list_rows("wbom_message_templates", filters, "template_name", limit, offset)


@router.post("/suggest")
def suggest(contact_id: int = None, message_type: str = "general"):
    tpl = select_template_for_contact(contact_id, message_type)
    if not tpl:
        raise HTTPException(404, "No matching template")
    return tpl


@router.post("/generate-draft")
def draft(template_id: int, message_id: int):
    from database import get_row
    from services.data_extractor import extract_all_fields
    template = get_row("wbom_message_templates", "template_id", template_id)
    if not template:
        raise HTTPException(404, "Template not found")
    msg = get_row("wbom_whatsapp_messages", "message_id", message_id)
    if not msg:
        raise HTTPException(404, "Message not found")
    # Re-extract data from the stored message
    from services.template_engine import generate_template
    extracted = extract_all_fields(msg["message_body"], template.get("required_fields") or [])
    result = generate_template(template, extracted)
    return result


@router.post("/complete", response_model=TemplateCompleteResponse)
def complete(req: TemplateCompleteRequest):
    result = complete_template(req.template_id, req.message_id, req.field_values)
    if not result:
        raise HTTPException(400, "Could not complete template")
    return result
