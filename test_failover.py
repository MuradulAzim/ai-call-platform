#!/usr/bin/env python3
"""Test LLM failover routing in fazle-brain."""
import requests, time, json

BRAIN = "http://172.22.0.7:8200"

# Test 1: Health check
print("=" * 50)
print("TEST 1: Health check")
try:
    r = requests.get(f"{BRAIN}/health", timeout=5)
    print(f"  Status: {r.status_code}, Body: {r.text[:100]}")
except Exception as e:
    print(f"  FAIL: {e}")

# Test 2: Full chat (should trigger failover chain)
print("\n" + "=" * 50)
print("TEST 2: Full /chat (failover chain test)")
payload = {
    "user_id": "test-failover",
    "message": "Hello, how are you?",
    "platform": "test"
}
try:
    t0 = time.time()
    r = requests.post(f"{BRAIN}/chat", json=payload, timeout=45)
    elapsed = time.time() - t0
    print(f"  Status: {r.status_code}")
    print(f"  Elapsed: {elapsed:.2f}s")
    if r.status_code == 200:
        data = r.json()
        print(f"  Reply: {data.get('reply', 'NO REPLY')[:150]}")
        if 'presence' in data:
            print(f"  Presence: {data['presence']}")
    else:
        print(f"  Body: {r.text[:200]}")
except Exception as e:
    print(f"  FAIL: {e}")

# Test 3: Check brain logs for failover chain
print("\n" + "=" * 50)
print("TEST 3: Done. Check docker logs fazle-brain for failover chain entries.")
print("=" * 50)
