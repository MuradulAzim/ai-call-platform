#!/usr/bin/env bash
# ============================================================
# debug.sh — Quick debugging overview of the platform
# Usage: bash scripts/debug.sh [section]
# Sections: containers|logs|ports|disk|cpu|memory|nginx|docker|all
# Default: all
# ============================================================
set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

SECTION="${1:-all}"

header() { echo -e "\n${CYAN}━━ $1 ━━${NC}"; }

# ── Container Status ────────────────────────────────────────
show_containers() {
    header "Docker Container Status"
    docker ps -a --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" | head -30 || true
    echo ""

    STOPPED=$(docker ps -a --filter "status=exited" --format "{{.Names}}" 2>/dev/null)
    if [ -n "$STOPPED" ]; then
        echo -e "${RED}Stopped containers:${NC}"
        echo "$STOPPED" | while read -r c; do
            echo "  $c"
        done
    fi

    RESTARTING=$(docker ps -a --filter "status=restarting" --format "{{.Names}}" 2>/dev/null)
    if [ -n "$RESTARTING" ]; then
        echo -e "${RED}Restarting containers (crash loop?):${NC}"
        echo "$RESTARTING" | while read -r c; do
            RESTARTS=$(docker inspect --format='{{.RestartCount}}' "$c" 2>/dev/null || echo "?")
            echo "  $c (restarts: $RESTARTS)"
        done
    fi
}

# ── Recent Logs from Failing Services ──────────────────────
show_logs() {
    header "Recent Logs (unhealthy/stopped/restarting)"
    PROBLEM=$(docker ps -a --filter "status=exited" --filter "status=restarting" --format "{{.Names}}" 2>/dev/null)
    # Also check unhealthy
    UNHEALTHY=$(docker ps --filter "health=unhealthy" --format "{{.Names}}" 2>/dev/null)
    ALL_PROBLEMS=$(echo -e "${PROBLEM}\n${UNHEALTHY}" | sort -u | grep -v '^$' || true)

    if [ -z "$ALL_PROBLEMS" ]; then
        echo -e "  ${GREEN}No failing services — all containers healthy${NC}"
    else
        while IFS= read -r c; do
            [ -z "$c" ] && continue
            echo -e "\n${YELLOW}── $c ──${NC}"
            docker logs --tail 25 "$c" 2>&1 | sed 's/^/  /'
        done <<< "$ALL_PROBLEMS"
    fi
}

# ── Open Ports ──────────────────────────────────────────────
show_ports() {
    header "Listening Ports"
    (ss -tlnp 2>/dev/null | head -40) || true
    echo ""
    echo "UDP ports:"
    (ss -ulnp 2>/dev/null | grep -E ':(3478|5349|[4-5][0-9]{4})' | head -10) || true
}

# ── Disk Usage ──────────────────────────────────────────────
show_disk() {
    header "Disk Usage"
    df -h / /home 2>/dev/null | awk 'NR==1 || /\/$|\/home$/'
    echo ""

    echo "Docker disk usage:"
    docker system df 2>/dev/null
    echo ""

    echo "Top 5 largest Docker volumes:"
    (docker system df -v 2>/dev/null | grep -A1 'VOLUME NAME' | head -12) || true
    echo ""

    echo "Large files (>100MB) in deploy dir:"
    find "$(pwd)" -maxdepth 3 -type f -size +100M -exec ls -lh {} \; 2>/dev/null | head -10 || echo "  None"
}

# ── CPU ─────────────────────────────────────────────────────
show_cpu() {
    header "CPU"
    echo "Cores: $(nproc)"
    echo "Load average: $(cat /proc/loadavg)"
    echo ""

    echo "Top 10 CPU-consuming processes:"
    (ps aux --sort=-%cpu | head -11) || true
    echo ""

    echo "Container CPU usage:"
    (docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}" 2>/dev/null | head -25) || true
}

# ── Memory ──────────────────────────────────────────────────
show_memory() {
    header "Memory"
    free -h
    echo ""

    echo "Container memory usage (sorted):"
    (docker stats --no-stream --format "{{.Name}}\t{{.MemUsage}}\t{{.MemPerc}}" 2>/dev/null | \
        sort -t$'\t' -k3 -rn | \
        awk -F'\t' 'BEGIN{printf "%-28s %-20s %s\n", "CONTAINER", "USAGE", "PCT"} {printf "%-28s %-20s %s\n", $1, $2, $3}' | head -25) || true
    echo ""

    echo "OOM kills (if any):"
    (dmesg 2>/dev/null | grep -i "out of memory\|oom" | tail -5 || true) || echo "  None detected"
}

# ── Nginx ───────────────────────────────────────────────────
show_nginx() {
    header "Nginx"
    echo "Service status:"
    (systemctl status nginx --no-pager -l 2>/dev/null | head -15) || echo "  systemctl not available"
    echo ""

    echo "Config test:"
    sudo nginx -t 2>&1 || echo "  (needs sudo)"
    echo ""

    echo "Enabled sites:"
    ls -la /etc/nginx/sites-enabled/ 2>/dev/null || echo "  /etc/nginx/sites-enabled not found"
    echo ""

    echo "Recent error log (last 15 lines):"
    tail -15 /var/log/nginx/error.log 2>/dev/null || echo "  Cannot read error log (need sudo?)"
}

# ── Docker Overview ─────────────────────────────────────────
show_docker() {
    header "Docker Overview"
    echo "Docker version: $(docker --version)"
    echo "Compose version: $(docker compose version 2>/dev/null || echo 'not found')"
    echo ""

    echo "Networks:"
    docker network ls --format "table {{.Name}}\t{{.Driver}}\t{{.Scope}}" 2>/dev/null
    echo ""

    echo "Images (platform):"
    (docker images --format "table {{.Repository}}\t{{.Tag}}\t{{.Size}}\t{{.CreatedSince}}" 2>/dev/null | \
        grep -E 'dograh|fazle|livekit|coturn|qdrant|ollama|postgres|redis|minio|prom|grafana|loki|cadvisor|cloudflare' | head -25) || true
}

# ── Run Sections ────────────────────────────────────────────
case "$SECTION" in
    containers) show_containers ;;
    logs)       show_logs ;;
    ports)      show_ports ;;
    disk)       show_disk ;;
    cpu)        show_cpu ;;
    memory)     show_memory ;;
    nginx)      show_nginx ;;
    docker)     show_docker ;;
    all)
        show_containers
        show_logs
        show_ports
        show_disk
        show_cpu
        show_memory
        show_nginx
        show_docker
        ;;
    *)
        echo "Usage: $0 [containers|logs|ports|disk|cpu|memory|nginx|docker|all]"
        exit 1
        ;;
esac
