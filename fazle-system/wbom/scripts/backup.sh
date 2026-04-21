#!/usr/bin/env bash
# ============================================================
# WBOM — PostgreSQL Backup Script  (Sprint-6 S6-04)
# Usage:
#   ./backup.sh                    # uses env vars or defaults
#   DB_HOST=localhost ./backup.sh  # override host
#
# Required env vars (or set defaults below):
#   WBOM_DATABASE_URL  — full DSN (takes precedence)
#   DB_HOST / DB_PORT / DB_NAME / DB_USER / PGPASSWORD
#
# Output: backups/wbom_YYYYMMDD_HHMMSS.sql.gz
# ============================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKUP_DIR="${BACKUP_DIR:-${SCRIPT_DIR}/../backups}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="${BACKUP_DIR}/wbom_${TIMESTAMP}.sql.gz"

# ── Parse DSN if provided ─────────────────────────────────────
if [[ -n "${WBOM_DATABASE_URL:-}" ]]; then
    # postgresql://user:pass@host:port/dbname
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

mkdir -p "${BACKUP_DIR}"

echo "=== WBOM Backup ==="
echo "  Time:     ${TIMESTAMP}"
echo "  Database: ${DB_NAME} @ ${DB_HOST}:${DB_PORT}"
echo "  Output:   ${BACKUP_FILE}"
echo ""

pg_dump \
    --host="${DB_HOST}" \
    --port="${DB_PORT}" \
    --username="${DB_USER}" \
    --no-password \
    --format=plain \
    --no-owner \
    --no-privileges \
    --schema-only=false \
    --table="wbom_*" \
    "${DB_NAME}" \
    | gzip -9 > "${BACKUP_FILE}"

SIZE=$(du -sh "${BACKUP_FILE}" | cut -f1)
echo "Backup complete: ${BACKUP_FILE} (${SIZE})"
echo ""

# ── Prune old backups (keep last 30) ─────────────────────────
KEEP="${KEEP_BACKUPS:-30}"
BACKUP_COUNT=$(ls -1 "${BACKUP_DIR}"/wbom_*.sql.gz 2>/dev/null | wc -l)
if [[ "${BACKUP_COUNT}" -gt "${KEEP}" ]]; then
    TO_DELETE=$(( BACKUP_COUNT - KEEP ))
    echo "Pruning ${TO_DELETE} old backup(s) (keeping ${KEEP})..."
    ls -1t "${BACKUP_DIR}"/wbom_*.sql.gz | tail -n "${TO_DELETE}" | xargs rm -f
    echo "Pruning done."
fi
