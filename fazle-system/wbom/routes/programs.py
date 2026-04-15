# ============================================================
# WBOM — Escort Program Routes
# CRUD for escort/security program assignments
# ============================================================
from fastapi import APIRouter, HTTPException, Query
from typing import Optional

from database import insert_row, get_row, update_row, delete_row, list_rows, search_rows
from models import ProgramCreate, ProgramUpdate, ProgramResponse

router = APIRouter(prefix="/programs", tags=["programs"])


@router.post("", response_model=ProgramResponse, status_code=201)
def create_program(data: ProgramCreate):
    row = insert_row("wbom_escort_programs", data.model_dump(exclude_none=True))
    return row


@router.get("/{program_id}", response_model=ProgramResponse)
def get_program(program_id: int):
    row = get_row("wbom_escort_programs", "program_id", program_id)
    if not row:
        raise HTTPException(404, "Program not found")
    return row


@router.put("/{program_id}", response_model=ProgramResponse)
def update_program(program_id: int, data: ProgramUpdate):
    fields = data.model_dump(exclude_none=True)
    row = update_row("wbom_escort_programs", "program_id", program_id, fields)
    if not row:
        raise HTTPException(404, "Program not found")
    return row


@router.delete("/{program_id}")
def remove_program(program_id: int):
    if not delete_row("wbom_escort_programs", "program_id", program_id):
        raise HTTPException(404, "Program not found")
    return {"deleted": True}


@router.get("", response_model=list[ProgramResponse])
def list_programs(
    status: Optional[str] = None,
    contact_id: Optional[int] = None,
    shift: Optional[str] = None,
    limit: int = Query(50, le=200),
    offset: int = 0,
):
    filters = {}
    if status:
        filters["status"] = status
    if contact_id:
        filters["contact_id"] = contact_id
    if shift:
        filters["shift"] = shift
    return list_rows("wbom_escort_programs", filters, "program_date DESC", limit, offset)


@router.get("/by-employee/{employee_id}", response_model=list[ProgramResponse])
def programs_by_employee(employee_id: int, limit: int = Query(50, le=200)):
    return list_rows("wbom_escort_programs", {"employee_id": employee_id}, "program_date DESC", limit, 0)


@router.get("/by-vessel/{vessel_name}")
def programs_by_vessel(vessel_name: str, limit: int = Query(50, le=200)):
    return search_rows("wbom_escort_programs", "mother_vessel", vessel_name, limit)
