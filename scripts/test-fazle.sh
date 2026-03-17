#!/usr/bin/env bash
# ============================================================
# test-fazle.sh — Test all Fazle AI service endpoints
# Usage: bash scripts/test-fazle.sh
# ============================================================
set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

PASS=0
FAIL=0
BASE="http://127.0.0.1"

pass() { PASS=$((PASS+1)); printf "  ${GREEN}✓${NC} %s\n" "$1"; }
fail() { FAIL=$((FAIL+1)); printf "  ${RED}✗${NC} %s\n" "$1"; }

echo "============================================"
echo " Fazle AI Service Tests"
echo " $(date)"
echo "============================================"
echo ""

# ── Helper: HTTP request with response ─────────────────────
http_check() {
    local name=$1 method=$2 url=$3 body="${4:-}"
    local code response
    if [ "$method" = "GET" ]; then
        response=$(curl -s -w "\n%{http_code}" --connect-timeout 5 --max-time 10 "$url" 2>/dev/null || echo -e "\n000")
    else
        response=$(curl -s -w "\n%{http_code}" --connect-timeout 5 --max-time 15 \
            -X POST -H "Content-Type: application/json" -d "$body" "$url" 2>/dev/null || echo -e "\n000")
    fi
    code=$(echo "$response" | tail -1)
    body_text=$(echo "$response" | head -n -1)

    if [ "$code" -ge 200 ] && [ "$code" -lt 400 ]; then
        pass "$name (HTTP $code)"
        if [ -n "$body_text" ]; then
            echo "    → $(echo "$body_text" | head -c 200)"
        fi
        return 0
    else
        fail "$name (HTTP $code)"
        if [ -n "$body_text" ] && [ "$body_text" != "000" ]; then
            echo "    → $(echo "$body_text" | head -c 200)"
        fi
        return 1
    fi
}

# ── 1. Fazle API Gateway ───────────────────────────────────
echo -e "${CYAN}── Fazle API Gateway (:8100) ──${NC}"
http_check "Health check" GET "${BASE}:8100/health"
http_check "Status endpoint" GET "${BASE}:8100/fazle/status" || true
echo ""

# ── 2. Fazle Brain ─────────────────────────────────────────
echo -e "${CYAN}── Fazle Brain (:8200) ──${NC}"
# Brain is internal only (ai-network), test via fazle-api or docker exec
BRAIN_HEALTH=$(docker exec fazle-brain python -c "import urllib.request; print(urllib.request.urlopen('http://localhost:8200/health').read().decode())" 2>/dev/null || echo "FAIL")
if echo "$BRAIN_HEALTH" | grep -qi "ok\|healthy\|status"; then
    pass "Brain health: $BRAIN_HEALTH"
else
    fail "Brain health: $BRAIN_HEALTH"
fi
echo ""

# ── 3. Fazle Memory ────────────────────────────────────────
echo -e "${CYAN}── Fazle Memory (:8300) ──${NC}"
MEM_HEALTH=$(docker exec fazle-memory python -c "import urllib.request; print(urllib.request.urlopen('http://localhost:8300/health').read().decode())" 2>/dev/null || echo "FAIL")
if echo "$MEM_HEALTH" | grep -qi "ok\|healthy\|status"; then
    pass "Memory health: $MEM_HEALTH"
else
    fail "Memory health: $MEM_HEALTH"
fi
echo ""

# ── 4. Fazle Task Engine ───────────────────────────────────
echo -e "${CYAN}── Fazle Task Engine (:8400) ──${NC}"
TASK_HEALTH=$(docker exec fazle-task-engine python -c "import urllib.request; print(urllib.request.urlopen('http://localhost:8400/health').read().decode())" 2>/dev/null || echo "FAIL")
if echo "$TASK_HEALTH" | grep -qi "ok\|healthy\|status"; then
    pass "Task Engine health: $TASK_HEALTH"
else
    fail "Task Engine health: $TASK_HEALTH"
fi
echo ""

# ── 5. Fazle Web Intelligence ──────────────────────────────
echo -e "${CYAN}── Fazle Web Intelligence (:8500) ──${NC}"
TOOLS_HEALTH=$(docker exec fazle-web-intelligence python -c "import urllib.request; print(urllib.request.urlopen('http://localhost:8500/health').read().decode())" 2>/dev/null || echo "FAIL")
if echo "$TOOLS_HEALTH" | grep -qi "ok\|healthy\|status"; then
    pass "Web Intelligence health: $TOOLS_HEALTH"
