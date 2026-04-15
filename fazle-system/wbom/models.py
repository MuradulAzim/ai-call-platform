# ============================================================
# WBOM — Pydantic Models
# Request/Response schemas for all WBOM API endpoints
# ============================================================
from datetime import date, datetime
from decimal import Decimal
from typing import Optional
from pydantic import BaseModel, Field


# ── Contacts ──────────────────────────────────────────────────

class ContactCreate(BaseModel):
    whatsapp_number: str = Field(..., max_length=20)
    display_name: str = Field(..., max_length=100)
    company_name: Optional[str] = Field(None, max_length=150)
    relation_type_id: Optional[int] = None
    business_type_id: Optional[int] = None
    notes: Optional[str] = None


class ContactUpdate(BaseModel):
    display_name: Optional[str] = Field(None, max_length=100)
    company_name: Optional[str] = Field(None, max_length=150)
    relation_type_id: Optional[int] = None
    business_type_id: Optional[int] = None
    is_active: Optional[bool] = None
    notes: Optional[str] = None


class ContactResponse(BaseModel):
    contact_id: int
    whatsapp_number: str
    display_name: str
    company_name: Optional[str] = None
    relation_type_id: Optional[int] = None
    business_type_id: Optional[int] = None
    is_active: bool = True
    created_at: datetime
    updated_at: datetime
    notes: Optional[str] = None


# ── Employees ─────────────────────────────────────────────────

class EmployeeCreate(BaseModel):
    employee_mobile: str = Field(..., max_length=20)
    employee_name: str = Field(..., max_length=100)
    designation: str = Field(..., pattern=r"^(Escort|Seal-man|Security Guard|Supervisor|Labor)$")
    joining_date: Optional[date] = None
    bank_account: Optional[str] = Field(None, max_length=50)
    emergency_contact: Optional[str] = Field(None, max_length=20)
    address: Optional[str] = None


class EmployeeUpdate(BaseModel):
    employee_name: Optional[str] = Field(None, max_length=100)
    designation: Optional[str] = Field(None, pattern=r"^(Escort|Seal-man|Security Guard|Supervisor|Labor)$")
    status: Optional[str] = Field(None, pattern=r"^(Active|Inactive|On Leave|Terminated)$")
    bank_account: Optional[str] = Field(None, max_length=50)
    emergency_contact: Optional[str] = Field(None, max_length=20)
    address: Optional[str] = None


class EmployeeResponse(BaseModel):
    employee_id: int
    employee_mobile: str
    employee_name: str
    designation: str
    joining_date: Optional[date] = None
    status: str = "Active"
    bank_account: Optional[str] = None
    emergency_contact: Optional[str] = None
    address: Optional[str] = None
    created_at: datetime
    updated_at: datetime


# ── Escort Programs ───────────────────────────────────────────

class ProgramCreate(BaseModel):
    mother_vessel: str = Field(..., max_length=100)
    lighter_vessel: str = Field(..., max_length=100)
    master_mobile: str = Field(..., max_length=20)
    destination: Optional[str] = Field(None, max_length=100)
    escort_employee_id: Optional[int] = None
    escort_mobile: Optional[str] = Field(None, max_length=20)
    program_date: date
    shift: str = Field(..., pattern=r"^[DN]$")
    contact_id: Optional[int] = None
    whatsapp_message_id: Optional[str] = None
    remarks: Optional[str] = None


class ProgramUpdate(BaseModel):
    escort_employee_id: Optional[int] = None
    escort_mobile: Optional[str] = Field(None, max_length=20)
    status: Optional[str] = Field(None, pattern=r"^(Assigned|Running|Completed|Cancelled)$")
    destination: Optional[str] = Field(None, max_length=100)
    reply_message_id: Optional[str] = None
    remarks: Optional[str] = None


