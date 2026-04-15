-- ============================================================
-- WBOM (WhatsApp Business Operations Manager) Tables
-- Migration 009 — Al-Aqsa Security Service business operations
-- ============================================================

-- 1. Relation Types
CREATE TABLE IF NOT EXISTS wbom_relation_types (
    relation_type_id SERIAL PRIMARY KEY,
    relation_name VARCHAR(50) NOT NULL,
    description TEXT,
    greeting_template TEXT,
    is_active BOOLEAN DEFAULT TRUE
);

INSERT INTO wbom_relation_types (relation_name, description, greeting_template)
VALUES
    ('Client', 'Regular business client', 'Dear {name}, thank you for choosing Al-Aqsa Security Service.'),
    ('Vendor', 'Service provider or supplier', 'Hello {name}, greetings from Al-Aqsa Security.'),
    ('Partner', 'Business partner', 'Assalamu Alaikum {name}, hope you are doing well.'),
    ('Employee', 'Internal staff member', 'Hello {name},')
ON CONFLICT DO NOTHING;

-- 2. Business Types
CREATE TABLE IF NOT EXISTS wbom_business_types (
    business_type_id SERIAL PRIMARY KEY,
    business_name VARCHAR(100) NOT NULL,
    service_category VARCHAR(50),
    default_templates JSONB,
    is_active BOOLEAN DEFAULT TRUE
);

INSERT INTO wbom_business_types (business_name, service_category, default_templates)
VALUES
    ('Shipping Company', 'Maritime', '[1,2,3]'),
    ('Import/Export Agent', 'Maritime', '[1,2]'),
    ('Construction Company', 'Land Security', '[4,5]'),
    ('Factory', 'Land Security', '[5,6]'),
    ('Bank', 'Land Security', '[6,7]')
ON CONFLICT DO NOTHING;

-- 3. Contacts
CREATE TABLE IF NOT EXISTS wbom_contacts (
    contact_id SERIAL PRIMARY KEY,
    whatsapp_number VARCHAR(20) UNIQUE NOT NULL,
    display_name VARCHAR(100) NOT NULL,
    company_name VARCHAR(150),
    relation_type_id INT REFERENCES wbom_relation_types(relation_type_id),
    business_type_id INT REFERENCES wbom_business_types(business_type_id),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    notes TEXT
);

CREATE INDEX IF NOT EXISTS idx_wbom_contacts_whatsapp ON wbom_contacts (whatsapp_number);
CREATE INDEX IF NOT EXISTS idx_wbom_contacts_name ON wbom_contacts (display_name);

