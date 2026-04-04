"""Test optimized prompt: quality + speed for both social and family chat."""
import httpx, time, json, asyncio

BRAIN = "http://localhost:8200"

tests = [
    {
        "name": "Social: Greeting (Bangla)",
        "payload": {
            "message": "Assalamu alaikum bhai, ki obostha?",
            "user": "TestUser",
            "relationship": "social",
            "conversation_id": "social-whatsapp-01700000099",
        },
    },
    {
        "name": "Social: Job inquiry",
        "payload": {
            "message": "ভাই কাজ আছে নাকি? বেতন কত?",
            "user": "JobSeeker",
            "relationship": "social",
            "conversation_id": "social-whatsapp-01700000088",
        },
    },
    {
        "name": "Social: Who are you?",
        "payload": {
            "message": "আপনি কে? আপনি কি AI?",
            "user": "Curious",
            "relationship": "social",
            "conversation_id": "social-whatsapp-01700000077",
        },
    },
    {
        "name": "Self: Quick hi",
        "payload": {
            "message": "hi",
            "user": "Azim",
            "relationship": "self",
            "conversation_id": "self-test-1",
        },
    },
    {
        "name": "Social: Scam accusation",
        "payload": {
            "message": "এইটা কি বাটপারি? টাকা মারবে নাকি?",
            "user": "Skeptic",
            "relationship": "social",
            "conversation_id": "social-whatsapp-01700000066",
        },
    },
]

print("=" * 70)
print("OPTIMIZED PROMPT TEST — Quality + Speed")
print("=" * 70)

# Warmup: load model into memory first
print("\n--- WARMUP (loading model) ---")
start = time.time()
try:
    with httpx.Client(timeout=120.0) as client:
        r = client.post(f"{BRAIN}/chat", json={
            "message": "hi", "user": "Warmup", "relationship": "self", "conversation_id": "warmup-1"
        })
    print(f"  Warmup done in {time.time()-start:.1f}s — status {r.status_code}")
except Exception as e:
    print(f"  Warmup failed: {e}")

for t in tests:
    print(f"\n--- {t['name']} ---")
    print(f"  Input: {t['payload']['message']}")
    start = time.time()
    try:
        with httpx.Client(timeout=60.0) as client:
            r = client.post(f"{BRAIN}/chat", json=t["payload"])
        elapsed = time.time() - start
        if r.status_code == 200:
            d = r.json()
            reply = d.get("reply", "")
            route = d.get("intelligence", {}).get("route", d.get("route", "?"))
            print(f"  Reply ({len(reply)}c): {reply[:300]}")
            print(f"  Time: {elapsed:.1f}s | Route: {route}")
        else:
            print(f"  ERROR: {r.status_code} in {time.time()-start:.1f}s")
    except Exception as e:
        print(f"  FAIL: {e}")

print("\n" + "=" * 70)
print("DONE")