class ProgramResponse(BaseModel):
    program_id: int
    mother_vessel: str
    lighter_vessel: str
    master_mobile: str
    destination: Optional[str] = None
    escort_employee_id: Optional[int] = None
    escort_mobile: Optional[str] = None
    program_date: date
    shift: str
    status: str = "Assigned"
    assignment_time: datetime
    completion_time: Optional[datetime] = None
    contact_id: Optional[int] = None
    whatsapp_message_id: Optional[str] = None
    reply_message_id: Optional[str] = None
    remarks: Optional[str] = None


# ── Cash Transactions ─────────────────────────────────────────

class TransactionCreate(BaseModel):
    employee_id: int
    program_id: Optional[int] = None
    transaction_type: str = Field(..., pattern=r"^(Advance|Food|Conveyance|Salary|Deduction|Other)$")
    amount: Decimal = Field(..., gt=0, max_digits=10, decimal_places=2)
    payment_method: str = Field(..., pattern=r"^(Cash|Bkash|Nagad|Rocket|Bank)$")
    payment_mobile: Optional[str] = Field(None, max_length=20)
    transaction_date: date
    reference_number: Optional[str] = Field(None, max_length=50)
    remarks: Optional[str] = None
    created_by: Optional[str] = Field(None, max_length=50)


class TransactionResponse(BaseModel):
    transaction_id: int
    employee_id: int
    program_id: Optional[int] = None
    transaction_type: str
    amount: Decimal
    payment_method: str
    payment_mobile: Optional[str] = None
    transaction_date: date
    transaction_time: datetime
    status: str = "Completed"
    reference_number: Optional[str] = None
    remarks: Optional[str] = None
    whatsapp_message_id: Optional[str] = None
    created_by: Optional[str] = None


# ── Billing ───────────────────────────────────────────────────

class BillingCreate(BaseModel):
    program_id: int
    contact_id: int
    bill_date: date
    bill_number: Optional[str] = Field(None, max_length=50)
    service_charge: Optional[Decimal] = None
    other_charges: Optional[Decimal] = Field(default=Decimal("0"))
    total_amount: Optional[Decimal] = None
    remarks: Optional[str] = None


class BillingUpdate(BaseModel):
    payment_status: Optional[str] = Field(None, pattern=r"^(Pending|Partial|Paid)$")
    payment_date: Optional[date] = None
    remarks: Optional[str] = None


class BillingResponse(BaseModel):
    bill_id: int
    program_id: int
    contact_id: int
    bill_date: date
    bill_number: Optional[str] = None
    service_charge: Optional[Decimal] = None
    other_charges: Optional[Decimal] = None
    total_amount: Optional[Decimal] = None
    payment_status: str = "Pending"
    payment_date: Optional[date] = None
    remarks: Optional[str] = None
    created_at: datetime


# ── Salary ────────────────────────────────────────────────────

class SalaryGenerateRequest(BaseModel):
    employee_id: int
    month: int = Field(..., ge=1, le=12)
    year: int = Field(..., ge=2020, le=2099)
    basic_salary: Decimal = Field(..., gt=0)
    program_allowance: Optional[Decimal] = Field(default=Decimal("0"))
    other_allowance: Optional[Decimal] = Field(default=Decimal("0"))
    remarks: Optional[str] = None


class SalaryResponse(BaseModel):
    salary_id: int
    employee_id: int
    month: int
    year: int
    basic_salary: Optional[Decimal] = None
    total_programs: int = 0
    program_allowance: Optional[Decimal] = None
    other_allowance: Optional[Decimal] = None
    total_advances: Optional[Decimal] = None
    total_deductions: Optional[Decimal] = None
    net_salary: Optional[Decimal] = None
    payment_date: Optional[date] = None
    payment_status: str = "Pending"
    remarks: Optional[str] = None


# ── Message Templates ─────────────────────────────────────────

class TemplateCreate(BaseModel):
    template_name: str = Field(..., max_length=100)
    template_type: str = Field(..., pattern=r"^(escort_order|payment|general_reply|status_update|query_response)$")
    template_body: str
    required_fields: Optional[list[str]] = None
    optional_fields: Optional[list[str]] = None
    extraction_patterns: Optional[dict] = None


