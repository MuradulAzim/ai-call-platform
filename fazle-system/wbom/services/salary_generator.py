# ============================================================
# WBOM — Salary Generator
# Auto-calculates salary based on programs, advances, deductions
# ============================================================
import logging
from decimal import Decimal
from typing import Optional

from database import get_conn, get_row, insert_row, execute_query
import psycopg2.extras

logger = logging.getLogger("wbom.salary_generator")


def generate_salary(
    employee_id: int,
    month: int,
    year: int,
    basic_salary: Decimal,
    program_allowance: Decimal = Decimal("0"),
    other_allowance: Decimal = Decimal("0"),
    remarks: Optional[str] = None,
) -> dict:
    """Generate salary record for an employee for a given month.

    Auto-calculates:
    - total_programs: count of completed programs in the month
    - total_advances: sum of Advance transactions in the month
    - total_deductions: sum of Deduction transactions in the month
    - net_salary: basic + allowances - advances - deductions
    """
    # 1. Count completed programs
    programs = execute_query("""
        SELECT COUNT(*) as total FROM wbom_escort_programs
        WHERE escort_employee_id = %s
          AND EXTRACT(MONTH FROM program_date) = %s
          AND EXTRACT(YEAR FROM program_date) = %s
          AND status = 'Completed'
    """, (employee_id, month, year))
    total_programs = programs[0]["total"] if programs else 0

    # 2. Sum advances
    advances = execute_query("""
        SELECT COALESCE(SUM(amount), 0) as total FROM wbom_cash_transactions
        WHERE employee_id = %s
          AND EXTRACT(MONTH FROM transaction_date) = %s
          AND EXTRACT(YEAR FROM transaction_date) = %s
          AND transaction_type = 'Advance'
          AND status = 'Completed'
    """, (employee_id, month, year))
    total_advances = Decimal(str(advances[0]["total"])) if advances else Decimal("0")

    # 3. Sum deductions
    deductions = execute_query("""
        SELECT COALESCE(SUM(amount), 0) as total FROM wbom_cash_transactions
        WHERE employee_id = %s
          AND EXTRACT(MONTH FROM transaction_date) = %s
          AND EXTRACT(YEAR FROM transaction_date) = %s
          AND transaction_type = 'Deduction'
          AND status = 'Completed'
    """, (employee_id, month, year))
    total_deductions = Decimal(str(deductions[0]["total"])) if deductions else Decimal("0")

    # 4. Calculate net salary
    net_salary = basic_salary + program_allowance + other_allowance - total_advances - total_deductions

    # 5. Upsert salary record
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                INSERT INTO wbom_salary_records
                    (employee_id, month, year, basic_salary, total_programs,
                     program_allowance, other_allowance, total_advances,
                     total_deductions, net_salary, remarks)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (employee_id, month, year) DO UPDATE SET
                    basic_salary = EXCLUDED.basic_salary,
                    total_programs = EXCLUDED.total_programs,
                    program_allowance = EXCLUDED.program_allowance,
                    other_allowance = EXCLUDED.other_allowance,
                    total_advances = EXCLUDED.total_advances,
                    total_deductions = EXCLUDED.total_deductions,
                    net_salary = EXCLUDED.net_salary,
                    remarks = EXCLUDED.remarks
                RETURNING *
            """, (
                employee_id, month, year, basic_salary, total_programs,
                program_allowance, other_allowance, total_advances,
                total_deductions, net_salary, remarks,
            ))
            row = cur.fetchone()
        conn.commit()

    return dict(row)


def get_salary_summary(month: int, year: int) -> list[dict]:
    """Get salary summary for all employees for a given month."""
    return execute_query("""
        SELECT s.*, e.employee_name, e.employee_mobile, e.designation
        FROM wbom_salary_records s
        JOIN wbom_employees e ON e.employee_id = s.employee_id
        WHERE s.month = %s AND s.year = %s
        ORDER BY e.employee_name
    """, (month, year))


def mark_salary_paid(salary_id: int, payment_date: str = None) -> Optional[dict]:
    """Mark a salary record as paid."""
    from database import update_row_no_ts
    from datetime import date
    return update_row_no_ts("wbom_salary_records", "salary_id", salary_id, {
        "payment_status": "Paid",
        "payment_date": payment_date or date.today().isoformat(),
    })


# ── Business Calculation Rules (Phase 6 §6.2) ────────────────

from config import settings as _cfg

DEFAULT_PER_PROGRAM_RATE = Decimal(str(_cfg.per_program_allowance))


def calculate_monthly_salary(
    employee_id: int,
    month: int,
    year: int,
    per_program_rate: Decimal = DEFAULT_PER_PROGRAM_RATE,
) -> dict:
    """Calculate full salary breakdown for an employee.

    Uses business rules:
        net_salary = basic_salary + program_allowance + other_allowance
                   - total_advances - total_deductions

        program_allowance = total_programs * per_program_rate

        total_advances = SUM(Advance + Food + Conveyance transactions)
    """
    employee = get_row("wbom_employees", "employee_id", employee_id)
    if not employee:
        raise ValueError(f"Employee {employee_id} not found")

    # Count completed programs
    programs = execute_query("""
        SELECT COUNT(*) as total FROM wbom_escort_programs
        WHERE escort_employee_id = %s
          AND EXTRACT(MONTH FROM program_date) = %s
          AND EXTRACT(YEAR FROM program_date) = %s
          AND status = 'Completed'
    """, (employee_id, month, year))
    total_programs = programs[0]["total"] if programs else 0

    # Calculate program allowance
    program_allowance = Decimal(str(total_programs)) * per_program_rate

    # Total advances (Advance + Food + Conveyance)
    advances = execute_query("""
        SELECT COALESCE(SUM(amount), 0) as total FROM wbom_cash_transactions
        WHERE employee_id = %s
          AND EXTRACT(MONTH FROM transaction_date) = %s
          AND EXTRACT(YEAR FROM transaction_date) = %s
          AND transaction_type IN ('Advance', 'Food', 'Conveyance')
          AND status = 'Completed'
    """, (employee_id, month, year))
    total_advances = Decimal(str(advances[0]["total"])) if advances else Decimal("0")

    # Total deductions
    deductions = execute_query("""
        SELECT COALESCE(SUM(amount), 0) as total FROM wbom_cash_transactions
        WHERE employee_id = %s
          AND EXTRACT(MONTH FROM transaction_date) = %s
          AND EXTRACT(YEAR FROM transaction_date) = %s
          AND transaction_type = 'Deduction'
          AND status = 'Completed'
    """, (employee_id, month, year))
    total_deductions = Decimal(str(deductions[0]["total"])) if deductions else Decimal("0")

    # Use basic_salary of 0 (employee table doesn't have it; passed via generate_salary)
    basic_salary = Decimal("0")

    net_salary = basic_salary + program_allowance - total_advances - total_deductions

    salary_data = {
        "employee_id": employee_id,
        "employee_name": employee.get("employee_name"),
        "designation": employee.get("designation"),
        "month": month,
        "year": year,
        "basic_salary": str(basic_salary),
        "total_programs": total_programs,
        "per_program_rate": str(per_program_rate),
        "program_allowance": str(program_allowance),
        "total_advances": str(total_advances),
        "total_deductions": str(total_deductions),
        "net_salary": str(net_salary),
    }

    # Upsert the salary record
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                INSERT INTO wbom_salary_records
                    (employee_id, month, year, basic_salary, total_programs,
                     program_allowance, total_advances, total_deductions, net_salary)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (employee_id, month, year) DO UPDATE SET
                    basic_salary = EXCLUDED.basic_salary,
                    total_programs = EXCLUDED.total_programs,
                    program_allowance = EXCLUDED.program_allowance,
                    total_advances = EXCLUDED.total_advances,
                    total_deductions = EXCLUDED.total_deductions,
                    net_salary = EXCLUDED.net_salary
                RETURNING *
            """, (
                employee_id, month, year, basic_salary, total_programs,
                program_allowance, total_advances, total_deductions, net_salary,
            ))
            cur.fetchone()
        conn.commit()

    return salary_data


def get_employee_programs(employee_id: int, month: int, year: int) -> list[dict]:
    """Get detailed program list for salary report."""
    return execute_query("""
        SELECT p.*, c.display_name as contact_name
        FROM wbom_escort_programs p
        LEFT JOIN wbom_contacts c ON p.contact_id = c.contact_id
        WHERE p.escort_employee_id = %s
          AND EXTRACT(MONTH FROM p.program_date) = %s
          AND EXTRACT(YEAR FROM p.program_date) = %s
        ORDER BY p.program_date DESC
    """, (employee_id, month, year))


def get_employee_transactions(employee_id: int, month: int, year: int) -> list[dict]:
    """Get detailed transaction list for salary report."""
    return execute_query("""
        SELECT * FROM wbom_cash_transactions
        WHERE employee_id = %s
          AND EXTRACT(MONTH FROM transaction_date) = %s
          AND EXTRACT(YEAR FROM transaction_date) = %s
        ORDER BY transaction_date DESC
    """, (employee_id, month, year))
