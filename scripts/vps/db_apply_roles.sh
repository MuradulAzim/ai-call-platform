#!/usr/bin/env bash
# ============================================================
# Phase 4 (Optional) — Apply DB Role Hardening
# Creates least-privilege roles and grants
# WARNING: Does NOT switch app credentials automatically
# ============================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# ── Defaults ────────────────────────────────────────────────
CONTAINER="ai-postgres"
DB=""
SQL_FILE="$REPO_ROOT/db/hardening/roles_and_grants.sql"
DRY_RUN=0
PG_USER="postgres"

# ── Parse args ──────────────────────────────────────────────
usage() {
  echo "Usage: $0 --db <database_name> [--container <name>] [--sql <path>] [--dry-run]"
  echo ""
  echo "Options:"
  echo "  --db          Target database name (required)"
  echo "  --container   Docker container name (default: ai-postgres)"
  echo "  --sql         Path to SQL file (default: db/hardening/roles_and_grants.sql)"
  echo "  --dry-run     Print what would be applied, do not execute"
  echo ""
  echo "WARNING: This creates roles but does NOT switch app credentials."
  echo "         You must update .env and restart services separately."
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

echo "=== Phase 4 — Apply Role Hardening (OPTIONAL) ==="
echo "Container : $CONTAINER"
echo "Database  : $DB"
echo "SQL File  : $SQL_FILE"
echo "Dry Run   : $( [[ $DRY_RUN -eq 1 ]] && echo 'YES' || echo 'NO' )"
echo "Timestamp : $(date -u '+%Y-%m-%dT%H:%M:%SZ')"
echo ""
echo "WARNING: This creates roles/grants only."
echo "         App credentials are NOT changed automatically."
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
echo "--- Applying role hardening ---"
docker exec -i "$CONTAINER" psql \
  -U "$PG_USER" \
  -d "$DB" \
  -v ON_ERROR_STOP=1 \
  --single-transaction \
  < "$SQL_FILE"

EXIT_CODE=$?
if [[ $EXIT_CODE -eq 0 ]]; then
  echo ""
  echo "=== Role hardening applied successfully ==="
  echo "Completed: $(date -u '+%Y-%m-%dT%H:%M:%SZ')"
  echo ""
  echo "NEXT STEPS:"
  echo "  1. Set passwords: ALTER ROLE fazle_app PASSWORD '...';"
  echo "  2. Update DATABASE_URL in .env to use new role"
  echo "  3. Restart services: docker compose restart"
else
  echo ""
  echo "=== ERROR: Role hardening failed (exit code $EXIT_CODE) ==="
  echo "No changes were committed (single-transaction mode)."
  exit $EXIT_CODE
fi
