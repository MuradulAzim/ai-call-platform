import httpx, json, sys
BRAIN = "http://127.0.0.1:8200"
conv_id = "social-whatsapp-0171234567"
print("Sending message 1...", flush=True)
r1 = httpx.post(f"{BRAIN}/chat", json={
    "message": "কাজ কি?",
    "user": "Test User",
    "relationship": "social",
    "conversation_id": conv_id,
    "context": "Platform: whatsapp. Reply naturally.",
}, timeout=120)
print(f"Status: {r1.status_code}", flush=True)
data = r1.json()
print(f"Reply: {data.get('reply', 'NO REPLY')[:300]}", flush=True)
print(f"ConvID: {data.get('conversation_id', 'NONE')}", flush=True)
print("DONE", flush=True)
