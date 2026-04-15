# ============================================================
# WBOM — Advanced Search Routes
# Cross-table search across WBOM data
# ============================================================
from fastapi import APIRouter, Query

from database import execute_query
from models import AdvancedSearchRequest, SearchResult

router = APIRouter(prefix="/search", tags=["search"])


@router.post("", response_model=SearchResult)
def advanced_search(req: AdvancedSearchRequest):
    results: dict = {}
    q = f"%{req.query}%"
    limit = req.limit or 20

    if not req.tables or "contacts" in req.tables:
        rows = execute_query(
            "SELECT * FROM wbom_contacts WHERE contact_name ILIKE %s OR whatsapp_number ILIKE %s OR company_name ILIKE %s LIMIT %s",
            (q, q, q, limit),
        )
        if rows:
            results["contacts"] = rows

    if not req.tables or "employees" in req.tables:
        rows = execute_query(
            "SELECT * FROM wbom_employees WHERE employee_name ILIKE %s OR employee_mobile ILIKE %s LIMIT %s",
            (q, q, limit),
        )
        if rows:
            results["employees"] = rows

    if not req.tables or "programs" in req.tables:
        rows = execute_query(
            "SELECT * FROM wbom_escort_programs WHERE mother_vessel ILIKE %s OR lighter_vessel ILIKE %s OR master_mobile ILIKE %s LIMIT %s",
            (q, q, q, limit),
        )
        if rows:
            results["programs"] = rows

    if not req.tables or "transactions" in req.tables:
        rows = execute_query(
            "SELECT * FROM wbom_cash_transactions WHERE description ILIKE %s LIMIT %s",
            (q, limit),
        )
        if rows:
            results["transactions"] = rows

    if not req.tables or "messages" in req.tables:
        rows = execute_query(
            "SELECT * FROM wbom_whatsapp_messages WHERE message_body ILIKE %s LIMIT %s",
            (q, limit),
        )
        if rows:
            results["messages"] = rows

    total = sum(len(v) for v in results.values())
    return SearchResult(query=req.query, total=total, results=results)


@router.get("")
def quick_search(q: str = Query(..., min_length=1), limit: int = Query(20, le=100)):
    req = AdvancedSearchRequest(query=q, limit=limit)
    return advanced_search(req)
