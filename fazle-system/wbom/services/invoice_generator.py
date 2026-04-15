# ============================================================
# WBOM — Invoice Generator
# Generates billing invoices for escort programs
# ============================================================
import logging
from datetime import date
from decimal import Decimal
from typing import Optional

from database import get_row, insert_row, execute_query

logger = logging.getLogger("wbom.invoice_generator")


def generate_invoice(
    program_id: int,
    contact_id: int,
    service_charge: Decimal,
    other_charges: Decimal = Decimal("0"),
    remarks: Optional[str] = None,
) -> dict:
    """Generate a billing invoice for a completed escort program."""
    # Validate program exists
    program = get_row("wbom_escort_programs", "program_id", program_id)
    if not program:
        raise ValueError(f"Program {program_id} not found")

    # Validate contact exists
    contact = get_row("wbom_contacts", "contact_id", contact_id)
    if not contact:
        raise ValueError(f"Contact {contact_id} not found")

    # Generate bill number: ALAQSA-YYYYMMDD-SEQNUM
    today = date.today()
    seq = _get_next_bill_seq(today)
    bill_number = f"ALAQSA-{today.strftime('%Y%m%d')}-{seq:04d}"

    total_amount = service_charge + other_charges

    bill = insert_row("wbom_billing_records", {
        "program_id": program_id,
        "contact_id": contact_id,
        "bill_date": today.isoformat(),
        "bill_number": bill_number,
        "service_charge": str(service_charge),
        "other_charges": str(other_charges),
        "total_amount": str(total_amount),
        "remarks": remarks,
    })

    return bill


def _get_next_bill_seq(bill_date: date) -> int:
    """Get next sequence number for a given date."""
    rows = execute_query("""
        SELECT COUNT(*) as cnt FROM wbom_billing_records
        WHERE bill_date = %s
    """, (bill_date.isoformat(),))
    return (rows[0]["cnt"] if rows else 0) + 1


def get_outstanding_invoices(contact_id: Optional[int] = None) -> list[dict]:
    """Get all unpaid/partial invoices, optionally filtered by contact."""
    if contact_id:
        return execute_query("""
            SELECT b.*, c.display_name, c.company_name, p.mother_vessel, p.lighter_vessel
            FROM wbom_billing_records b
            JOIN wbom_contacts c ON c.contact_id = b.contact_id
            JOIN wbom_escort_programs p ON p.program_id = b.program_id
            WHERE b.payment_status IN ('Pending', 'Partial') AND b.contact_id = %s
            ORDER BY b.bill_date
        """, (contact_id,))
    return execute_query("""
        SELECT b.*, c.display_name, c.company_name, p.mother_vessel, p.lighter_vessel
        FROM wbom_billing_records b
        JOIN wbom_contacts c ON c.contact_id = b.contact_id
        JOIN wbom_escort_programs p ON p.program_id = b.program_id
        WHERE b.payment_status IN ('Pending', 'Partial')
        ORDER BY b.bill_date
    """)


def format_invoice_text(bill: dict) -> str:
    """Format a billing record as a WhatsApp-friendly text invoice."""
    return (
        f"═══════════════════════\n"
        f"   AL-AQSA SECURITY SERVICE\n"
        f"        INVOICE\n"
        f"═══════════════════════\n"
        f"Invoice#: {bill.get('bill_number', 'N/A')}\n"
        f"Date: {bill.get('bill_date', 'N/A')}\n"
        f"───────────────────────\n"
        f"Service Charge: {bill.get('service_charge', 0)}/-\n"
        f"Other Charges:  {bill.get('other_charges', 0)}/-\n"
        f"───────────────────────\n"
        f"Total Amount:   {bill.get('total_amount', 0)}/-\n"
        f"Status: {bill.get('payment_status', 'Pending')}\n"
        f"═══════════════════════\n"
    )
