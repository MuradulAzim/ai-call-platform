import httpx, json, time, sys
BRAIN = "http://127.0.0.1:8200"
conv_id = "social-whatsapp-0171234567"

# Message 2 from same user (should have context from message 1)
print("Sending follow-up message from same user...", flush=True)
r2 = httpx.post(f"{BRAIN}/chat", json={
    "message": "বেতন কত?",
    "user": "Test User",
    "relationship": "social",
    "conversation_id": conv_id,
    "context": "Platform: whatsapp. Reply naturally.",
}, timeout=120)
print(f"Status: {r2.status_code}", flush=True)
data2 = r2.json()
print(f"Reply: {data2.get('reply', 'NO REPLY')[:300]}", flush=True)
print(flush=True)

# Now send same question AGAIN — should get DIFFERENT wording
print("Sending SAME question again (anti-repetition test)...", flush=True)
time.sleep(1)
r3 = httpx.post(f"{BRAIN}/chat", json={
    "message": "বেতন কত?",
    "user": "Test User",
    "relationship": "social",
    "conversation_id": conv_id,
    "context": "Platform: whatsapp. Reply naturally.",
}, timeout=120)
data3 = r3.json()
reply2 = data2.get("reply", "")
reply3 = data3.get("reply", "")
print(f"Reply 2: {reply2[:200]}", flush=True)
print(f"Reply 3: {reply3[:200]}", flush=True)
same = reply2.strip() == reply3.strip()
print(f"Identical? {same}", flush=True)
if not same:
    print("PASS: Anti-repetition working!", flush=True)
else:
    print("WARN: Replies are identical", flush=True)
print(flush=True)

# Test different user — no leakage
print("Sending from DIFFERENT user (memory isolation test)...", flush=True)
r4 = httpx.post(f"{BRAIN}/chat", json={
    "message": "আমি কি আগে কথা বলেছি?",
    "user": "Brand New User",
    "relationship": "social",
    "conversation_id": "social-whatsapp-0178888888",
    "context": "Platform: whatsapp. Reply naturally.",
}, timeout=120)
data4 = r4.json()
print(f"New user reply: {data4.get('reply', 'NO REPLY')[:300]}", flush=True)
print("(Should NOT reference 0171234567's conversation)", flush=True)
print(flush=True)
print("ALL TESTS DONE", flush=True)
