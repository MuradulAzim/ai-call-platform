-- ============================================================
-- 018: WBOM Case/Workflow Foundation
-- Adds case-centric workflow backbone for complaints/orders/HR/payroll
-- ============================================================

-- Case root: one row per operational issue/order/request lifecycle
CREATE TABLE IF NOT EXISTS wbom_cases (
    case_id BIGSERIAL PRIMARY KEY,
    case_type VARCHAR(40) NOT NULL,
    source_platform VARCHAR(20) NOT NULL DEFAULT 'whatsapp',
    source_channel VARCHAR(40) NOT NULL DEFAULT 'inbound_message',
    contact_id INT REFERENCES wbom_contacts(contact_id),
    employee_id INT REFERENCES wbom_employees(employee_id),
    related_program_id INT REFERENCES wbom_escort_programs(program_id),
    title VARCHAR(200) NOT NULL,
    description TEXT,
    priority VARCHAR(20) NOT NULL DEFAULT 'normal',
    severity VARCHAR(20) NOT NULL DEFAULT 'medium',
    status VARCHAR(30) NOT NULL DEFAULT 'open',
    owner_role VARCHAR(30),
    owner_user VARCHAR(80),
    opened_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    first_response_at TIMESTAMPTZ,
    due_at TIMESTAMPTZ,
    resolved_at TIMESTAMPTZ,
    closed_at TIMESTAMPTZ,
    resolution_summary TEXT,
    metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_wbom_cases_priority CHECK (priority IN ('low', 'normal', 'high', 'urgent')),
    CONSTRAINT chk_wbom_cases_severity CHECK (severity IN ('low', 'medium', 'high', 'critical')),
    CONSTRAINT chk_wbom_cases_status CHECK (
        status IN ('open', 'in_progress', 'waiting_customer', 'waiting_internal', 'resolved', 'closed', 'cancelled')
    )
);

CREATE INDEX IF NOT EXISTS idx_wbom_cases_status_due ON wbom_cases (status, due_at);
CREATE INDEX IF NOT EXISTS idx_wbom_cases_type_status ON wbom_cases (case_type, status);
CREATE INDEX IF NOT EXISTS idx_wbom_cases_contact ON wbom_cases (contact_id);
CREATE INDEX IF NOT EXISTS idx_wbom_cases_employee ON wbom_cases (employee_id);
CREATE INDEX IF NOT EXISTS idx_wbom_cases_opened_at ON wbom_cases (opened_at DESC);

