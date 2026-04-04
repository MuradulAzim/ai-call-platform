import httpx, time
r = httpx.post("http://localhost:8200/chat", json={
    "message": "hello",
    "user": "Debug",
    "relationship": "social",
    "conversation_id": "debug-003"
}, timeout=60.0)
print(f"Status: {r.status_code}")
print(f"Reply: {r.json().get('reply', '')[:200]}")
