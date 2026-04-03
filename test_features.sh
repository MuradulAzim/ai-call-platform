#!/bin/bash
# Test 1: Brain health
echo "=== Brain Health ==="
curl -s http://localhost:8200/health
echo ""

# Test 2: Chat with presence
echo "=== Chat with Presence ==="
curl -s --max-time 30 http://localhost:8200/chat -X POST \
  -H 'Content-Type: application/json' \
  -d '{"message":"hey bro","user":"Azim","relationship":"self"}'
echo ""

# Test 3: Autonomy health
echo "=== Autonomy Health ==="
curl -s http://localhost:9100/health
echo ""

# Test 4: Strategy insights
echo "=== Strategy Insights ==="
curl -s http://localhost:9100/strategy/insights
echo ""

# Test 5: Strategy report
echo "=== Strategy Report ==="
curl -s http://localhost:9100/strategy/report
echo ""
