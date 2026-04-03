#!/bin/bash
API_KEY="2aMFFfIaGDfgfP6JiXaevEgMRx9aZtgAzYriHGRcpvdEcWCtp7Xpqul0BYdjFchq"

echo "=== Test 1: /fazle/chat ==="
curl -s --max-time 25 http://localhost:8100/fazle/chat \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -d '{"message":"hello"}'
echo ""

echo "=== Test 2: Social engine /stats ==="
curl -s --max-time 10 http://localhost:9800/stats
echo ""

echo "=== Test 3: Social engine /reply-stats ==="
curl -s --max-time 10 http://localhost:9800/reply-stats
echo ""

echo "=== Test 4: Social engine /health ==="
curl -s --max-time 10 http://localhost:9800/health
echo ""

echo "=== Test 5: Brain /health ==="
curl -s --max-time 10 http://localhost:8200/health
echo ""

echo "=== Test 6: Container health ==="
docker ps --format 'table {{.Names}}\t{{.Status}}' | grep -E 'fazle-api|fazle-brain|fazle-social|ollama'
echo ""

echo "=== DONE ==="
