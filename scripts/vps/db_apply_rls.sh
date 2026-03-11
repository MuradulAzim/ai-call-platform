#!/usr/bin/env bash
# ============================================================
# Phase 4 — Apply RLS Policies to PostgreSQL
# Runs idempotent RLS SQL inside the postgres container
# ============================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# ── Defaults ────────────────────────────────────────────────
CONTAINER="ai-postgres"
DB=""
SQL_FILE="$REPO_ROOT/db/rls/rls_policies_idempotent.sql"
DRY_RUN=0
PG_USER="postgres"

# ── Parse args ──────────────────────────────────────────────
usage() {
  echo "Usage: $0 --db <database_name> [--container <name>] [--sql <path>] [--dry-run]"
  echo ""
  echo "Options:"
  echo "  --db          Target database name (required)"
  echo "  --container   Docker container name (default: ai-postgres)"
  echo "  --sql         Path to SQL file (default: db/rls/rls_policies_idempotent.sql)"
  echo "  --dry-run     Print what would be applied, do not execute"
  exit 1
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --container) CONTAINER="$2"; shift 2 ;;
    --db)        DB="$2"; shift 2 ;;
    --sql)       SQL_FILE="$2"; shift 2 ;;
    --dry-run)   DRY_RUN=1; shift ;;
    -h|--help)   usage ;;
    *)           echo "ERROR: Unknown option: $1"; usage ;;
  esac
done

if [[ -z "$DB" ]]; then
  echo "ERROR: --db is required"
  usage
fi

if [[ ! -f "$SQL_FILE" ]]; then
  echo "ERROR: SQL file not found: $SQL_FILE"
  exit 1
fi

echo "=== Phase 4 — Apply RLS Policies ==="
echo "Container : $CONTAINER"
echo "Database  : $DB"
echo "SQL File  : $SQL_FILE"
echo "Dry Run   : $( [[ $DRY_RUN -eq 1 ]] && echo 'YES' || echo 'NO' )"
echo "Timestamp : $(date -u '+%Y-%m-%dT%H:%M:%SZ')"
echo ""

# ── Run pre-checks ──────────────────────────────────────────
echo "--- Running pre-checks ---"
"$SCRIPT_DIR/db_precheck.sh" --db "$DB" --container "$CONTAINER"
echo ""

# ── Dry-run mode ─────────────────────────────────────────────
if [[ $DRY_RUN -eq 1 ]]; then
  echo "--- DRY RUN: SQL that would be applied ---"
  cat "$SQL_FILE"
  echo ""
  echo "--- DRY RUN complete. No changes made. ---"
  exit 0
fi

# ── Apply SQL in single transaction ──────────────────────────
echo "--- Applying RLS policies ---"
docker exec -i "$CONTAINER" psql \
  -U "$PG_USER" \
  -d "$DB" \
  -v ON_ERROR_STOP=1 \
  --single-transaction \
  < "$SQL_FILE"

EXIT_CODE=$?
if [[ $EXIT_CODE -eq 0 ]]; then
  echo ""
  echo "=== RLS policies applied successfully ==="
  echo "Completed: $(date -u '+%Y-%m-%dT%H:%M:%SZ')"
else
  echo ""
  echo "=== ERROR: RLS apply failed (exit code $EXIT_CODE) ==="
  echo "No changes were committed (single-transaction mode)."
  exit $EXIT_CODE
fi
