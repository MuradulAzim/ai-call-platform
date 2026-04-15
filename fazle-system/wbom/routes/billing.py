# ============================================================
# WBOM — Billing Routes
# CRUD + invoice generation for escort services
# ============================================================
from fastapi import APIRouter, HTTPException, Query
from typing import Optional

from database import insert_row, get_row, update_row, delete_row, list_rows
from models import BillingCreate, BillingUpdate, BillingResponse
from services.invoice_generator import generate_invoice, get_outstanding_invoices, format_invoice_text

router = APIRouter(prefix="/billing", tags=["billing"])


@router.post("", response_model=BillingResponse, status_code=201)
def create_billing(data: BillingCreate):
    row = insert_row("wbom_billing_records", data.model_dump(exclude_none=True))
    return row


@router.get("/{billing_id}", response_model=BillingResponse)
def get_billing(billing_id: int):
    row = get_row("wbom_billing_records", "billing_id", billing_id)
    if not row:
        raise HTTPException(404, "Billing record not found")
    return row


@router.put("/{billing_id}", response_model=BillingResponse)
def update_billing(billing_id: int, data: BillingUpdate):
    fields = data.model_dump(exclude_none=True)
    row = update_row("wbom_billing_records", "billing_id", billing_id, fields)
    if not row:
        raise HTTPException(404, "Billing record not found")
    return row


@router.delete("/{billing_id}")
def remove_billing(billing_id: int):
    if not delete_row("wbom_billing_records", "billing_id", billing_id):
        raise HTTPException(404, "Billing record not found")
    return {"deleted": True}


@router.get("", response_model=list[BillingResponse])
def list_billing(
    status: Optional[str] = None,
    contact_id: Optional[int] = None,
    limit: int = Query(50, le=200),
    offset: int = 0,
):
    filters = {}
    if status:
        filters["payment_status"] = status
    if contact_id:
        filters["contact_id"] = contact_id
    return list_rows("wbom_billing_records", filters, "billing_date DESC", limit, offset)


@router.post("/generate-invoice/{contact_id}")
def generate(contact_id: int, month: str = Query(..., pattern=r"^\d{4}-\d{2}$")):
    invoice = generate_invoice(contact_id, month)
    return invoice


@router.get("/outstanding/{contact_id}")
def outstanding(contact_id: int):
    return get_outstanding_invoices(contact_id)


@router.get("/invoice-text/{billing_id}")
def invoice_text(billing_id: int):
    text = format_invoice_text(billing_id)
    if not text:
        raise HTTPException(404, "Billing record not found")
    return {"text": text}
