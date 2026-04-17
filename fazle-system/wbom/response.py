# ============================================================
# WBOM — Standard API Response Wrapper
# All list/detail endpoints return normalized envelope:
#   { success, data, meta, schema, version }
# ============================================================
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any

VERSION = "v1"

# ── Field normalization maps ─────────────────────────────────
# DB column name → friendly API name

_EMPLOYEE_MAP = {
    "employee_id": "id",
    "employee_name": "name",
    "employee_mobile": "phone",
    "basic_salary": "salary",
    "bkash_number": "bkash",
    "nagad_number": "nagad",
    "nid_number": "nid",
    "emergency_contact": "emergency_phone",
    "bank_account": "bank",
    "joining_date": "joined",
    "created_at": "created_at",
    "updated_at": "updated_at",
}

_TRANSACTION_MAP = {
    "transaction_id": "id",
    "employee_id": "employee_id",
    "employee_name": "employee_name",
    "employee_mobile": "employee_phone",
    "transaction_type": "type",
    "payment_method": "method",
    "payment_mobile": "payment_phone",
    "transaction_date": "date",
    "transaction_time": "time",
    "reference_number": "reference",
    "whatsapp_message_id": "wa_msg_id",
    "idempotency_key": "idem_key",
    "approved_by": "approved_by",
    "approved_at": "approved_at",
    "created_by": "created_by",
}

_CLIENT_MAP = {
    "client_id": "id",
    "company_name": "company",
    "client_type": "type",
    "outstanding_balance": "balance",
    "credit_terms": "terms",
    "created_at": "created_at",
    "updated_at": "updated_at",
}

_APPLICATION_MAP = {
    "application_id": "id",
    "applicant_name": "name",
    "created_at": "applied_at",
    "updated_at": "updated_at",
}

_AUDIT_MAP = {
    "audit_id": "id",
    "entity_type": "entity",
    "entity_id": "entity_id",
    "created_at": "time",
}

_PAYMENT_MAP = {
    "id": "id",
    "employee_id": "employee_id",
    "employee_name": "employee_name",
    "payment_method": "method",
    "idempotency_key": "idem_key",
    "reviewed_by": "reviewed_by",
    "final_transaction_id": "transaction_id",
    "created_at": "created_at",
}

FIELD_MAPS: dict[str, dict[str, str]] = {
    "employees": _EMPLOYEE_MAP,
    "transactions": _TRANSACTION_MAP,
    "clients": _CLIENT_MAP,
    "applications": _APPLICATION_MAP,
    "audit": _AUDIT_MAP,
    "payments": _PAYMENT_MAP,
}


def _serialize(val: Any) -> Any:
    """Convert Python types to JSON-safe values."""
    if isinstance(val, Decimal):
        return float(val)
    if isinstance(val, datetime):
        return val.isoformat()
    if isinstance(val, date):
        return val.isoformat()
    return val


def normalize_row(row: dict, field_map: dict[str, str]) -> dict:
    """Rename DB columns → API names; pass-through unmapped fields."""
    out: dict[str, Any] = {}
    for k, v in row.items():
        key = field_map.get(k, k)
        out[key] = _serialize(v)
    return out


def _infer_type(val: Any) -> str:
    if val is None:
        return "string"
    if isinstance(val, bool):
        return "boolean"
    if isinstance(val, int):
        return "number"
    if isinstance(val, (float, Decimal)):
        return "number"
    if isinstance(val, (datetime, date)):
        return "datetime"
    if isinstance(val, dict):
        return "object"
    if isinstance(val, list):
        return "array"
    return "string"


def build_schema(sample: dict) -> dict[str, str]:
    """Derive {field: type} from a sample row."""
    return {k: _infer_type(v) for k, v in sample.items()}


def api_response(
    rows: list[dict],
    *,
    entity: str = "",
    total: int | None = None,
    page: int = 1,
    extra_meta: dict | None = None,
) -> dict:
    """Wrap a list of rows in the standard envelope.

    {
      "success": true,
      "data": [...normalized rows...],
      "meta": {"total": N, "page": 1, "count": len(data)},
      "schema": {"id": "number", ...},
      "version": "v1"
    }
    """
    fmap = FIELD_MAPS.get(entity, {})
    data = [normalize_row(r, fmap) for r in rows]
    count = len(data)
    meta = {
        "total": total if total is not None else count,
        "page": page,
        "count": count,
    }
    if extra_meta:
        meta.update(extra_meta)
    schema = build_schema(data[0]) if data else {}
    return {
        "success": True,
        "data": data,
        "meta": meta,
        "schema": schema,
        "version": VERSION,
    }


def api_single(row: dict, *, entity: str = "") -> dict:
    """Wrap a single row."""
    fmap = FIELD_MAPS.get(entity, {})
    data = normalize_row(row, fmap)
    return {
        "success": True,
        "data": data,
        "schema": build_schema(data),
        "version": VERSION,
    }


def api_error(message: str, status: int = 400) -> dict:
    """Return a standard error envelope (raise HTTPException instead for FastAPI)."""
    return {
        "success": False,
        "error": message,
        "version": VERSION,
    }
