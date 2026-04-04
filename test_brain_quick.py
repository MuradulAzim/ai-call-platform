import httpx, time
t0 = time.time()
try:
    r = httpx.post("http://fazle-brain:8200/chat", json={
        "message": "tell me about your security services",
        "sender_id": "timeout-test-v3",
        "platform": "whatsapp",
        "user_name": "TestUser"
    }, timeout=45)
    elapsed = time.time() - t0
    print("Status:", r.status_code, "| Time:", round(elapsed, 1), "s")
    data = r.json()
    reply = data.get("reply", "NO REPLY")
    print("Reply:", reply[:300])
except Exception as e:
    elapsed = time.time() - t0
    print("ERROR:", type(e).__name__, "in", round(elapsed, 1), "s:", e)
