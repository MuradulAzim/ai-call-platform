#!/usr/bin/env bash
# ============================================================
# WBOM — PostgreSQL Restore Script  (Sprint-6 S6-04)
# Usage:
#   ./restore.sh backups/wbom_20260421_120000.sql.gz
#
# IMPORTANT:
#   This script restores WBOM tables only (wbom_*).
#   It does NOT drop or recreate other tables.
#   A confirmation prompt protects against accidental restores.
# ============================================================
set -euo pipefail

BACKUP_FILE="${1:-}"

if [[ -z "${BACKUP_FILE}" ]]; then
    echo "Usage: ./restore.sh <backup_file.sql.gz>"
    echo ""
    echo "Available backups:"
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    ls -lh "${SCRIPT_DIR}/../backups"/wbom_*.sql.gz 2>/dev/null || echo "  (none found)"
    exit 1
fi

if [[ ! -f "${BACKUP_FILE}" ]]; then
    echo "ERROR: File not found: ${BACKUP_FILE}"
    exit 2
fi

# ── Parse DSN ─────────────────────────────────────────────────
if [[ -n "${WBOM_DATABASE_URL:-}" ]]; then
    DB_USER=$(echo "$WBOM_DATABASE_URL" | sed -E 's|postgresql://([^:]+):.*|\1|')
    PGPASSWORD=$(echo "$WBOM_DATABASE_URL" | sed -E 's|postgresql://[^:]+:([^@]+)@.*|\1|')
    DB_HOST=$(echo "$WBOM_DATABASE_URL" | sed -E 's|postgresql://[^@]+@([^:/]+).*|\1|')
    DB_PORT=$(echo "$WBOM_DATABASE_URL" | sed -E 's|.*:([0-9]+)/.*|\1|')
    DB_NAME=$(echo "$WBOM_DATABASE_URL" | sed -E 's|.*/([^?]+).*|\1|')
    export PGPASSWORD
fi

DB_HOST="${DB_HOST:-localhost}"
DB_PORT="${DB_PORT:-5432}"
DB_NAME="${DB_NAME:-postgres}"
DB_USER="${DB_USER:-postgres}"

FILESIZE=$(du -sh "${BACKUP_FILE}" | cut -f1)

echo "=== WBOM Restore ==="
echo "  File:     ${BACKUP_FILE} (${FILESIZE})"
echo "  Database: ${DB_NAME} @ ${DB_HOST}:${DB_PORT}"
echo ""
echo "WARNING: This will overwrite existing WBOM data."
read -r -p "Type 'yes' to continue: " CONFIRM

if [[ "${CONFIRM}" != "yes" ]]; then
    echo "Restore cancelled."
    exit 0
fi

echo ""
echo "Restoring..."
gunzip -c "${BACKUP_FILE}" | psql \
    --host="${DB_HOST}" \
    --port="${DB_PORT}" \
    --username="${DB_USER}" \
    --no-password \
    "${DB_NAME}"

echo ""
echo "Restore complete."