class TemplateResponse(BaseModel):
    template_id: int
    template_name: str
    template_type: str
    template_body: str
    required_fields: Optional[list] = None
    optional_fields: Optional[list] = None
    extraction_patterns: Optional[dict] = None
    is_active: bool = True
    created_at: datetime


# ── WhatsApp Messages ─────────────────────────────────────────

class MessageCreate(BaseModel):
    whatsapp_msg_id: Optional[str] = None
    contact_id: Optional[int] = None
    sender_number: str = Field(..., max_length=20)
    message_type: str = Field(..., pattern=r"^(incoming|outgoing)$")
    content_type: str = Field(default="text", pattern=r"^(text|image|document|audio|video)$")
    message_body: str


class MessageProcessRequest(BaseModel):
    """Request to process an incoming WhatsApp message through WBOM pipeline."""
    sender_number: str
    message_body: str
    whatsapp_msg_id: Optional[str] = None
    content_type: str = "text"


class MessageProcessResponse(BaseModel):
    message_id: int
    classification: str
    confidence: float = 0.5
    extracted_data: dict
    suggested_template: Optional[dict] = None
    draft_reply: Optional[str] = None
    requires_admin_input: bool = True
    missing_fields: list[str] = []
    unfilled_fields: list[str] = []
    confidence_scores: dict = {}


class TemplateCompleteRequest(BaseModel):
    """Admin fills in missing fields and sends completed message."""
    message_id: int
    template_id: int
    field_values: dict
    send_message: bool = False


class TemplateCompleteResponse(BaseModel):
    completed_message: str
    is_sent: bool = False
    sent_message_id: Optional[str] = None
    data_saved: bool = False


# ── Contact Profile (Phase 4 §4.1) ────────────────────────────

class ContactProfileCard(BaseModel):
    contact_id: int
    whatsapp_number: str
    display_name: str
    company_name: Optional[str] = None
    relation_type: Optional[str] = None
    business_type: Optional[str] = None
    is_active: bool = True
    assigned_templates_count: int = 0
    recent_interactions_count: int = 0
    pending_programs_count: int = 0


# ── Validation (Phase 4 §4.3) ────────────────────────────────

class ValidationRequest(BaseModel):
    mobile_number: Optional[str] = None
    employee_name: Optional[str] = None
    mother_vessel: Optional[str] = None
    lighter_vessel: Optional[str] = None
    amount: Optional[str] = None


class ValidationItem(BaseModel):
    field: str
    value: Optional[str] = None
    valid: bool
    message: str


class ValidationResponse(BaseModel):
    all_valid: bool
    items: list[ValidationItem]


# ── Order Processing (Phase 5 §5.1) ──────────────────────────

class OrderProcessRequest(BaseModel):
    message_id: int
    sender_number: str
    message_body: str
    contact_id: Optional[int] = None


class OrderProcessResponse(BaseModel):
    message_id: int
    classification: str = "escort_order"
    extracted_data: dict
    suggested_template: Optional[dict] = None
    draft_reply: Optional[str] = None
    requires_admin_input: bool = True
    missing_fields: list[str] = []
    unfilled_fields: list[str] = []
    confidence_scores: dict = {}


class SaveProgramRequest(BaseModel):
    message_id: int
    extracted_data: dict
    contact_id: Optional[int] = None
    admin_overrides: Optional[dict] = None


# ── Payment Processing (Phase 5 §5.2) ────────────────────────

class PaymentProcessRequest(BaseModel):
    message_id: int
    sender_number: str
    message_body: str
    contact_id: Optional[int] = None


class PaymentProcessResponse(BaseModel):
    message_id: int
    classification: str = "payment"
    extracted_data: dict
    employee: Optional[dict] = None
    transaction: Optional[dict] = None
    transaction_type: Optional[str] = None
    payment_method: Optional[str] = None
    amount: Optional[str] = None
    requires_admin_input: bool = True
    missing_fields: list[str] = []