-- Immutable event stream: timeline of every important transition/action
CREATE TABLE IF NOT EXISTS wbom_case_events (
    event_id BIGSERIAL PRIMARY KEY,
    case_id BIGINT NOT NULL REFERENCES wbom_cases(case_id) ON DELETE CASCADE,
    event_type VARCHAR(60) NOT NULL,
    actor_type VARCHAR(30) NOT NULL DEFAULT 'system',
    actor_id VARCHAR(120),
    event_source VARCHAR(40) NOT NULL DEFAULT 'api',
    message_id INT REFERENCES wbom_whatsapp_messages(message_id),
    old_status VARCHAR(30),
    new_status VARCHAR(30),
    note TEXT,
    payload_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_wbom_case_events_case_created ON wbom_case_events (case_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_wbom_case_events_type ON wbom_case_events (event_type, created_at DESC);

-- Action queue: pending tasks/approvals/reminders tied to cases
CREATE TABLE IF NOT EXISTS wbom_workflow_tasks (
    workflow_task_id BIGSERIAL PRIMARY KEY,
    case_id BIGINT NOT NULL REFERENCES wbom_cases(case_id) ON DELETE CASCADE,
    task_type VARCHAR(50) NOT NULL,
    task_title VARCHAR(200) NOT NULL,
    task_status VARCHAR(30) NOT NULL DEFAULT 'pending',
    approval_required BOOLEAN NOT NULL DEFAULT FALSE,
    assignee_role VARCHAR(30),
    assignee_user VARCHAR(80),
    requester VARCHAR(80),
    due_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    completion_note TEXT,
    correlation_key VARCHAR(120),
    payload_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_wbom_workflow_task_status CHECK (
        task_status IN ('pending', 'in_progress', 'approved', 'rejected', 'completed', 'cancelled', 'failed')
    )
);

CREATE INDEX IF NOT EXISTS idx_wbom_workflow_tasks_status_due ON wbom_workflow_tasks (task_status, due_at);
CREATE INDEX IF NOT EXISTS idx_wbom_workflow_tasks_case ON wbom_workflow_tasks (case_id, created_at DESC);
CREATE UNIQUE INDEX IF NOT EXISTS idx_wbom_workflow_tasks_corr_key ON wbom_workflow_tasks (correlation_key)
    WHERE correlation_key IS NOT NULL AND correlation_key != '';

-- SLA policy table: response/resolve targets by case type + severity
CREATE TABLE IF NOT EXISTS wbom_sla_policies (
    sla_policy_id BIGSERIAL PRIMARY KEY,
    case_type VARCHAR(40) NOT NULL,
    severity VARCHAR(20) NOT NULL,
    first_response_minutes INT NOT NULL,
    resolution_minutes INT,
    escalation_after_minutes INT,
    active BOOLEAN NOT NULL DEFAULT TRUE,
    policy_name VARCHAR(120),
    metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_wbom_sla_severity CHECK (severity IN ('low', 'medium', 'high', 'critical')),
    CONSTRAINT chk_wbom_sla_positive_response CHECK (first_response_minutes > 0),
    CONSTRAINT chk_wbom_sla_positive_resolution CHECK (resolution_minutes IS NULL OR resolution_minutes > 0),
    CONSTRAINT chk_wbom_sla_positive_escalation CHECK (escalation_after_minutes IS NULL OR escalation_after_minutes > 0)
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_wbom_sla_unique_active
    ON wbom_sla_policies (case_type, severity, active)
    WHERE active = TRUE;

-- Escalation rules: who gets notified at which level
CREATE TABLE IF NOT EXISTS wbom_escalation_rules (
    escalation_rule_id BIGSERIAL PRIMARY KEY,
    case_type VARCHAR(40) NOT NULL,
    severity VARCHAR(20) NOT NULL,
    escalation_level INT NOT NULL,
    target_role VARCHAR(30) NOT NULL,
    target_user VARCHAR(80),
    notify_channel VARCHAR(30) NOT NULL DEFAULT 'whatsapp',
    active BOOLEAN NOT NULL DEFAULT TRUE,
    metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_wbom_escalation_severity CHECK (severity IN ('low', 'medium', 'high', 'critical')),
    CONSTRAINT chk_wbom_escalation_level CHECK (escalation_level >= 1)
);

CREATE INDEX IF NOT EXISTS idx_wbom_escalation_rule_lookup
    ON wbom_escalation_rules (case_type, severity, escalation_level)
    WHERE active = TRUE;

-- Parser feedback loop: extracted vs corrected values for learning
CREATE TABLE IF NOT EXISTS wbom_parser_feedback (
    parser_feedback_id BIGSERIAL PRIMARY KEY,
    source_message_id INT REFERENCES wbom_whatsapp_messages(message_id) ON DELETE SET NULL,
    case_id BIGINT REFERENCES wbom_cases(case_id) ON DELETE SET NULL,
    parser_name VARCHAR(80) NOT NULL DEFAULT 'default',
    field_name VARCHAR(80) NOT NULL,
    extracted_value TEXT,
    corrected_value TEXT,
    confidence NUMERIC(5,4),
    accepted BOOLEAN,
    corrected_by VARCHAR(80),
    correction_reason TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_wbom_parser_feedback_message ON wbom_parser_feedback (source_message_id);
CREATE INDEX IF NOT EXISTS idx_wbom_parser_feedback_field ON wbom_parser_feedback (field_name, created_at DESC);

-- Identity graph table: links same person across channels/identifiers
CREATE TABLE IF NOT EXISTS wbom_identity_links (
    identity_link_id BIGSERIAL PRIMARY KEY,
    identity_key VARCHAR(120) NOT NULL,
    platform VARCHAR(20) NOT NULL,
    platform_user_id VARCHAR(200) NOT NULL,
    contact_id INT REFERENCES wbom_contacts(contact_id) ON DELETE SET NULL,
    confidence NUMERIC(5,4) NOT NULL DEFAULT 1.0000,
    linked_by VARCHAR(40) NOT NULL DEFAULT 'system',
    active BOOLEAN NOT NULL DEFAULT TRUE,
    metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_wbom_identity_confidence CHECK (confidence >= 0 AND confidence <= 1)
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_wbom_identity_platform_user
    ON wbom_identity_links (platform, platform_user_id);
CREATE INDEX IF NOT EXISTS idx_wbom_identity_key_active
    ON wbom_identity_links (identity_key, active);

-- Message intent snapshot: captures intent/entity/confidence at decision time
CREATE TABLE IF NOT EXISTS wbom_message_intents (
    message_intent_id BIGSERIAL PRIMARY KEY,
    message_id INT NOT NULL REFERENCES wbom_whatsapp_messages(message_id) ON DELETE CASCADE,
    case_id BIGINT REFERENCES wbom_cases(case_id) ON DELETE SET NULL,
    intent_name VARCHAR(80) NOT NULL,
    route_name VARCHAR(80),
    sender_role VARCHAR(40),
    confidence NUMERIC(5,4),
    secondary_intents JSONB NOT NULL DEFAULT '[]'::jsonb,
    entities_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    policy_decision VARCHAR(30) NOT NULL DEFAULT 'auto',
    policy_reason TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_wbom_message_intent_confidence CHECK (confidence IS NULL OR (confidence >= 0 AND confidence <= 1))
);

CREATE INDEX IF NOT EXISTS idx_wbom_message_intents_message ON wbom_message_intents (message_id);
CREATE INDEX IF NOT EXISTS idx_wbom_message_intents_intent ON wbom_message_intents (intent_name, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_wbom_message_intents_case ON wbom_message_intents (case_id, created_at DESC);

-- Helpful defaults for complaint and order SLA behavior
INSERT INTO wbom_sla_policies (case_type, severity, first_response_minutes, resolution_minutes, escalation_after_minutes, active, policy_name)
VALUES
    ('complaint', 'critical', 15, 120, 30, TRUE, 'complaint-critical-default'),
    ('complaint', 'high', 30, 480, 60, TRUE, 'complaint-high-default'),
    ('complaint', 'medium', 120, 1440, 240, TRUE, 'complaint-medium-default'),
    ('order', 'high', 15, 180, 30, TRUE, 'order-high-default'),
    ('employee_request', 'medium', 240, 1440, 480, TRUE, 'employee-request-default')
ON CONFLICT DO NOTHING;

INSERT INTO wbom_escalation_rules (case_type, severity, escalation_level, target_role, notify_channel, active)
VALUES
    ('complaint', 'critical', 1, 'supervisor', 'whatsapp', TRUE),
    ('complaint', 'critical', 2, 'owner', 'whatsapp', TRUE),
    ('complaint', 'high', 1, 'operation_manager', 'whatsapp', TRUE),
    ('order', 'high', 1, 'operation_manager', 'whatsapp', TRUE),
    ('employee_request', 'medium', 1, 'hr_manager', 'whatsapp', TRUE)
ON CONFLICT DO NOTHING;
