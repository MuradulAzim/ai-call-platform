#!/bin/bash
# Test login endpoint
cat > /tmp/login.json << 'EOF'
{"email":"admin@iamazim.com","password":"Admin123!"}
EOF

echo "=== JSON CONTENT ==="
cat /tmp/login.json

echo ""
echo "=== LOGIN TEST ==="
curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d @/tmp/login.json

echo ""
echo "=== SIGNUP TEST ==="
cat > /tmp/signup.json << 'EOF'
{"email":"test3@iamazim.com","password":"Test1234!","name":"Test User"}
EOF
curl -s -X POST http://localhost:8000/api/v1/auth/signup \
  -H "Content-Type: application/json" \
  -d @/tmp/signup.json

echo ""
echo "=== NGINX ACCESS LOG (last auth requests) ==="
sudo grep -i 'auth' /var/log/nginx/access.log 2>/dev/null | tail -10

echo ""
echo "=== API LOGS (auth related) ==="
docker logs dograh-api --tail 100 2>&1 | grep -i 'auth\|login\|signup\|422\|500\|error' | tail -20
