import httpx, time, json, random

BASE = "http://localhost:8200"
cid = "test-" + str(random.randint(1000,9999))

# Warmup: loads model
t = time.time()
r = httpx.post(BASE + "/chat", json={
    "message": "hi", "user": "WarmUp",
    "relationship": "self", "conversation_id": "warmup-" + cid
}, timeout=55)
print("Warmup: %d in %.1fs" % (r.status_code, time.time()-t))

# Real chat test (model should be warm now)
t = time.time()
r = httpx.post(BASE + "/chat", json={
    "message": "Tell me about your security business", "user": "TestUser",
    "relationship": "self", "conversation_id": cid
}, timeout=55)
d = r.json()
elapsed = time.time()-t
reply = d.get("reply", "-") or "-"
print("Chat: %d in %.1fs" % (r.status_code, elapsed))
print("Reply: %s" % reply[:200])
