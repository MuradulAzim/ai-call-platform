#!/bin/bash
# Check session endpoint cookie behavior

# Get an auth token
TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@iamazim.com","password":"Admin123!"}' | \
  python3 -c "import sys,json; print(json.load(sys.stdin).get('token',''))" 2>/dev/null)

echo "Token: ${TOKEN:0:30}..."

echo ""
echo "=== Session Response Headers ==="
curl -s -D /tmp/session_headers.txt -X POST https://iamazim.com/api/auth/session \
  -H "Content-Type: application/json" \
  -d "{\"token\":\"$TOKEN\",\"user\":{\"id\":1,\"email\":\"admin@iamazim.com\"}}" \
  -o /tmp/session_body.txt

cat /tmp/session_headers.txt
echo ""
echo "Body:"
cat /tmp/session_body.txt
echo ""

echo ""
echo "=== Test with cookie jar (full flow) ==="
# Use cookie jar to test full flow
curl -s -c /tmp/cookies.txt -X POST https://iamazim.com/api/auth/session \
  -H "Content-Type: application/json" \
  -d "{\"token\":\"$TOKEN\",\"user\":{\"id\":1,\"email\":\"admin@iamazim.com\"}}" \
  -o /dev/null -w "Session: HTTP %{http_code}\n"

echo "Cookies saved:"
cat /tmp/cookies.txt
echo ""

echo ""
echo "=== Now test /after-sign-in with cookies ==="
curl -s -b /tmp/cookies.txt -w "HTTP:%{http_code}" -L -D - https://iamazim.com/after-sign-in -o /dev/null 2>/dev/null | grep -iE 'HTTP/|location|set-cookie'

echo ""
echo ""
echo "=== Test /api/auth/oss with cookies ==="
curl -s -b /tmp/cookies.txt https://iamazim.com/api/auth/oss
echo ""
