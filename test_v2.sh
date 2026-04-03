#!/bin/bash
# Write curl results to files, then cat them
curl -s http://localhost:8200/health > /tmp/r1.txt 2>&1
curl -s http://localhost:9100/health > /tmp/r2.txt 2>&1
curl -s http://localhost:9100/strategy/insights > /tmp/r3.txt 2>&1
curl -s http://localhost:9100/strategy/report > /tmp/r4.txt 2>&1
curl -s --max-time 30 http://localhost:8200/chat -X POST \
  -H 'Content-Type: application/json' \
  -d '{"message":"hey bro","user":"Azim","relationship":"self"}' > /tmp/r5.txt 2>&1

echo "BRAIN_HEALTH:"
cat /tmp/r1.txt
echo ""
echo "AUTONOMY_HEALTH:"
cat /tmp/r2.txt
echo ""
echo "STRATEGY_INSIGHTS:"
cat /tmp/r3.txt
echo ""
echo "STRATEGY_REPORT:"
cat /tmp/r4.txt
echo ""
echo "CHAT_RESULT:"
cat /tmp/r5.txt
echo ""
echo "TEST_DONE"
