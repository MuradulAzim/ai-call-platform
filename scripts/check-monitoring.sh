#!/usr/bin/env bash
# ============================================================
# check-monitoring.sh — Verify monitoring & observability stack
# Usage: bash scripts/check-monitoring.sh
# ============================================================
set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

PASS=0
FAIL=0
WARN=0

pass() { PASS=$((PASS+1)); printf "  ${GREEN}✓${NC} %s\n" "$1"; }
fail() { FAIL=$((FAIL+1)); printf "  ${RED}✗${NC} %s\n" "$1"; }
warn() { WARN=$((WARN+1)); printf "  ${YELLOW}⚠${NC} %s\n" "$1"; }

echo "============================================"
echo " Monitoring Stack Health"
echo " $(date)"
echo "============================================"
echo ""

# ── Container Status ───────────────────────────────────────
echo -e "${CYAN}── Monitoring Containers ──${NC}"
for c in prometheus grafana loki promtail node-exporter cadvisor; do
    STATUS=$(docker inspect --format='{{.State.Status}}' "$c" 2>/dev/null | tr -d '[:space:]' || echo "not-found")
    HEALTH=$(docker inspect --format='{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' "$c" 2>/dev/null | tr -d '[:space:]' || echo "none")
    if [ "$STATUS" = "running" ] && { [ "$HEALTH" = "healthy" ] || [ "$HEALTH" = "none" ]; }; then
        pass "$(printf '%-18s running (%s)' "$c" "$HEALTH")"
    elif [ "$STATUS" = "not-found" ]; then
        warn "$(printf '%-18s not found' "$c")"
    else
        fail "$(printf '%-18s %s (%s)' "$c" "$STATUS" "$HEALTH")"
    fi
done
echo ""

# ── Prometheus ──────────────────────────────────────────────
echo -e "${CYAN}── Prometheus (internal network — via docker exec) ──${NC}"

