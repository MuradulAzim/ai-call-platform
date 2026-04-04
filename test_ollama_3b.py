import httpx, time

# Test qwen2.5:3b directly with a minimal prompt
t0 = time.time()
try:
    r = httpx.post("http://ollama:11434/api/chat", json={
        "model": "qwen2.5:3b",
        "messages": [
            {"role": "system", "content": "You are Azim's AI assistant. Reply in Bengali, keep it brief (1-2 sentences)."},
            {"role": "user", "content": "hi"}
        ],
        "stream": False,
        "options": {"num_predict": 150}
    }, timeout=120)
    elapsed = time.time() - t0
    print("Status:", r.status_code, "| Time:", round(elapsed, 1), "s")
    if r.status_code == 200:
        data = r.json()
        print("Reply:", data["message"]["content"][:300])
    else:
        print("Error:", r.text[:300])
except Exception as e:
    elapsed = time.time() - t0
    print("ERROR:", type(e).__name__, "in", round(elapsed, 1), "s:", e)
