import urllib.request
import json

BRAIN = "http://172.22.0.7:8200"

# Test complex chat (full path, not fast path)
try:
    data = json.dumps({
        "message": "ki korcho bro? explain to me how the system monitoring works in detail",
        "user": "Azim",
        "relationship": "self"
    }).encode()
    req = urllib.request.Request(f"{BRAIN}/chat", data=data, headers={"Content-Type": "application/json"})
    r = urllib.request.urlopen(req, timeout=120)
    resp = json.loads(r.read().decode())
    print("REPLY:", resp.get("reply", "NO_REPLY")[:200])
    print("HAS_PRESENCE:", "presence" in resp)
    print("PRESENCE:", json.dumps(resp.get("presence", {})))
    print("INTELLIGENCE:", json.dumps(resp.get("intelligence", {})))
except Exception as e:
    print("ERROR:", str(e))

# Test social relationship path
try:
    data = json.dumps({
        "message": "ki koaj ache?",
        "user": "customer1",
        "user_id": "social-user-123",
        "relationship": "social",
        "conversation_id": "social-whatsapp-01712345678"
    }).encode()
    req = urllib.request.Request(f"{BRAIN}/chat", data=data, headers={"Content-Type": "application/json"})
    r = urllib.request.urlopen(req, timeout=120)
    resp = json.loads(r.read().decode())
    print("\nSOCIAL_REPLY:", resp.get("reply", "NO_REPLY")[:200])
    print("SOCIAL_PRESENCE:", json.dumps(resp.get("presence", {})))
except Exception as e:
    print("\nSOCIAL_ERROR:", str(e))
