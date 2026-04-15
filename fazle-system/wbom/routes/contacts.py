# ============================================================
# WBOM — Contact Routes
# CRUD + search for business contacts
# ============================================================
from fastapi import APIRouter, HTTPException, Query
from typing import Optional

from database import insert_row, get_row, update_row, delete_row, list_rows, search_rows, count_rows, execute_query
from models import ContactCreate, ContactUpdate, ContactResponse, ContactProfileCard

router = APIRouter(prefix="/contacts", tags=["contacts"])


@router.post("", response_model=ContactResponse, status_code=201)
def create_contact(data: ContactCreate):
    row = insert_row("wbom_contacts", data.model_dump(exclude_none=True))
    return row


@router.get("/{contact_id}", response_model=ContactResponse)
def get_contact(contact_id: int):
    row = get_row("wbom_contacts", "contact_id", contact_id)
    if not row:
        raise HTTPException(404, "Contact not found")
    return row


@router.put("/{contact_id}", response_model=ContactResponse)
def update_contact(contact_id: int, data: ContactUpdate):
    fields = data.model_dump(exclude_none=True)
    row = update_row("wbom_contacts", "contact_id", contact_id, fields)
    if not row:
        raise HTTPException(404, "Contact not found")
    return row


@router.delete("/{contact_id}")
def remove_contact(contact_id: int):
    if not delete_row("wbom_contacts", "contact_id", contact_id):
        raise HTTPException(404, "Contact not found")
    return {"deleted": True}


@router.get("", response_model=list[ContactResponse])
def list_contacts(
    is_active: Optional[bool] = None,
    relation_type_id: Optional[int] = None,
    business_type_id: Optional[int] = None,
    limit: int = Query(50, le=200),
    offset: int = 0,
):
    filters = {}
    if is_active is not None:
        filters["is_active"] = is_active
    if relation_type_id:
        filters["relation_type_id"] = relation_type_id
    if business_type_id:
        filters["business_type_id"] = business_type_id
    return list_rows("wbom_contacts", filters, "display_name", limit, offset)


@router.get("/search/{query}")
def search_contacts(query: str, limit: int = Query(20, le=100)):
    by_name = search_rows("wbom_contacts", "display_name", query, limit)
    by_phone = search_rows("wbom_contacts", "whatsapp_number", query, limit)
    by_company = search_rows("wbom_contacts", "company_name", query, limit)
    # Deduplicate by contact_id
    seen = set()
    results = []
    for row in by_name + by_phone + by_company:
        if row["contact_id"] not in seen:
            seen.add(row["contact_id"])
            results.append(row)
    return results[:limit]


@router.get("/by-whatsapp/{number}", response_model=ContactResponse)
def get_by_whatsapp(number: str):
    rows = search_rows("wbom_contacts", "whatsapp_number", number, 1)
    if not rows:
        raise HTTPException(404, "Contact not found")
    return rows[0]


@router.get("/{contact_id}/profile", response_model=ContactProfileCard)
def get_contact_profile(contact_id: int):
    """Phase 4 §4.1: Contact profile card with aggregated data."""
    contact = get_row("wbom_contacts", "contact_id", contact_id)
    if not contact:
        raise HTTPException(404, "Contact not found")

    # Relation type name
    relation_name = None
    if contact.get("relation_type_id"):
        rt = get_row("wbom_relation_types", "relation_type_id", contact["relation_type_id"])
        relation_name = rt["relation_name"] if rt else None

    # Business type name
    business_name = None
    if contact.get("business_type_id"):
        bt = get_row("wbom_business_types", "business_type_id", contact["business_type_id"])
        business_name = bt["business_name"] if bt else None

    # Aggregated counts
    templates_count = execute_query(
        "SELECT COUNT(*) as cnt FROM wbom_contact_templates WHERE contact_id = %s",
        (contact_id,),
    )
    interactions_count = execute_query(
        "SELECT COUNT(*) as cnt FROM wbom_whatsapp_messages "
        "WHERE contact_id = %s AND received_at >= NOW() - INTERVAL '30 days'",
        (contact_id,),
    )
    pending_count = execute_query(
        "SELECT COUNT(*) as cnt FROM wbom_escort_programs "
        "WHERE contact_id = %s AND status IN ('Assigned', 'Running')",
        (contact_id,),
    )

    return {
        "contact_id": contact["contact_id"],
        "whatsapp_number": contact["whatsapp_number"],
        "display_name": contact["display_name"],
        "company_name": contact.get("company_name"),
        "relation_type": relation_name,
        "business_type": business_name,
        "is_active": contact.get("is_active", True),
        "assigned_templates_count": templates_count[0]["cnt"] if templates_count else 0,
        "recent_interactions_count": interactions_count[0]["cnt"] if interactions_count else 0,
        "pending_programs_count": pending_count[0]["cnt"] if pending_count else 0,
    }
