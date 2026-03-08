#!/usr/bin/env bash
# ============================================================
# rollback-vps.sh — Rollback VPS to previous state
# Usage: bash scripts/rollback-vps.sh [commit-hash]
# If no hash given, reads from deployment-package/ROLLBACK_TARGET.txt
# ============================================================
set -euo pipefail

VPS_IP="5.189.131.48"
VPS_USER="azim"
VPS_DIR="/home/azim/ai-call-platform"

# Get rollback target
if [ -n "${1:-}" ]; then
    ROLLBACK_HASH="$1"
elif [ -f deployment-package/ROLLBACK_TARGET.txt ]; then
    ROLLBACK_HASH=$(cat deployment-package/ROLLBACK_TARGET.txt)
else
    echo "Usage: bash scripts/rollback-vps.sh [commit-hash]"
    echo "  Or create deployment-package/ROLLBACK_TARGET.txt with the target hash"
    exit 1
fi

echo "============================================"
echo " ROLLBACK VPS to: $ROLLBACK_HASH"
echo " Target: ${VPS_USER}@${VPS_IP}:${VPS_DIR}"
echo "============================================"
echo ""
echo "⚠  This will revert all services to the previous deployment."
echo "   Press Enter to proceed or Ctrl+C to abort."
read -r

# ── SSH connectivity ────────────────────────────────────────
if ! ssh -o ConnectTimeout=10 "${VPS_USER}@${VPS_IP}" "echo OK" >/dev/null 2>&1; then
    echo "✗ Cannot reach VPS via SSH"
    exit 1
fi

# ── Run rollback ────────────────────────────────────────────
ssh "${VPS_USER}@${VPS_IP}" << REMOTE
  set -e
  cd ${VPS_DIR}

  echo "[1/4] Recording current state..."
  echo "Pre-rollback commit: \$(git rev-parse HEAD)"

  echo "[2/4] Reverting to ${ROLLBACK_HASH}..."
  git checkout ${ROLLBACK_HASH} -- .
  git checkout -- .env 2>/dev/null || true

  echo "[3/4] Rebuilding containers..."
  docker compose pull 2>/dev/null || true
  docker compose up -d --build --remove-orphans

  echo "[4/4] Waiting for stabilization (30s)..."
  sleep 30

  bash scripts/health-check.sh || true
REMOTE

echo ""
echo "============================================"
echo " Rollback complete → $ROLLBACK_HASH"
echo "============================================"
