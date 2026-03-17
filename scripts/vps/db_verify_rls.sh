#!/usr/bin/env bash
# ============================================================
# Phase 4 — Verify RLS Policies on PostgreSQL
# Checks that RLS is enabled/forced and policies exist
# ============================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# ── Defaults ────────────────────────────────────────────────
CONTAINER="ai-postgres"
DB=""
SQL_FILE="$REPO_ROOT/db/rls/rls_policies_idempotent.sql"
PG_USER="postgres"

# ── Parse args ──────────────────────────────────────────────
usage() {
  echo "Usage: $0 --db <database_name> [--container <name>]"
  echo ""
  echo "Options:"
  echo "  --db          Target database name (required)"
  echo "  --container   Docker container name (default: ai-postgres)"
  exit 1
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --container) CONTAINER="$2"; shift 2 ;;
    --db)        DB="$2"; shift 2 ;;
    -h|--help)   usage ;;
    *)           echo "ERROR: Unknown option: $1"; usage ;;
  esac
done

if [[ -z "$DB" ]]; then
  echo "ERROR: --db is required"
  usage
fi

echo "=== Phase 4 — Verify RLS ==="
echo "Container : $CONTAINER"
echo "Database  : $DB"
echo "Timestamp : $(date -u '+%Y-%m-%dT%H:%M:%SZ')"
echo ""

FAIL=0

# ── Derive expected tables from the SQL file ─────────────────
# Parse "ALTER TABLE ... ENABLE ROW LEVEL SECURITY" lines
EXPECTED_TABLES=()
if [[ -f "$SQL_FILE" ]]; then
  while IFS= read -r tbl; do
    # Strip schema prefix if present
    tbl="${tbl#public.}"
    EXPECTED_TABLES+=("$tbl")
  done < <(grep -iE '^\s*ALTER\s+TABLE\s+(IF\s+EXISTS\s+)?[^ ]+\s+ENABLE\s+ROW\s+LEVEL\s+SECURITY' "$SQL_FILE" \
    | sed -E 's/.*ALTER\s+TABLE\s+(IF\s+EXISTS\s+)?([^ ]+)\s+ENABLE.*/\2/i' \
    | sort -u)
fi

if [[ ${#EXPECTED_TABLES[@]} -eq 0 ]]; then
  echo "WARN: Could not derive expected tables from SQL file; checking all public tables."
fi

echo "Expected RLS tables: ${EXPECTED_TABLES[*]:-<all public>}"
echo ""

# ── 1. Check RLS enabled/forced per table ────────────────────
echo "--- RLS Status on Tables ---"
RLS_OUTPUT=$(docker exec -i "$CONTAINER" psql -U "$PG_USER" -d "$DB" -tA -v ON_ERROR_STOP=1 <<'EOSQL'
SELECT c.relname,
       c.relrowsecurity::text,
       c.relforcerowsecurity::text
FROM pg_class c
JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE c.relkind = 'r'
  AND n.nspname = 'public'
ORDER BY c.relname;
EOSQL
)

printf "%-30s %-15s %-15s\n" "TABLE" "RLS_ENABLED" "RLS_FORCED"
printf "%-30s %-15s %-15s\n" "-----" "-----------" "----------"

while IFS='|' read -r tname renabled rforced; do
  [[ -z "$tname" ]] && continue
  printf "%-30s %-15s %-15s\n" "$tname" "$renabled" "$rforced"
done <<< "$RLS_OUTPUT"

echo ""

# ── Verify expected tables have RLS enabled + forced ─────────
for tbl in "${EXPECTED_TABLES[@]}"; do
  tbl_clean="${tbl#public.}"
  ROW=$(echo "$RLS_OUTPUT" | grep "^${tbl_clean}|" || true)
  if [[ -z "$ROW" ]]; then
    echo "FAIL: Table '$tbl_clean' not found in database"
    FAIL=1
    continue
  fi
  ENABLED=$(echo "$ROW" | cut -d'|' -f2)
  FORCED=$(echo "$ROW" | cut -d'|' -f3)
  if [[ "$ENABLED" != "true" ]]; then
    echo "FAIL: Table '$tbl_clean' — relrowsecurity is NOT enabled"
    FAIL=1
  fi
  if [[ "$FORCED" != "true" ]]; then
    echo "FAIL: Table '$tbl_clean' — relforcerowsecurity is NOT forced"
    FAIL=1
  fi
done

# ── 2. List policies by table ────────────────────────────────
echo "--- Policies Installed ---"
POLICY_OUTPUT=$(docker exec -i "$CONTAINER" psql -U "$PG_USER" -d "$DB" -v ON_ERROR_STOP=1 <<'EOSQL'
SELECT schemaname, tablename, policyname, cmd
FROM pg_policies
WHERE schemaname = 'public'
ORDER BY tablename, policyname;
EOSQL
)

echo "$POLICY_OUTPUT"
echo ""

# ── Policy summary count ─────────────────────────────────────
echo "--- Policy Count by Table ---"
docker exec -i "$CONTAINER" psql -U "$PG_USER" -d "$DB" -v ON_ERROR_STOP=1 <<'EOSQL'
SELECT schemaname, tablename, COUNT(*) AS policy_count
FROM pg_policies
WHERE schemaname = 'public'
GROUP BY schemaname, tablename
ORDER BY schemaname, tablename;
EOSQL

echo ""

# ── Verify expected policies exist ───────────────────────────
# Derive expected policy names from the SQL file
EXPECTED_POLICIES=()
if [[ -f "$SQL_FILE" ]]; then
  while IFS= read -r pname; do
    EXPECTED_POLICIES+=("$pname")
  done < <(grep -iE "policyname\s*=\s*'" "$SQL_FILE" \
    | sed -E "s/.*policyname\s*=\s*'([^']+)'.*/\1/" \
    | sort -u)
fi

if [[ ${#EXPECTED_POLICIES[@]} -gt 0 ]]; then
  echo "--- Checking Expected Policies ---"
  INSTALLED_POLICIES=$(docker exec -i "$CONTAINER" psql -U "$PG_USER" -d "$DB" -tAc \
    "SELECT policyname FROM pg_policies WHERE schemaname='public';" 2>/dev/null || true)

  for pol in "${EXPECTED_POLICIES[@]}"; do
    if echo "$INSTALLED_POLICIES" | grep -qx "$pol"; then
      echo "  OK: $pol"
    else
      echo "  FAIL: policy '$pol' NOT FOUND"
      FAIL=1
    fi
  done
  echo ""
fi

# ── Result ──────────────────────────────────────────────────
if [[ $FAIL -ne 0 ]]; then
  echo "=== VERIFICATION FAILED ==="
  exit 1
else
  echo "=== VERIFICATION PASSED ==="
  exit 0
fi
