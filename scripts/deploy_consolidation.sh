#!/usr/bin/env bash
# ============================================================
# deploy_consolidation.sh
# Full DB consolidation deploy — backup → migrate → deploy
# ============================================================
set -euo pipefail

SERVER="azim@5.189.131.48"
REMOTE_DIR="/home/azim/ai-call-platform"
COMPOSE_FILE="fazle-ai/docker-compose.yaml"

echo "============================================"
echo "  DB Consolidation Deploy — $(date)"
echo "============================================"

# ── STEP 1: Remote backup ──────────────────────────────────
echo ""
echo "=== STEP 1: Database Backup ==="
ssh "$SERVER" "cd $REMOTE_DIR && \
  BACKUP_FILE=\"backup_consolidation_\$(date +%F_%H-%M).sql\" && \
  docker exec fazle-postgres pg_dump -U postgres -d fazle > \"/home/azim/\$BACKUP_FILE\" && \
  ls -lh /home/azim/\$BACKUP_FILE && \
  echo \"Backup saved: /home/azim/\$BACKUP_FILE\""
echo "✅ Backup complete"

# ── STEP 2: Git pull ──────────────────────────────────────
echo ""
echo "=== STEP 2: Git Pull ==="
ssh "$SERVER" "cd $REMOTE_DIR && git stash 2>/dev/null; git pull origin main"
echo "✅ Code updated"

# ── STEP 3: Rebuild affected services ─────────────────────
echo ""
echo "=== STEP 3: Docker Build ==="
ssh "$SERVER" "cd $REMOTE_DIR && \
  docker compose -f $COMPOSE_FILE --env-file .env build --no-cache fazle-wbom fazle-social-engine fazle-api fazle-ui"
echo "✅ Build complete"

# ── STEP 4: Restart services ──────────────────────────────
echo ""
echo "=== STEP 4: Rolling Restart ==="
ssh "$SERVER" "cd $REMOTE_DIR && \
  docker compose -f $COMPOSE_FILE --env-file .env up -d fazle-wbom --remove-orphans && \
  sleep 10 && \
  docker compose -f $COMPOSE_FILE --env-file .env up -d fazle-social-engine fazle-api fazle-ui --remove-orphans"
echo "✅ Services restarted"

# ── STEP 5: Wait + Health check ───────────────────────────
echo ""
echo "=== STEP 5: Health Check ==="
sleep 15
ssh "$SERVER" "cd $REMOTE_DIR && \
  echo '--- Container Status ---' && \
  docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}' | grep -E 'fazle|postgres|redis|nginx' && \
  echo '' && \
  echo '--- WBOM Health ---' && \
  KEY=\$(grep INTERNAL_KEY .env | head -1 | cut -d= -f2) && \
  curl -sf -H \"X-INTERNAL-KEY: \$KEY\" http://localhost:9900/health | python3 -m json.tool 2>/dev/null || echo 'WBOM health check failed' && \
  echo '' && \
  echo '--- API Health ---' && \
  curl -sf http://localhost:8100/health | python3 -m json.tool 2>/dev/null || echo 'API health check failed'"

# ── STEP 6: Validate migration ────────────────────────────
echo ""
echo "=== STEP 6: Migration Validation ==="
ssh "$SERVER" "cd $REMOTE_DIR && \
  docker exec fazle-postgres psql -U postgres -d fazle -c \"
    SELECT 'wbom_employees' AS table_name, COUNT(*) AS rows FROM wbom_employees
    UNION ALL
    SELECT 'wbom_contacts', COUNT(*) FROM wbom_contacts
    UNION ALL
    SELECT 'wbom_cash_transactions', COUNT(*) FROM wbom_cash_transactions
    UNION ALL
    SELECT 'wbom_whatsapp_messages', COUNT(*) FROM wbom_whatsapp_messages
    UNION ALL
    SELECT 'wbom_escort_programs', COUNT(*) FROM wbom_escort_programs
    UNION ALL
    SELECT 'wbom_attendance', COUNT(*) FROM wbom_attendance
    ORDER BY table_name;
  \" && \
  echo '' && \
  echo '--- Legacy tables (should be renamed) ---' && \
  docker exec fazle-postgres psql -U postgres -d fazle -c \"
    SELECT tablename FROM pg_tables
    WHERE schemaname = 'public'
      AND (tablename LIKE '_legacy_%' OR tablename LIKE 'ops_%' OR tablename = 'fazle_contacts' OR tablename = 'fazle_social_messages')
    ORDER BY tablename;
  \""

echo ""
echo "============================================"
echo "  ✅ CONSOLIDATION DEPLOY COMPLETE"
echo "============================================"
