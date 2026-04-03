#!/usr/bin/env python3
"""Test parallel LLM failover routing in fazle-brain."""
import requests, time

BRAIN = "http://172.22.0.7:8200"

print("=" * 60)
print("TEST: Parallel LLM failover (/chat)")
print("=" * 60)

payload = {
    "user_id": "test-parallel",
    "message": "Hello, how are you?",
    "platform": "test"
}

t0 = time.time()
try:
    r = requests.post(f"{BRAIN}/chat", json=payload, timeout=30)
    elapsed = time.time() - t0
    print(f"Status : {r.status_code}")
    print(f"Elapsed: {elapsed:.2f}s")
    if r.status_code == 200:
        data = r.json()
        reply = data.get("reply", "NO REPLY")
        print(f"Reply  : {reply[:200]}")
        if "presence" in data:
            print(f"Presence: {data['presence']}")
    else:
        print(f"Body   : {r.text[:300]}")
except Exception as e:
    elapsed = time.time() - t0
    print(f"FAIL ({elapsed:.2f}s): {e}")

print("=" * 60)
print("Done. Check 'docker logs fazle-brain --tail 20' for parallel routing details.")
