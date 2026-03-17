#!/bin/bash
# Simulate browser-like login request through Nginx

echo "=== Test 1: Direct to backend (bypassing Nginx) ==="
curl -s -w "\nHTTP:%{http_code}" -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -H "Accept: */*" \
  -H "Origin: https://iamazim.com" \
  -d '{"email":"admin@iamazim.com","password":"Admin123!"}'

echo ""
echo ""
echo "=== Test 2: Through Nginx (like browser) ==="
curl -s -w "\nHTTP:%{http_code}" -X POST https://iamazim.com/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/plain, */*" \
  -H "Origin: https://iamazim.com" \
  -H "Referer: https://iamazim.com/auth/login" \
  -d '{"email":"admin@iamazim.com","password":"Admin123!"}'

echo ""
echo ""
echo "=== Test 3: Through api.iamazim.com (cross-origin) ==="
curl -s -w "\nHTTP:%{http_code}" -X POST https://api.iamazim.com/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -H "Accept: application/json" \
  -H "Origin: https://iamazim.com" \
  -d '{"email":"admin@iamazim.com","password":"Admin123!"}'

echo ""
echo ""
echo "=== Test 4: OPTIONS preflight to Nginx ==="
curl -s -w "\nHTTP:%{http_code}" -X OPTIONS https://iamazim.com/api/v1/auth/login \
  -H "Origin: https://iamazim.com" \
  -H "Access-Control-Request-Method: POST" \
  -H "Access-Control-Request-Headers: content-type" \
  -D -

echo ""
echo ""
echo "=== Test 5: Session endpoint (POST) ==="
TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@iamazim.com","password":"Admin123!"}' | python3 -c "import sys,json; print(json.load(sys.stdin).get('token',''))" 2>/dev/null)

echo "Token obtained: ${TOKEN:0:20}..."
curl -s -w "\nHTTP:%{http_code}" -X POST https://iamazim.com/api/auth/session \
  -H "Content-Type: application/json" \
  -H "Origin: https://iamazim.com" \
  -d "{\"token\":\"$TOKEN\",\"user\":{\"id\":1,\"email\":\"admin@iamazim.com\"}}"

echo ""
echo ""
echo "=== API LOGS (last login requests) ==="
docker logs dograh-api --tail 100 2>&1 | grep -E 'auth|422|500|error' | grep -v health | tail -10

echo ""
echo "=== UI LOGS (errors only) ==="
docker logs dograh-ui 2>&1 | grep -iE 'error|syntax|fail' | tail -5
