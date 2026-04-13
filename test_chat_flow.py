#!/usr/bin/env python3
"""Test: Ollama-first LLM with OpenAI fallback + DB conversation logging."""
import requests, json, sys

BASE = "http://localhost:8100"

# 1. Login
r = requests.post(f"{BASE}/auth/login", json={
    "email": "azim@iamazim.com",
    "password": "Azim@Fazle2026!"
})
assert r.status_code == 200, f"Login failed: {r.status_code} {r.text}"
token = r.json()["access_token"]
print("1. Login OK")

# 2. Send chat
r2 = requests.post(f"{BASE}/fazle/chat", json={
    "message": "Hello, how are you?",
    "user_id": "test-user-1"
}, headers={"Authorization": f"Bearer {token}"}, timeout=90)
print(f"2. Chat status: {r2.status_code}")
if r2.status_code == 200:
    data = r2.json()
    print(f"   Reply: {json.dumps(data, ensure_ascii=False)[:300]}")
else:
    print(f"   Error: {r2.text[:300]}")

# 3. Check gateway health (internal Docker network, use docker exec)
import subprocess
result3 = subprocess.run([
    "docker", "exec", "fazle-llm-gateway",
    "python3", "-c",
    "import urllib.request; print(urllib.request.urlopen('http://localhost:8800/health').read().decode())"
], capture_output=True, text=True, timeout=10)
print(f"3. Gateway health: {result3.stdout.strip()}")

# 4. Check DB for logged conversations
result = subprocess.run([
    "docker", "exec", "ai-postgres",
    "psql", "-U", "postgres", "-d", "postgres", "-t", "-c",
    "SELECT count(*) FROM llm_conversation_log;"
], capture_output=True, text=True)
count = result.stdout.strip()
print(f"4. Conversations in DB: {count}")

# 5. Check training data endpoint
result5 = subprocess.run([
    "docker", "exec", "fazle-llm-gateway",
    "python3", "-c",
    "import urllib.request; print(urllib.request.urlopen('http://localhost:8800/training-data?limit=5').read().decode())"
], capture_output=True, text=True, timeout=10)
print(f"5. Training data: {result5.stdout.strip()[:300]}")

print("\nDone!")