-- 4. Message Templates
CREATE TABLE IF NOT EXISTS wbom_message_templates (
    template_id SERIAL PRIMARY KEY,
    template_name VARCHAR(100) NOT NULL,
    template_type VARCHAR(30) NOT NULL CHECK (template_type IN ('escort_order', 'payment', 'general_reply', 'status_update', 'query_response')),
    template_body TEXT NOT NULL,
    required_fields JSONB,
    optional_fields JSONB,
    extraction_patterns JSONB,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

INSERT INTO wbom_message_templates (template_name, template_type, template_body, required_fields, extraction_patterns)
VALUES
(
    'Escort Service Reply',
    'escort_order',
    E'Mv.{mother_vessel}\nLighter: {lighter_vessel}\n{master_mobile}\nEscort name: {escort_name}\nEscort Mobile: {escort_mobile}\n{date}({shift})\nAl-Aqsa Security Service',
    '["mother_vessel", "lighter_vessel", "master_mobile", "escort_name", "escort_mobile", "date", "shift"]',
    '{"mother_vessel": "(?i)m\\.?v\\.?\\s*([\\w\\s-]+?)(?:/|\\n|lighter|capacity)", "lighter_vessel": "(?i)(?:lighter[:\\s]*|mv[:\\.\\s]+)([\\w\\s-]+?)(?=\\s*cap|\\s*\\d{10,}|\\s*dest|\\s*mob)", "mobile": "\\b(0\\d{10})\\b|\\+880(\\d{10})\\b"}'
),
(
    'Payment Acknowledgment',
    'payment',
    E'ID: {employee_mobile}\n{employee_name}\n{payment_mobile}({payment_method})\n{amount}/-\nStatus: {status}\nRemarks: {remarks}',
    '["employee_mobile", "employee_name", "payment_mobile", "payment_method", "amount", "status"]',
    '{"employee_name": "(?:ID:\\s*\\d+\\s+)?([A-Za-z\\s.]+?)(?=\\s*\\d{10,}|\\s*SG|\\s*MAX)", "mobile": "\\b(0\\d{10})\\b", "amount": "(\\d+)/-", "payment_method": "\\((N|B|b|n)\\)"}'
)
ON CONFLICT DO NOTHING;

-- 5. Contact Templates (many-to-many)
CREATE TABLE IF NOT EXISTS wbom_contact_templates (
    id SERIAL PRIMARY KEY,
    contact_id INT NOT NULL REFERENCES wbom_contacts(contact_id) ON DELETE CASCADE,
    template_id INT NOT NULL REFERENCES wbom_message_templates(template_id),
    is_default BOOLEAN DEFAULT FALSE,
    priority INT DEFAULT 0,
    assigned_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (contact_id, template_id)
);

-- 6. Employees
CREATE TABLE IF NOT EXISTS wbom_employees (
    employee_id SERIAL PRIMARY KEY,
    employee_mobile VARCHAR(20) UNIQUE NOT NULL,
    employee_name VARCHAR(100) NOT NULL,
    designation VARCHAR(30) NOT NULL CHECK (designation IN ('Escort', 'Seal-man', 'Security Guard', 'Supervisor', 'Labor')),
    joining_date DATE,
    status VARCHAR(20) DEFAULT 'Active' CHECK (status IN ('Active', 'Inactive', 'On Leave', 'Terminated')),
    bank_account VARCHAR(50),
    emergency_contact VARCHAR(20),
    address TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_wbom_employees_mobile ON wbom_employees (employee_mobile);
CREATE INDEX IF NOT EXISTS idx_wbom_employees_name ON wbom_employees (employee_name);

-- 7. Escort Programs
CREATE TABLE IF NOT EXISTS wbom_escort_programs (
    program_id SERIAL PRIMARY KEY,
    mother_vessel VARCHAR(100) NOT NULL,
    lighter_vessel VARCHAR(100) NOT NULL,
    master_mobile VARCHAR(20) NOT NULL,
    destination VARCHAR(100),
    escort_employee_id INT REFERENCES wbom_employees(employee_id),
    escort_mobile VARCHAR(20),
    program_date DATE NOT NULL,
    shift VARCHAR(1) NOT NULL CHECK (shift IN ('D', 'N')),
    status VARCHAR(20) DEFAULT 'Assigned' CHECK (status IN ('Assigned', 'Running', 'Completed', 'Cancelled')),
    assignment_time TIMESTAMPTZ DEFAULT NOW(),
    completion_time TIMESTAMPTZ,
    contact_id INT REFERENCES wbom_contacts(contact_id),
    whatsapp_message_id VARCHAR(100),
    reply_message_id VARCHAR(100),
    remarks TEXT
);

CREATE INDEX IF NOT EXISTS idx_wbom_programs_mother ON wbom_escort_programs (mother_vessel);
CREATE INDEX IF NOT EXISTS idx_wbom_programs_lighter ON wbom_escort_programs (lighter_vessel);
CREATE INDEX IF NOT EXISTS idx_wbom_programs_date ON wbom_escort_programs (program_date);
CREATE INDEX IF NOT EXISTS idx_wbom_programs_status ON wbom_escort_programs (status);

-- 8. Cash Transactions
CREATE TABLE IF NOT EXISTS wbom_cash_transactions (
    transaction_id SERIAL PRIMARY KEY,
    employee_id INT NOT NULL REFERENCES wbom_employees(employee_id),
    program_id INT REFERENCES wbom_escort_programs(program_id),
    transaction_type VARCHAR(20) NOT NULL CHECK (transaction_type IN ('Advance', 'Food', 'Conveyance', 'Salary', 'Deduction', 'Other')),
    amount DECIMAL(10,2) NOT NULL,
    payment_method VARCHAR(10) NOT NULL CHECK (payment_method IN ('Cash', 'Bkash', 'Nagad', 'Rocket', 'Bank')),
    payment_mobile VARCHAR(20),
    transaction_date DATE NOT NULL,
    transaction_time TIMESTAMPTZ DEFAULT NOW(),
    status VARCHAR(20) DEFAULT 'Completed' CHECK (status IN ('Pending', 'Completed', 'Failed')),
    reference_number VARCHAR(50),
    remarks TEXT,
    whatsapp_message_id VARCHAR(100),
    created_by VARCHAR(50)
);

CREATE INDEX IF NOT EXISTS idx_wbom_transactions_employee ON wbom_cash_transactions (employee_id);
CREATE INDEX IF NOT EXISTS idx_wbom_transactions_date ON wbom_cash_transactions (transaction_date);
CREATE INDEX IF NOT EXISTS idx_wbom_transactions_type ON wbom_cash_transactions (transaction_type);

-- 9. Billing Records
CREATE TABLE IF NOT EXISTS wbom_billing_records (
    bill_id SERIAL PRIMARY KEY,
    program_id INT NOT NULL REFERENCES wbom_escort_programs(program_id),
    contact_id INT NOT NULL REFERENCES wbom_contacts(contact_id),
    bill_date DATE NOT NULL,
    bill_number VARCHAR(50) UNIQUE,
    service_charge DECIMAL(10,2),
    other_charges DECIMAL(10,2) DEFAULT 0,
    total_amount DECIMAL(10,2),
    payment_status VARCHAR(20) DEFAULT 'Pending' CHECK (payment_status IN ('Pending', 'Partial', 'Paid')),
    payment_date DATE,
    remarks TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_wbom_billing_number ON wbom_billing_records (bill_number);
CREATE INDEX IF NOT EXISTS idx_wbom_billing_contact ON wbom_billing_records (contact_id);

-- 10. Salary Records
CREATE TABLE IF NOT EXISTS wbom_salary_records (
    salary_id SERIAL PRIMARY KEY,
    employee_id INT NOT NULL REFERENCES wbom_employees(employee_id),
    month INT NOT NULL,
    year INT NOT NULL,
    basic_salary DECIMAL(10,2),
    total_programs INT DEFAULT 0,
    program_allowance DECIMAL(10,2) DEFAULT 0,
    other_allowance DECIMAL(10,2) DEFAULT 0,
    total_advances DECIMAL(10,2) DEFAULT 0,
    total_deductions DECIMAL(10,2) DEFAULT 0,
    net_salary DECIMAL(10,2),
    payment_date DATE,
    payment_status VARCHAR(20) DEFAULT 'Pending' CHECK (payment_status IN ('Pending', 'Paid')),
    remarks TEXT,
    UNIQUE (employee_id, month, year)
);

-- 11. WhatsApp Messages
CREATE TABLE IF NOT EXISTS wbom_whatsapp_messages (
    message_id SERIAL PRIMARY KEY,
    whatsapp_msg_id VARCHAR(100) UNIQUE,
    contact_id INT REFERENCES wbom_contacts(contact_id),
    sender_number VARCHAR(20) NOT NULL,
    message_type VARCHAR(10) NOT NULL CHECK (message_type IN ('incoming', 'outgoing')),
    content_type VARCHAR(10) DEFAULT 'text' CHECK (content_type IN ('text', 'image', 'document', 'audio', 'video')),
    message_body TEXT NOT NULL,
    classification VARCHAR(20) DEFAULT 'unclassified' CHECK (classification IN ('order', 'payment', 'query', 'general', 'unclassified')),
    is_processed BOOLEAN DEFAULT FALSE,
    template_used_id INT REFERENCES wbom_message_templates(template_id),
    received_at TIMESTAMPTZ DEFAULT NOW(),
    processed_at TIMESTAMPTZ,
    related_program_id INT REFERENCES wbom_escort_programs(program_id),
    related_transaction_id INT REFERENCES wbom_cash_transactions(transaction_id)
);

CREATE INDEX IF NOT EXISTS idx_wbom_messages_sender ON wbom_whatsapp_messages (sender_number);
CREATE INDEX IF NOT EXISTS idx_wbom_messages_received ON wbom_whatsapp_messages (received_at);
CREATE INDEX IF NOT EXISTS idx_wbom_messages_class ON wbom_whatsapp_messages (classification);

-- 12. Extracted Data
CREATE TABLE IF NOT EXISTS wbom_extracted_data (
    extraction_id SERIAL PRIMARY KEY,
    message_id INT NOT NULL REFERENCES wbom_whatsapp_messages(message_id) ON DELETE CASCADE,
    field_name VARCHAR(100) NOT NULL,
    field_value TEXT,
    confidence_score DECIMAL(3,2),
    is_verified BOOLEAN DEFAULT FALSE,
    extracted_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_wbom_extracted_message ON wbom_extracted_data (message_id);

-- 13. Template Generation Log
CREATE TABLE IF NOT EXISTS wbom_template_generation_log (
    log_id SERIAL PRIMARY KEY,
    message_id INT NOT NULL REFERENCES wbom_whatsapp_messages(message_id),
    template_id INT NOT NULL REFERENCES wbom_message_templates(template_id),
    generated_content TEXT NOT NULL,
    admin_modified_content TEXT,
    is_sent BOOLEAN DEFAULT FALSE,
    generated_at TIMESTAMPTZ DEFAULT NOW(),
    sent_at TIMESTAMPTZ
);
