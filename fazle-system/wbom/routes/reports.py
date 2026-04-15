# ============================================================
# WBOM — Report Routes
# Phase 7 §7.1: Salary + billing reports
# ============================================================
from fastapi import APIRouter, HTTPException, Query
from typing import Optional

from database import execute_query
from models import SalaryReportResponse, BillingReportResponse
from services.salary_generator import (
    calculate_monthly_salary, get_employee_programs, get_employee_transactions,
)

from config import settings as _cfg
from services.wbom_logger import handle_errors

router = APIRouter(prefix="/reports", tags=["reports"])

DEFAULT_SERVICE_CHARGE = _cfg.default_service_charge


@router.get(
    "/salary/{employee_id}/{month}/{year}",
    response_model=SalaryReportResponse,
)
@handle_errors
def salary_report(employee_id: int, month: int, year: int):
    """Generate salary report for an employee."""
    try:
        salary_data = calculate_monthly_salary(employee_id, month, year)
    except ValueError as e:
        raise HTTPException(404, str(e))

    programs = get_employee_programs(employee_id, month, year)
    transactions = get_employee_transactions(employee_id, month, year)

    return SalaryReportResponse(
        salary_summary=salary_data,
        programs=programs,
        transactions=transactions,
    )


@router.get(
    "/billing/{contact_id}",
    response_model=BillingReportResponse,
)
def billing_report(
    contact_id: int,
    date_from: Optional[str] = Query(None, description="YYYY-MM-DD"),
    date_to: Optional[str] = Query(None, description="YYYY-MM-DD"),
):
    """Generate billing report for a contact."""
    # Default: current month
    if not date_from:
        from datetime import date
        today = date.today()
        date_from = today.replace(day=1).isoformat()
    if not date_to:
        from datetime import date
        date_to = date.today().isoformat()

    programs = execute_query("""
        SELECT * FROM wbom_escort_programs
        WHERE contact_id = %s
          AND status = 'Completed'
          AND program_date BETWEEN %s AND %s
        ORDER BY program_date DESC
    """, (contact_id, date_from, date_to))

    total_programs = len(programs)
    total_amount = total_programs * DEFAULT_SERVICE_CHARGE

    return BillingReportResponse(
        contact_id=contact_id,
        period={"from": date_from, "to": date_to},
        total_programs=total_programs,
        service_charge=DEFAULT_SERVICE_CHARGE,
        total_amount=total_amount,
        programs=programs,
    )
