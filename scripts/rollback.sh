#!/usr/bin/env bash
# ============================================================
# rollback.sh — Rollback to a previous deployment
# Usage: bash scripts/rollback.sh [commit-hash]
#   No args = rollback to the most recent backup
# ============================================================
set -euo pipefail

DEPLOY_DIR="/home/azim/ai-call-platform"
BACKUP_DIR="$DEPLOY_DIR/backups"

cd "$DEPLOY_DIR"

if [ -n "${1:-}" ]; then
    TARGET_COMMIT="$1"
    echo "Rolling back to specified commit: $TARGET_COMMIT"
else
    # Find the most recent rollback commit file
    LATEST_BACKUP=$(ls -1t "$BACKUP_DIR"/commit-rollback-*.txt 2>/dev/null | head -1)
    if [ -z "$LATEST_BACKUP" ]; then
        echo "ERROR: No rollback snapshots found in $BACKUP_DIR"
        exit 1
    fi
    TARGET_COMMIT=$(cat "$LATEST_BACKUP")
    echo "Rolling back to most recent snapshot: $TARGET_COMMIT"
    echo "  (from $LATEST_BACKUP)"
fi

CURRENT_COMMIT=$(git rev-parse HEAD)
echo ""
echo "Current commit:  $CURRENT_COMMIT"
echo "Rollback target: $TARGET_COMMIT"
echo ""

if [ "$CURRENT_COMMIT" = "$TARGET_COMMIT" ]; then
    echo "Already at target commit. Nothing to do."
    exit 0
fi

read -p "Proceed with rollback? (y/N) " -n 1 -r
echo ""
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Rollback cancelled."
    exit 0
fi

echo "[1/4] Checking out commit $TARGET_COMMIT..."
git checkout "$TARGET_COMMIT" 2>&1

echo "[2/4] Validating compose file..."
if ! docker compose config --quiet 2>&1; then
    echo "ERROR: Compose file invalid at target commit!"
    git checkout "$CURRENT_COMMIT"
    exit 1
fi

echo "[3/4] Rebuilding containers..."
docker compose pull --ignore-pull-failures 2>&1
docker compose build --parallel 2>&1
docker compose up -d --remove-orphans 2>&1

echo "[4/4] Verifying services..."
sleep 10
docker compose ps

echo ""
echo "============================================"
echo " Rollback complete!"
echo " Now at: $(git rev-parse HEAD)"
echo "============================================"
echo ""
echo "To verify services are healthy:"
echo "  bash scripts/health-check.sh"