else
    fail "Web Intelligence health: $TOOLS_HEALTH"
fi
echo ""

# ── 6. Fazle Trainer ───────────────────────────────────────
echo -e "${CYAN}── Fazle Trainer (:8600) ──${NC}"
TRAINER_HEALTH=$(docker exec fazle-trainer python -c "import urllib.request; print(urllib.request.urlopen('http://localhost:8600/health').read().decode())" 2>/dev/null || echo "FAIL")
if echo "$TRAINER_HEALTH" | grep -qi "ok\|healthy\|status"; then
    pass "Trainer health: $TRAINER_HEALTH"
else
    fail "Trainer health: $TRAINER_HEALTH"
fi
echo ""

# ── 7. Fazle UI ─────────────────────────────────────────────
echo -e "${CYAN}── Fazle UI (:3020) ──${NC}"
http_check "Fazle UI homepage" GET "${BASE}:3020"
echo ""

# ── 8. Ollama ───────────────────────────────────────────────
echo -e "${CYAN}── Ollama LLM ──${NC}"
OLLAMA_TAGS=$(docker exec ollama curl -s http://localhost:11434/api/tags 2>/dev/null || echo "FAIL")
if echo "$OLLAMA_TAGS" | grep -q '"models"'; then
    MODEL_COUNT=$(echo "$OLLAMA_TAGS" | grep -oP '"name"\s*:\s*"\K[^"]+' | wc -l)
    pass "Ollama reachable — $MODEL_COUNT model(s) available"
    echo "$OLLAMA_TAGS" | grep -oP '"name"\s*:\s*"\K[^"]+' | while read -r m; do
        echo "    → $m"
    done
else
    fail "Ollama unreachable or no models"
fi
echo ""

# ── 9. Qdrant ───────────────────────────────────────────────
echo -e "${CYAN}── Qdrant Vector DB ──${NC}"
QDRANT_HEALTH=$(docker exec qdrant bash -c 'echo > /dev/tcp/localhost/6333 && echo OK' 2>/dev/null || echo "FAIL")
if [ "$QDRANT_HEALTH" = "OK" ]; then
    pass "Qdrant health OK (port open)"
else
    fail "Qdrant health: $QDRANT_HEALTH"
fi
# Query collections via fazle-memory (same network, has python)
COLLECTIONS=$(docker exec fazle-memory python -c "
import urllib.request, json
try:
    r = urllib.request.urlopen('http://qdrant:6333/collections', timeout=5)
    data = json.loads(r.read())
    colls = data.get('result', {}).get('collections', [])
    for c in colls:
        name = c['name']
        info = json.loads(urllib.request.urlopen(f'http://qdrant:6333/collections/{name}', timeout=5).read())
        points = info.get('result', {}).get('points_count', '?')
        print(f'{name}:{points}')
except: pass
" 2>/dev/null || echo "")
if [ -n "$COLLECTIONS" ]; then
    pass "Qdrant collections reachable"
    while IFS= read -r entry; do
        [ -z "$entry" ] && continue
        col="${entry%%:*}"
        pts="${entry#*:}"
        echo "    → $col ($pts vectors)"
    done <<< "$COLLECTIONS"
else
    fail "Qdrant collections unreachable"
fi
echo ""

# ── 10. Integration: Decision Endpoint ─────────────────────
echo -e "${CYAN}── Integration Test: /fazle/decision ──${NC}"
DECISION_BODY='{"caller":"test-script","intent":"health_check","conversation_context":"Automated test from test-fazle.sh"}'
http_check "POST /fazle/decision" POST "${BASE}:8100/fazle/decision" "$DECISION_BODY" || true
echo ""

# ── 11. Integration: Chat Endpoint ─────────────────────────
echo -e "${CYAN}── Integration Test: /fazle/chat ──${NC}"
CHAT_BODY='{"message":"Hello Fazle, this is a health check test","user":"system"}'
http_check "POST /fazle/chat" POST "${BASE}:8100/fazle/chat" "$CHAT_BODY" || true
echo ""

# ── Summary ─────────────────────────────────────────────────
echo "============================================"
echo -e " ${GREEN}✓ $PASS passed${NC}  ${RED}✗ $FAIL failed${NC}"
if [ $FAIL -eq 0 ]; then
    echo -e " ${GREEN}All Fazle tests passed${NC}"
else
    echo -e " ${YELLOW}$FAIL test(s) failed — check logs above${NC}"
fi
echo "============================================"

exit $FAIL
