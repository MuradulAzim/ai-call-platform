import httpx, time, json

# Call brain's chat endpoint and capture what it sends to Ollama
# by checking Ollama's perspective

# First, check the system prompt size the brain generates
t0 = time.time()
try:
    r = httpx.post("http://fazle-brain:8200/chat", json={
        "message": "hello",
        "sender_id": "prompt-size-test",
        "platform": "whatsapp",
        "user_name": "TestUser"
    }, timeout=60)
    elapsed = time.time() - t0
    print("Status:", r.status_code, "| Time:", round(elapsed, 1), "s")
    data = r.json()
    print("Reply:", data.get("reply", "NO REPLY")[:200])
    print("Route:", data.get("route", "N/A"))
except Exception as e:
    print("ERROR:", type(e).__name__, "in", round(time.time()-t0, 1), "s:", e)
