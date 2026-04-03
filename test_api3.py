import urllib.request
import json

BRAIN = "http://172.22.0.7:8200"
AUTONOMY = "http://172.22.0.18:9100"

# Test 1: Trigger strategy manually
try:
    req = urllib.request.Request(f"{AUTONOMY}/strategy/trigger", data=b'', headers={"Content-Type": "application/json"}, method="POST")
    r = urllib.request.urlopen(req, timeout=10)
    print("STRATEGY_TRIGGER:", r.read().decode())
except Exception as e:
    print("STRATEGY_TRIGGER_ERROR:", str(e))

# Test 2: Simple chat (fast path)
try:
    data = json.dumps({"message": "hi", "user": "Azim", "relationship": "self"}).encode()
    req = urllib.request.Request(f"{BRAIN}/chat", data=data, headers={"Content-Type": "application/json"})
    r = urllib.request.urlopen(req, timeout=60)
    resp = json.loads(r.read().decode())
    print("CHAT_REPLY:", resp.get("reply", "NO_REPLY"))
    has_presence = "presence" in resp
    print("HAS_PRESENCE:", has_presence)
    if has_presence:
        print("PRESENCE:", json.dumps(resp["presence"]))
    print("ROUTE:", resp.get("route", resp.get("intelligence", {}).get("route", "unknown")))
except Exception as e:
    print("CHAT_ERROR:", str(e))
