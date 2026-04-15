"""
Import contacts.csv (Google Contacts export) into wbom_contacts.
Generates a SQL file then executes it on VPS via SSH + docker exec.
"""
import csv
import re
import subprocess
import sys
import tempfile
import os

CSV_PATH = os.path.join(os.path.dirname(__file__), "contacts.csv")
SSH_HOST = "azim@5.189.131.48"
CONTAINER = "ai-postgres"
DB_USER = "postgres"

# ── Relation type mapping (must match wbom_relation_types seed data) ──
# 1=Client, 2=Vendor, 3=Partner, 4=Employee
EMPLOYEE_KEYWORDS = [
    "al-aqsa", "al aqsa", "alaqsa", "security guard", "sg ",
    "escort", "seal-man", "supervisor"
]


def normalize_phone(raw: str) -> str | None:
    """Convert any phone format to 01XXXXXXXXX (11 digits, BD mobile)."""
    if not raw or not raw.strip():
        return None
    digits = re.sub(r"[^0-9]", "", raw.strip())
    if not digits:
        return None
    # +880 prefix → strip to local
    if digits.startswith("880") and len(digits) >= 13:
        digits = "0" + digits[3:]
    # Already starts with 0
    if digits.startswith("0") and len(digits) == 11:
        return digits
    # Missing leading 0
    if len(digits) == 10 and digits[0] in "1":
        return "0" + digits
    # Return as-is if it looks like a valid number
    if len(digits) >= 10:
        if not digits.startswith("0"):
            digits = "0" + digits
        return digits[:20]  # cap length
    return None


def classify_relation(name: str, org: str, labels: str) -> int:
    """Return relation_type_id: 1=Client, 2=Vendor, 3=Partner, 4=Employee."""
    combined = f"{name} {org} {labels}".lower()
    for kw in EMPLOYEE_KEYWORDS:
        if kw in combined:
            return 4  # Employee
    return 1  # Default to Client


def escape_sql(val: str) -> str:
    """Escape single quotes for SQL strings."""
    if not val:
        return ""
    return val.replace("'", "''").strip()


def main():
    if not os.path.exists(CSV_PATH):
        print(f"ERROR: {CSV_PATH} not found")
        sys.exit(1)

    contacts = []
    seen_phones = set()

    with open(CSV_PATH, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            first = row.get("First Name", "").strip()
            middle = row.get("Middle Name", "").strip()
            last = row.get("Last Name", "").strip()
            parts = [p for p in [first, middle, last] if p]
            display_name = " ".join(parts) if parts else None

            phone_raw = row.get("Phone 1 - Value", "").strip()
            phone = normalize_phone(phone_raw)

            if not display_name or not phone:
                continue
            if phone in seen_phones:
                continue
            seen_phones.add(phone)

            org = row.get("Organization Name", "").strip()
            labels = row.get("Labels", "").strip()
            notes = row.get("Notes", "").strip()

            relation_id = classify_relation(display_name, org, labels)

            contacts.append({
                "phone": phone,
                "name": escape_sql(display_name),
                "company": escape_sql(org),
                "relation_type_id": relation_id,
                "notes": escape_sql(notes),
            })

    if not contacts:
        print("No valid contacts found in CSV")
        sys.exit(1)

    print(f"Parsed {len(contacts)} unique contacts from CSV")

    # Generate SQL
    sql_lines = [
        "BEGIN;",
        "",
        "-- Import contacts from Google Contacts CSV",
    ]

    for c in contacts:
        company = f"'{c['company']}'" if c["company"] else "NULL"
        notes = f"'{c['notes']}'" if c["notes"] else "NULL"
        sql_lines.append(
            f"INSERT INTO wbom_contacts "
            f"(whatsapp_number, display_name, company_name, relation_type_id, notes) "
            f"VALUES ('{c['phone']}', '{c['name']}', {company}, {c['relation_type_id']}, {notes}) "
            f"ON CONFLICT (whatsapp_number) DO UPDATE SET "
            f"display_name = EXCLUDED.display_name, "
            f"company_name = COALESCE(EXCLUDED.company_name, wbom_contacts.company_name), "
            f"updated_at = NOW();"
        )

    sql_lines.append("")
    sql_lines.append("SELECT COUNT(*) AS total_contacts FROM wbom_contacts;")
    sql_lines.append("")
    sql_lines.append("COMMIT;")

    sql_content = "\n".join(sql_lines)

    # Write to temp file
    sql_file = os.path.join(tempfile.gettempdir(), "import_contacts_wbom.sql")
    with open(sql_file, "w", encoding="utf-8") as f:
        f.write(sql_content)
    print(f"Generated SQL: {sql_file} ({len(contacts)} INSERT statements)")

    # Upload and execute on VPS
    print("\nUploading SQL to VPS...")
    scp_cmd = f'scp "{sql_file}" {SSH_HOST}:/tmp/import_contacts_wbom.sql'
    result = subprocess.run(scp_cmd, shell=True, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"SCP failed: {result.stderr}")
        sys.exit(1)

    print("Executing on VPS...")
    ssh_cmd = (
        f'ssh {SSH_HOST} "docker exec -i {CONTAINER} '
        f"psql -U {DB_USER} -f /tmp/import_contacts_wbom.sql"
        f'"'
    )
    # The file is inside the container? No, it's on the host. Need to pipe it.
    ssh_cmd = (
        f'ssh {SSH_HOST} "cat /tmp/import_contacts_wbom.sql | '
        f'docker exec -i {CONTAINER} psql -U {DB_USER}"'
    )
    result = subprocess.run(ssh_cmd, shell=True, capture_output=True, text=True)
    print(result.stdout)
    if result.stderr:
        # psql often puts notices in stderr
        for line in result.stderr.split("\n"):
            if "ERROR" in line or "FATAL" in line:
                print(f"ERROR: {line}")
            elif line.strip():
                print(f"  {line}")
    if result.returncode != 0:
        print(f"Execution failed with code {result.returncode}")
        sys.exit(1)

    print("\nContacts import complete!")


if __name__ == "__main__":
    main()