# ── Conversation Handling (Phase 5 §5.3) ─────────────────────

class ConversationRequest(BaseModel):
    message_id: int
    sender_number: str
    message_body: str
    contact_id: Optional[int] = None


class ConversationResponse(BaseModel):
    message_id: int
    classification: str = "general"
    intent: str
    handler_used: str
    context: dict = {}
    response: dict = {}
    requires_admin_input: bool = False


# ── Quick Actions (Phase 4 §4.2) ─────────────────────────────

class QuickActionResponse(BaseModel):
    success: bool
    message: str
    message_id: int


# ── Field Validation (Phase 6 §6.1) ──────────────────────────

class FieldValidationRequest(BaseModel):
    """Validate arbitrary fields against business rules."""
    fields: dict  # {field_name: value}


class FieldValidationResult(BaseModel):
    field: str
    valid: bool
    value: Optional[str] = None
    error: Optional[str] = None


class FieldValidationResponse(BaseModel):
    all_valid: bool
    results: list[FieldValidationResult]


# ── Subagent API (Phase 7 §7.1) ──────────────────────────────

class SubagentMessageRequest(BaseModel):
    """Inbound message from core module."""
    sender_number: str
    message_body: str
    whatsapp_msg_id: Optional[str] = None
    token: Optional[str] = None


class SubagentMessageResponse(BaseModel):
    status: str = "success"
    message_id: int
    classification: str
    confidence: float
    template: Optional[dict] = None
    requires_admin_input: list[str] = []


class TemplateCompletionRequest(BaseModel):
    """Admin completes and sends a template."""
    message_id: int
    template_id: int
    completed_message: str
    recipient_number: str
    message_type: str  # escort_order | payment
    template_data: dict  # filled field values


class TemplateCompletionResponse(BaseModel):
    status: str = "success"
    sent_message_id: Optional[str] = None
    database_records: Optional[dict] = None


# ── Reports (Phase 7 §7.1) ───────────────────────────────────

class SalaryReportResponse(BaseModel):
    salary_summary: dict
    programs: list[dict] = []
    transactions: list[dict] = []


class BillingReportResponse(BaseModel):
    contact_id: int
    period: dict
    total_programs: int
    service_charge: float
    total_amount: float
    programs: list[dict] = []


# ── Search ────────────────────────────────────────────────────

class AdvancedSearchRequest(BaseModel):
    query: str
    search_in: list[str] = Field(default=["contacts", "employees", "programs"])
    date_from: Optional[date] = None
    date_to: Optional[date] = None
    limit: int = Field(default=20, le=100)


class SearchResult(BaseModel):
    source: str
    items: list[dict]
    total: int


# ── Multi-lighter (Phase 8 §Scenario 3) ──────────────────────

class MultiLighterProcessRequest(BaseModel):
    """Request to process a message with multiple lighter entries."""
    message_id: int
    sender_number: str
    message_body: str
    contact_id: Optional[int] = None


class MultiLighterExtractedField(BaseModel):
    value: Optional[str] = None
    confidence: float = 0.0


class MultiLighterEntry(BaseModel):
    lighter_vessel: MultiLighterExtractedField
    capacity: MultiLighterExtractedField
    destination: MultiLighterExtractedField
    mobile_number: MultiLighterExtractedField


class MultiLighterProcessResponse(BaseModel):
    message_id: int
    classification: str = "escort_order"
    is_multi_lighter: bool = True
    lighter_count: int
    mother_vessel: MultiLighterExtractedField
    date: MultiLighterExtractedField
    lighters: list[dict]
    draft_reply: Optional[str] = None
    requires_admin_input: bool = False
    missing_by_lighter: list[dict] = []


class MultiLighterSaveRequest(BaseModel):
    """Save multiple lighter programs from a processed multi-lighter message."""
    message_id: int
    contact_id: Optional[int] = None
    multi_data: dict
    admin_overrides: Optional[list[dict]] = None
