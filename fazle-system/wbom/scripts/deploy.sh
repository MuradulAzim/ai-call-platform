#!/usr/bin/env bash
# ============================================================
# WBOM — Zero-downtime deploy script
# Usage: ./scripts/deploy.sh [--skip-tests] [--skip-backup]
# ============================================================
set -euo pipefail

WBOM_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE_FILE="${WBOM_DIR}/../../fazle-ai/docker-compose.yaml"
ENV_FILE="${WBOM_DIR}/../../.env"
SERVICE_NAME="fazle-wbom"
HEALTH_URL="http://localhost:9900/health"
SKIP_TESTS=false
SKIP_BACKUP=false

for arg in "$@"; do
  case $arg in
    --skip-tests)  SKIP_TESTS=true  ;;
    --skip-backup) SKIP_BACKUP=true ;;
  esac
done

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"; }
die() { log "ERROR: $*" >&2; exit 1; }

# ── 1. Safety check ─────────────────────────────────────────
log "=== WBOM Deploy — $(date) ==="
log "Service: $SERVICE_NAME"
log "Compose:  $COMPOSE_FILE"

[ -f "$COMPOSE_FILE" ] || die "docker-compose.yaml not found at $COMPOSE_FILE"
[ -f "$ENV_FILE" ]     || die ".env not found at $ENV_FILE"

# ── 2. Backup ────────────────────────────────────────────────
if [ "$SKIP_BACKUP" = false ]; then
  log "--- Backup ---"
  bash "${WBOM_DIR}/scripts/backup.sh" && log "Backup complete" || {
    log "WARNING: backup failed — continue? [y/N]"
    read -r ans
    [[ "${ans,,}" == "y" ]] || die "Deploy aborted due to backup failure"
  }
fi

# ── 3. Git pull ──────────────────────────────────────────────
log "--- Git pull ---"
cd "${WBOM_DIR}/../.."
git pull origin "$(git rev-parse --abbrev-ref HEAD)"
COMMIT=$(git rev-parse --short HEAD)
log "At commit $COMMIT"

# ── 4. Run tests ─────────────────────────────────────────────
if [ "$SKIP_TESTS" = false ]; then
  log "--- Running tests ---"
  cd "${WBOM_DIR}"
  python -m pytest tests/ -q --tb=short -x || die "Tests failed — deploy aborted"
  log "All tests passed"
fi

# ── 5. Rebuild container ──────────────────────────────────────
log "--- Building $SERVICE_NAME ---"
docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" \
  build --no-cache "$SERVICE_NAME"

# ── 6. Restart with zero-downtime swap ───────────────────────
log "--- Restarting $SERVICE_NAME ---"
docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" \
  up -d --no-deps --remove-orphans "$SERVICE_NAME"

# ── 7. Health check loop ──────────────────────────────────────
log "--- Waiting for health check ($HEALTH_URL) ---"
RETRIES=12
for i in $(seq 1 $RETRIES); do
  HTTP=$(curl -sf -o /dev/null -w "%{http_code}" "$HEALTH_URL" 2>/dev/null || echo "000")
  if [ "$HTTP" = "200" ]; then
    log "Health check passed (attempt $i)"
    break
  fi
  if [ "$i" -eq "$RETRIES" ]; then
    log "ERROR: Health check failed after $RETRIES attempts. Rolling back…"
    docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" \
      restart "$SERVICE_NAME" || true
    die "Deploy FAILED — $SERVICE_NAME did not become healthy"
  fi
  log "  Attempt $i/$RETRIES — HTTP $HTTP — retrying in 10s…"
  sleep 10
done

# ── 8. Summary ───────────────────────────────────────────────
VERSION=$(curl -sf "$HEALTH_URL" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('version','?'))" 2>/dev/null || echo "?")
log "=== Deploy complete ==="
log "  Commit:  $COMMIT"
log "  Version: $VERSION"
log "  Service: $SERVICE_NAME — HEALTHY"
