import json, urllib.request, time

# Simulate a WhatsApp message going through social-engine → brain → Ollama
# This tests the FULL webhook pipeline
url = "http://localhost:8200/chat"

tests = [
    {"msg": "Hi, who are you?", "rel": "self", "user": "Azim", "cid": "e2e-self-1"},
    {"msg": "bhai ki korso?", "rel": "social", "user": "Rahim", "cid": "e2e-social-1"},
    {"msg": "What is your business?", "rel": "social", "user": "Client", "cid": "e2e-social-2"},
]

for t in tests:
    payload = json.dumps({
        "message": t["msg"],
        "user": t["user"],
        "relationship": t["rel"],
        "conversation_id": t["cid"]
    }).encode()
    
    t0 = time.time()
    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
    resp = urllib.request.urlopen(req, timeout=55)
    d = json.loads(resp.read())
    elapsed = time.time() - t0
    
    reply = d.get("reply", "")
    print(f"[{t['rel']:6s}] {elapsed:5.1f}s | {t['msg']}")
    print(f"         -> {reply[:150]}")
    print()