# Health
PROM_HEALTHY=$(docker exec prometheus wget -q -O- http://localhost:9090/-/healthy 2>/dev/null || echo "FAIL")
if echo "$PROM_HEALTHY" | grep -qi "ok\|healthy\|Prometheus"; then
    pass "Prometheus healthy"
else
    fail "Prometheus not healthy"
fi

# Ready
PROM_READY=$(docker exec prometheus wget -q -O- http://localhost:9090/-/ready 2>/dev/null || echo "FAIL")
if echo "$PROM_READY" | grep -qi "ok\|ready\|Prometheus"; then
    pass "Prometheus ready"
else
    fail "Prometheus not ready"
fi

# Target scrape status
TARGETS=$(docker exec prometheus wget -q -O- http://localhost:9090/api/v1/targets 2>/dev/null || echo "")
if [ -n "$TARGETS" ]; then
    UP_COUNT=$(echo "$TARGETS" | grep -o '"health":"up"' | wc -l || true)
    DOWN_COUNT=$(echo "$TARGETS" | grep -o '"health":"down"' | wc -l || true)
    UNKNOWN_COUNT=$(echo "$TARGETS" | grep -o '"health":"unknown"' | wc -l || true)

    if [ "$DOWN_COUNT" -eq 0 ]; then
        pass "All $UP_COUNT scrape targets UP"
    else
        warn "$UP_COUNT up, $DOWN_COUNT down, $UNKNOWN_COUNT unknown"
    fi

    # Show target details
    echo "  Scrape targets:"
    JOBS=$(echo "$TARGETS" | grep -oP '"job"\s*:\s*"\K[^"]+' | sort -u || true)
    for job in $JOBS; do
        JOB_HEALTH=$(echo "$TARGETS" | grep -oP "\"job\":\"${job}\".*?\"health\":\"\\K[a-z]+" | head -1 || echo "unknown")
        if [ "$JOB_HEALTH" = "up" ]; then
            printf "    ${GREEN}✓${NC} %s\n" "$job"
        else
            printf "    ${RED}✗${NC} %s (%s)\n" "$job" "$JOB_HEALTH"
        fi
    done
else
    fail "Cannot query Prometheus targets API"
fi

# TSDB stats
TSDB=$(docker exec prometheus wget -q -O- http://localhost:9090/api/v1/status/tsdb 2>/dev/null || echo "")
if [ -n "$TSDB" ]; then
    SERIES=$(echo "$TSDB" | grep -oP '"numSeries"\s*:\s*\K[0-9]+' || echo "?")
    echo "  Time series count: $SERIES"
fi
echo ""

# ── Grafana ─────────────────────────────────────────────────
echo -e "${CYAN}── Grafana ──${NC}"

GRAFANA_CODE=$(curl -s -o /dev/null -w "%{http_code}" --connect-timeout 5 http://127.0.0.1:3030/api/health 2>/dev/null || echo "000")
if [ "$GRAFANA_CODE" -ge 200 ] && [ "$GRAFANA_CODE" -lt 400 ]; then
    pass "Grafana healthy (HTTP $GRAFANA_CODE)"
else
    fail "Grafana not healthy (HTTP $GRAFANA_CODE)"
fi

GRAFANA_HEALTH=$(curl -s http://127.0.0.1:3030/api/health 2>/dev/null || echo "")
if [ -n "$GRAFANA_HEALTH" ]; then
    DB_STATUS=$(echo "$GRAFANA_HEALTH" | grep -oP '"database"\s*:\s*"\K[^"]+' || echo "?")
    VERSION=$(echo "$GRAFANA_HEALTH" | grep -oP '"version"\s*:\s*"\K[^"]+' || echo "?")
    pass "Grafana v$VERSION (DB: $DB_STATUS)"
fi

# Datasources
DATASOURCES=$(curl -s -u admin:admin http://127.0.0.1:3030/api/datasources 2>/dev/null || echo "")
if echo "$DATASOURCES" | grep -q '"name"'; then
    echo "  Configured datasources:"
    DS_NAMES=$(echo "$DATASOURCES" | grep -oP '"name"\s*:\s*"\K[^"]+' || true)
    for ds in $DS_NAMES; do
        printf "    → %s\n" "$ds"
    done
else
    warn "No datasources configured (or auth required)"
fi
echo ""

# ── Loki ────────────────────────────────────────────────────
echo -e "${CYAN}── Loki ──${NC}"

# Loki is internal-only; check docker healthcheck status
LOKI_STATUS=$(docker inspect --format='{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' loki 2>/dev/null | tr -d '[:space:]' || echo "unknown")
if [ "$LOKI_STATUS" = "healthy" ]; then
    pass "Loki healthy (docker healthcheck)"
else
    warn "Loki status: $LOKI_STATUS"
fi

# Query labels via promtail container (which is on monitoring-network and has wget)
LOKI_LABELS=$(docker exec promtail wget -q -O- "http://loki:3100/loki/api/v1/labels" 2>/dev/null || echo "")
if echo "$LOKI_LABELS" | grep -q '"values"'; then
    LABEL_COUNT=$(echo "$LOKI_LABELS" | grep -oP '"[^"]+' | grep -v 'status\|values\|data' | wc -l || echo "0")
    pass "Loki has labels ($LABEL_COUNT indexed)"
else
    warn "Cannot query Loki labels"
fi
echo ""

# ── Promtail ────────────────────────────────────────────────
echo -e "${CYAN}── Promtail ──${NC}"

PROMTAIL_STATUS=$(docker inspect --format='{{.State.Status}}' promtail 2>/dev/null || echo "not-found")
if [ "$PROMTAIL_STATUS" = "running" ]; then
    pass "Promtail running"

    # Check targets
    PROMTAIL_TARGETS=$(docker exec promtail wget -q -O- http://localhost:9080/targets 2>/dev/null || echo "")
    if [ -n "$PROMTAIL_TARGETS" ]; then
        ACTIVE=$(echo "$PROMTAIL_TARGETS" | grep -c "Active" || true)
        pass "Promtail has active scrape targets"
    else
        warn "Cannot query Promtail targets"
    fi
else
    fail "Promtail not running"
fi
echo ""

# ── Node Exporter ───────────────────────────────────────────
echo -e "${CYAN}── Node Exporter ──${NC}"
NODE_STATUS=$(docker inspect --format='{{.State.Status}}' node-exporter 2>/dev/null || echo "not-found")
if [ "$NODE_STATUS" = "running" ]; then
    pass "Node Exporter running"
else
    fail "Node Exporter not running"
fi
echo ""

# ── cAdvisor ────────────────────────────────────────────────
echo -e "${CYAN}── cAdvisor ──${NC}"
CADVISOR_STATUS=$(docker inspect --format='{{.State.Status}}' cadvisor 2>/dev/null || echo "not-found")
if [ "$CADVISOR_STATUS" = "running" ]; then
    pass "cAdvisor running"
else
    fail "cAdvisor not running"
fi
echo ""

# ── Monitoring URLs ─────────────────────────────────────────
echo -e "${CYAN}── Monitoring URLs ──${NC}"
echo "  Prometheus:  http://127.0.0.1:9090"
echo "  Grafana:     http://127.0.0.1:3030  (or https://iamazim.com/grafana/)"
echo "  Loki:        http://127.0.0.1:3100  (internal via Grafana)"
echo ""

# ── Summary ─────────────────────────────────────────────────
echo "============================================"
echo -e " ${GREEN}✓ $PASS passed${NC}  ${RED}✗ $FAIL failed${NC}  ${YELLOW}⚠ $WARN warnings${NC}"
if [ $FAIL -eq 0 ]; then
    echo -e " ${GREEN}Monitoring stack healthy${NC}"
else
    echo -e " ${RED}$FAIL check(s) failed${NC}"
fi
echo "============================================"

exit $FAIL
