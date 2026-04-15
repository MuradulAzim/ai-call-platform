# ============================================================
# WBOM — Employee Routes
# CRUD + search for security personnel
# ============================================================
from fastapi import APIRouter, HTTPException, Query
from typing import Optional

from database import insert_row, get_row, update_row, delete_row, list_rows, search_rows
from models import EmployeeCreate, EmployeeUpdate, EmployeeResponse

router = APIRouter(prefix="/employees", tags=["employees"])


@router.post("", response_model=EmployeeResponse, status_code=201)
def create_employee(data: EmployeeCreate):
    row = insert_row("wbom_employees", data.model_dump(exclude_none=True))
    return row


@router.get("/{employee_id}", response_model=EmployeeResponse)
def get_employee(employee_id: int):
    row = get_row("wbom_employees", "employee_id", employee_id)
    if not row:
        raise HTTPException(404, "Employee not found")
    return row


@router.put("/{employee_id}", response_model=EmployeeResponse)
def update_employee(employee_id: int, data: EmployeeUpdate):
    fields = data.model_dump(exclude_none=True)
    row = update_row("wbom_employees", "employee_id", employee_id, fields)
    if not row:
        raise HTTPException(404, "Employee not found")
    return row


@router.delete("/{employee_id}")
def remove_employee(employee_id: int):
    if not delete_row("wbom_employees", "employee_id", employee_id):
        raise HTTPException(404, "Employee not found")
    return {"deleted": True}


@router.get("", response_model=list[EmployeeResponse])
def list_employees(
    status: Optional[str] = None,
    designation: Optional[str] = None,
    limit: int = Query(50, le=200),
    offset: int = 0,
):
    filters = {}
    if status:
        filters["status"] = status
    if designation:
        filters["designation"] = designation
    return list_rows("wbom_employees", filters, "employee_name", limit, offset)


@router.get("/search/{query}")
def search_employees(query: str, limit: int = Query(20, le=100)):
    by_name = search_rows("wbom_employees", "employee_name", query, limit)
    by_mobile = search_rows("wbom_employees", "employee_mobile", query, limit)
    seen = set()
    results = []
    for row in by_name + by_mobile:
        if row["employee_id"] not in seen:
            seen.add(row["employee_id"])
            results.append(row)
    return results[:limit]


@router.get("/by-mobile/{mobile}", response_model=EmployeeResponse)
def get_by_mobile(mobile: str):
    rows = search_rows("wbom_employees", "employee_mobile", mobile, 1)
    if not rows:
        raise HTTPException(404, "Employee not found")
    return rows[0]
