#!/bin/bash
echo "=== Stats ==="
docker exec fazle-social-engine python3 -c "import urllib.request; print(urllib.request.urlopen('http://localhost:9800/stats').read().decode())"
echo ""

echo "=== Reply-stats ==="
docker exec fazle-social-engine python3 -c "import urllib.request; print(urllib.request.urlopen('http://localhost:9800/reply-stats').read().decode())"
echo ""

echo "=== Social health ==="
docker exec fazle-social-engine python3 -c "import urllib.request; print(urllib.request.urlopen('http://localhost:9800/health').read().decode())"
echo ""

echo "=== Brain health ==="
docker exec fazle-brain python3 -c "import urllib.request; print(urllib.request.urlopen('http://localhost:8200/health').read().decode())"
echo ""

echo "=== Feedback ==="
docker exec fazle-social-engine python3 -c "import urllib.request; print(urllib.request.urlopen('http://localhost:9800/feedback').read().decode())"
echo ""
