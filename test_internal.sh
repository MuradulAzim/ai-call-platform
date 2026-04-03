#!/bin/bash
echo "=== Stats (via docker exec) ==="
docker exec fazle-api curl -s --max-time 10 http://fazle-social-engine:9800/stats
echo ""

echo "=== Reply-stats (via docker exec) ==="
docker exec fazle-api curl -s --max-time 10 http://fazle-social-engine:9800/reply-stats
echo ""

echo "=== Social health ==="
docker exec fazle-api curl -s --max-time 10 http://fazle-social-engine:9800/health
echo ""

echo "=== Brain health ==="
docker exec fazle-api curl -s --max-time 10 http://fazle-brain:8200/health
echo ""

echo "=== Brain /chat ==="
docker exec fazle-api curl -s --max-time 20 http://fazle-brain:8200/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"test","user":"test"}'
echo ""

echo "=== Brain logs (last 10) ==="
docker logs fazle-brain --tail 10 2>&1
echo ""
