#!/usr/bin/env bash
# ============================================================
# diagnose.sh — Master diagnostics runner
# Runs all health/test scripts and produces a summary report
# Usage: bash scripts/diagnose.sh [--save]
# --save: Save report to diagnose-report-<timestamp>.txt
# ============================================================
set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SAVE_REPORT=false
[ "${1:-}" = "--save" ] && SAVE_REPORT=true

REPORT_FILE=""
if $SAVE_REPORT; then
    REPORT_FILE="${SCRIPT_DIR}/../diagnose-report-$(date +%Y%m%d-%H%M%S).txt"
fi

# Run command, capture exit code, optionally tee to file
run_script() {
    local name=$1 script=$2
    echo ""
    echo -e "${BOLD}╔════════════════════════════════════════════╗${NC}"
    echo -e "${BOLD}║  $name${NC}"
    echo -e "${BOLD}╚════════════════════════════════════════════╝${NC}"
    echo ""

    local rc=0
    if [ -f "$script" ]; then
        bash "$script" || rc=$?
    else
        echo -e "${RED}Script not found: $script${NC}"
        rc=99
    fi
    return $rc
}

echo -e "${BOLD}╔════════════════════════════════════════════════════╗${NC}"
echo -e "${BOLD}║       FULL PLATFORM DIAGNOSTICS                   ║${NC}"
echo -e "${BOLD}║       $(date)            ║${NC}"
echo -e "${BOLD}╚════════════════════════════════════════════════════╝${NC}"

RESULTS=()
SCRIPTS=(
    "Platform Health Check:${SCRIPT_DIR}/health-check.sh"
    "Fazle AI Tests:${SCRIPT_DIR}/test-fazle.sh"
    "Monitoring Stack:${SCRIPT_DIR}/check-monitoring.sh"
    "Debug Overview:${SCRIPT_DIR}/debug.sh"
)

for entry in "${SCRIPTS[@]}"; do
    NAME="${entry%%:*}"
    SCRIPT="${entry#*:}"
    RC=0
    run_script "$NAME" "$SCRIPT" || RC=$?
    if [ $RC -eq 0 ]; then
        RESULTS+=("${GREEN}✓${NC} $NAME — ALL PASSED")
    else
        RESULTS+=("${RED}✗${NC} $NAME — $RC issue(s)")
    fi
done

# ── Final Summary ──────────────────────────────────────────
echo ""
echo ""
echo -e "${BOLD}╔════════════════════════════════════════════════════╗${NC}"
echo -e "${BOLD}║              DIAGNOSTICS SUMMARY                  ║${NC}"
echo -e "${BOLD}╚════════════════════════════════════════════════════╝${NC}"
echo ""
for r in "${RESULTS[@]}"; do
    echo -e "  $r"
done
echo ""

# Quick stats
TOTAL_CONTAINERS=$(docker ps -q 2>/dev/null | wc -l)
HEALTHY_CONTAINERS=$(docker ps --filter "health=healthy" -q 2>/dev/null | wc -l)
UNHEALTHY=$(docker ps --filter "health=unhealthy" -q 2>/dev/null | wc -l)
STOPPED=$(docker ps -a --filter "status=exited" -q 2>/dev/null | wc -l)
DISK=$(df / | awk 'NR==2 {print $5}')
MEM=$(free | awk 'NR==2 {printf "%.0f%%", $3/$2*100}')
LOAD=$(cat /proc/loadavg 2>/dev/null | awk '{print $1}' || echo "?")

echo -e "${CYAN}Quick Stats:${NC}"
echo "  Containers running: $TOTAL_CONTAINERS (healthy: $HEALTHY_CONTAINERS, unhealthy: $UNHEALTHY, stopped: $STOPPED)"
echo "  Disk: $DISK  |  Memory: $MEM  |  Load: $LOAD"
echo ""
echo "  Platform:   https://iamazim.com"
echo "  API:        https://api.iamazim.com"
echo "  Fazle:      https://fazle.iamazim.com"
echo "  Grafana:    https://iamazim.com/grafana/"
echo ""

if $SAVE_REPORT; then
    echo "Report would be saved to: $REPORT_FILE"
    echo "(Re-run with: bash scripts/diagnose.sh --save 2>&1 | tee $REPORT_FILE)"
fi

echo -e "${BOLD}Diagnostics complete.${NC}"
