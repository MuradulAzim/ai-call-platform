#!/bin/bash
# Test the full login flow

echo "=== 1. Login via backend ==="
LOGIN_RESULT=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@iamazim.com","password":"Admin123!"}')
echo "$LOGIN_RESULT"

TOKEN=$(echo "$LOGIN_RESULT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('token',''))" 2>/dev/null)
echo ""
echo "Token: ${TOKEN:0:30}..."

echo ""
echo "=== 2. Test /api/auth/session via frontend (direct) ==="
curl -s -w "\nHTTP:%{http_code}" -X POST http://localhost:3010/api/auth/session \
  -H "Content-Type: application/json" \
  -d "{\"token\":\"$TOKEN\",\"user\":{\"id\":1,\"email\":\"admin@iamazim.com\"}}"
echo ""

echo ""
echo "=== 3. Test /api/auth/session via Nginx ==="
curl -s -w "\nHTTP:%{http_code}" -X POST https://iamazim.com/api/auth/session \
  -H "Content-Type: application/json" \
  -d "{\"token\":\"$TOKEN\",\"user\":{\"id\":1,\"email\":\"admin@iamazim.com\"}}"
echo ""

echo ""
echo "=== 4. Test /api/auth/oss ==="
curl -s -w "\nHTTP:%{http_code}" https://iamazim.com/api/auth/oss
echo ""

echo ""
echo "=== 5. Check session route exists ==="
find /app/.next/server/app/api/auth/session -type f 2>/dev/null || echo "Route files not found (running outside container)"

echo ""
echo "=== 6. UI logs (last 10) ==="
docker logs dograh-ui --tail 10 2>&1

echo ""
echo "=== 7. Recent API errors ==="
docker logs dograh-api --tail 50 2>&1 | grep -v health | tail -10
