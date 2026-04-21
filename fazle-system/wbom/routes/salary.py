# ============================================================
# WBOM — Salary Routes  [DEPRECATED — Sprint-5 S5-01]
# Use /api/wbom/payroll/* for all new payroll operations.
# These endpoints will be removed after 2026-07-01.
# ============================================================
import logging

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse

from models import SalaryGenerateRequest, SalaryResponse
from services.salary_generator import generate_salary, get_salary_summary, mark_salary_paid

logger = logging.getLogger("wbom.salary")

_DEPRECATION_HEADERS = {
    "Deprecation": "true",
    "Sunset": "2026-07-01",
    "X-WBOM-Migrate-To": "/api/wbom/payroll",
    "Link": '</api/wbom/payroll>; rel="successor-version"',
}

router = APIRouter(prefix="/salary", tags=["salary"])


@router.post("/generate", response_model=SalaryResponse)
def generate(req: SalaryGenerateRequest):
    logger.warning(
        "DEPRECATED /salary/generate called for employee_id=%s month=%s year=%s. "
        "Migrate to POST /api/wbom/payroll/runs.",
        req.employee_id, req.month, req.year,
    )
    record = generate_salary(
        employee_id=req.employee_id,
        month=req.month,
        year=req.year,
        basic_salary=req.basic_salary,
        program_allowance=req.program_allowance,
        other_allowance=req.other_allowance,
        remarks=req.remarks,
    )
    return JSONResponse(content=dict(record), headers=_DEPRECATION_HEADERS)


@router.get("/summary")
def summary(month: int = Query(..., ge=1, le=12), year: int = Query(..., ge=2020, le=2099)):
    logger.warning(
        "DEPRECATED /salary/summary called month=%s year=%s. "
        "Migrate to GET /api/wbom/payroll/runs.",
        month, year,
    )
    rows = get_salary_summary(month, year)
    total = sum(r.get("net_salary", 0) for r in rows)
    return JSONResponse(
        content={"month": month, "year": year, "records": rows, "total_payable": total},
        headers=_DEPRECATION_HEADERS,
    )


@router.post("/mark-paid/{salary_id}")
def paid(salary_id: int):
    logger.warning(
        "DEPRECATED /salary/mark-paid/%s called. "
        "Migrate to POST /api/wbom/payroll/runs/{run_id}/pay.",
        salary_id,
    )
    ok = mark_salary_paid(salary_id)
    if not ok:
        raise HTTPException(404, "Salary record not found")
    return JSONResponse(content={"paid": True}, headers=_DEPRECATION_HEADERS)
