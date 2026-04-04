import httpx, time

# Warm up qwen2.5:1.5b with a tiny prompt
print("Warming up qwen2.5:1.5b...")
t0 = time.time()
try:
    r = httpx.post("http://ollama:11434/api/chat", json={
        "model": "qwen2.5:1.5b",
        "messages": [{"role": "user", "content": "hi"}],
        "stream": False,
        "options": {"num_predict": 1}
    }, timeout=120)
    elapsed = time.time() - t0
    print("Warmup done:", r.status_code, "in", round(elapsed, 1), "s")
except Exception as e:
    print("ERROR:", type(e).__name__, "in", round(time.time()-t0, 1), "s:", e)

# Now test actual chat
print("\nTesting chat...")
t0 = time.time()
try:
    r = httpx.post("http://fazle-brain:8200/chat", json={
        "message": "tell me about your security services",
        "sender_id": "test-final",
        "platform": "whatsapp",
        "user_name": "TestUser"
    }, timeout=60)
    elapsed = time.time() - t0
    print("Status:", r.status_code, "| Time:", round(elapsed, 1), "s")
    data = r.json()
    reply = data.get("reply", "NO REPLY")
    print("Reply:", reply[:400])
except Exception as e:
    print("ERROR:", type(e).__name__, "in", round(time.time()-t0, 1), "s:", e)
