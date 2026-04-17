# ============================================================
# WBOM — Schema Discovery Endpoint
# GET /schema/{entity} → field definitions for dynamic UIs
# ============================================================
from fastapi import APIRouter, HTTPException

from response import FIELD_MAPS, VERSION

router = APIRouter(prefix="/schema", tags=["schema"])

# Static schema definitions — single source of truth
_SCHEMAS: dict[str, list[dict]] = {
    "employees": [
        {"name": "id", "type": "number", "label": "ID", "sortable": True},
        {"name": "name", "type": "string", "label": "Name", "sortable": True},
        {"name": "phone", "type": "string", "label": "Phone", "sortable": False},
        {"name": "designation", "type": "string", "label": "Designation", "sortable": True},
        {"name": "status", "type": "string", "label": "Status", "sortable": True},
        {"name": "salary", "type": "number", "label": "Basic Salary", "sortable": True},
        {"name": "bkash", "type": "string", "label": "Bkash", "sortable": False},
        {"name": "nagad", "type": "string", "label": "Nagad", "sortable": False},
        {"name": "nid", "type": "string", "label": "NID", "sortable": False},
        {"name": "joined", "type": "datetime", "label": "Joined", "sortable": True},
    ],
    "transactions": [
        {"name": "id", "type": "number", "label": "ID", "sortable": True},
        {"name": "employee_name", "type": "string", "label": "Employee", "sortable": True},
        {"name": "type", "type": "string", "label": "Type", "sortable": True},
        {"name": "amount", "type": "number", "label": "Amount", "sortable": True},
        {"name": "method", "type": "string", "label": "Method", "sortable": True},
        {"name": "status", "type": "string", "label": "Status", "sortable": True},
        {"name": "date", "type": "datetime", "label": "Date", "sortable": True},
        {"name": "remarks", "type": "string", "label": "Remarks", "sortable": False},
    ],
    "clients": [
        {"name": "id", "type": "number", "label": "ID", "sortable": True},
        {"name": "name", "type": "string", "label": "Name", "sortable": True},
        {"name": "phone", "type": "string", "label": "Phone", "sortable": False},
        {"name": "company", "type": "string", "label": "Company", "sortable": True},
        {"name": "type", "type": "string", "label": "Type", "sortable": True},
        {"name": "balance", "type": "number", "label": "Balance", "sortable": True},
        {"name": "is_active", "type": "boolean", "label": "Active", "sortable": True},
    ],
    "applications": [
        {"name": "id", "type": "number", "label": "ID", "sortable": True},
        {"name": "name", "type": "string", "label": "Name", "sortable": True},
        {"name": "phone", "type": "string", "label": "Phone", "sortable": False},
        {"name": "position", "type": "string", "label": "Position", "sortable": True},
        {"name": "experience", "type": "string", "label": "Experience", "sortable": False},
        {"name": "status", "type": "string", "label": "Status", "sortable": True},
        {"name": "source", "type": "string", "label": "Source", "sortable": True},
        {"name": "applied_at", "type": "datetime", "label": "Applied", "sortable": True},
    ],
    "audit": [
        {"name": "id", "type": "number", "label": "ID", "sortable": True},
        {"name": "time", "type": "datetime", "label": "Time", "sortable": True},
        {"name": "event", "type": "string", "label": "Event", "sortable": True},
        {"name": "actor", "type": "string", "label": "Actor", "sortable": True},
        {"name": "entity", "type": "string", "label": "Entity", "sortable": True},
        {"name": "entity_id", "type": "number", "label": "Entity ID", "sortable": False},
        {"name": "payload", "type": "object", "label": "Details", "sortable": False},
    ],
    "payments": [
        {"name": "id", "type": "number", "label": "ID", "sortable": True},
        {"name": "employee_name", "type": "string", "label": "Employee", "sortable": True},
        {"name": "amount", "type": "number", "label": "Amount", "sortable": True},
        {"name": "method", "type": "string", "label": "Method", "sortable": True},
        {"name": "status", "type": "string", "label": "Status", "sortable": True},
        {"name": "created_at", "type": "datetime", "label": "Created", "sortable": True},
    ],
}


@router.get("/{entity}")
def get_schema(entity: str):
    """Return field schema for a given entity.
    Frontend uses this to dynamically render tables/forms."""
    if entity not in _SCHEMAS:
        raise HTTPException(404, f"Unknown entity: {entity}")
    return {
        "success": True,
        "entity": entity,
        "fields": _SCHEMAS[entity],
        "field_map": FIELD_MAPS.get(entity, {}),
        "version": VERSION,
    }


@router.get("")
def list_entities():
    """Return all available entities."""
    return {
        "success": True,
        "entities": list(_SCHEMAS.keys()),
        "version": VERSION,
    }
