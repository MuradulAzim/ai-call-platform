#!/usr/bin/env bash
# ============================================================
# Phase 4 — DB Pre-Check Script
# Validates container, connectivity, and target DB exist
# ============================================================
set -euo pipefail

# ── Defaults ────────────────────────────────────────────────
CONTAINER="ai-postgres"
DB=""
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

echo "=== Phase 4 DB Pre-Check ==="
echo "Container : $CONTAINER"
echo "Database  : $DB"
echo "Timestamp : $(date -u '+%Y-%m-%dT%H:%M:%SZ')"
echo ""

FAIL=0

# ── Check: docker available ─────────────────────────────────
echo -n "[1/5] Docker available ... "
if command -v docker &>/dev/null; then
  echo "OK"
else
  echo "FAIL — docker not found in PATH"
  exit 1
fi

# ── Check: container exists and is running ──────────────────
echo -n "[2/5] Container '$CONTAINER' running ... "
STATE=$(docker inspect -f '{{.State.Running}}' "$CONTAINER" 2>/dev/null || true)
if [[ "$STATE" == "true" ]]; then
  echo "OK"
else
  echo "FAIL — container not running or does not exist"
  exit 1
fi

# ── Check: pg_isready ────────────────────────────────────────
echo -n "[3/5] pg_isready ... "
if docker exec "$CONTAINER" pg_isready -U "$PG_USER" -q 2>/dev/null; then
  echo "OK"
else
  echo "FAIL — PostgreSQL is not accepting connections"
  exit 1
fi

# ── Check: target database exists ────────────────────────────
echo -n "[4/5] Database '$DB' exists ... "
DB_EXISTS=$(docker exec -i "$CONTAINER" psql -U "$PG_USER" -tAc \
  "SELECT 1 FROM pg_database WHERE datname='${DB}';" 2>/dev/null || true)
if [[ "$DB_EXISTS" == "1" ]]; then
  echo "OK"
else
  echo "FAIL — database '$DB' not found"
  exit 1
fi

# ── Check: disk space (warn only) ───────────────────────────
echo -n "[5/5] Disk space ... "
# Try to get % used on root inside the container
DISK_PCT=$(docker exec "$CONTAINER" sh -c "df / 2>/dev/null | awk 'NR==2{print \$5}' | tr -d '%'" 2>/dev/null || echo "unknown")
if [[ "$DISK_PCT" == "unknown" ]]; then
  echo "WARN — could not determine disk usage"
elif [[ "$DISK_PCT" -ge 90 ]]; then
  echo "WARN — ${DISK_PCT}% used (< 10% free)"
else
  echo "OK (${DISK_PCT}% used)"
fi

echo ""
echo "=== Pre-check passed ==="
exit 0
