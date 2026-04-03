import urllib.request
import json

# Test Brain health
try:
    r = urllib.request.urlopen("http://localhost:8200/health")
    print("BRAIN_HEALTH:", r.read().decode())
except Exception as e:
    print("BRAIN_HEALTH_ERROR:", str(e))

# Test Autonomy health
try:
    r = urllib.request.urlopen("http://localhost:9100/health")
    print("AUTONOMY_HEALTH:", r.read().decode())
except Exception as e:
    print("AUTONOMY_HEALTH_ERROR:", str(e))

# Test Strategy insights
try:
    r = urllib.request.urlopen("http://localhost:9100/strategy/insights")
    print("STRATEGY_INSIGHTS:", r.read().decode())
except Exception as e:
    print("STRATEGY_INSIGHTS_ERROR:", str(e))

# Test Strategy report
try:
    r = urllib.request.urlopen("http://localhost:9100/strategy/report")
    print("STRATEGY_REPORT:", r.read().decode())
except Exception as e:
    print("STRATEGY_REPORT_ERROR:", str(e))

# Test Chat
try:
    data = json.dumps({"message": "hey bro", "user": "Azim", "relationship": "self"}).encode()
    req = urllib.request.Request("http://localhost:8200/chat", data=data, headers={"Content-Type": "application/json"})
    r = urllib.request.urlopen(req, timeout=30)
    resp = json.loads(r.read().decode())
    print("CHAT_REPLY:", resp.get("reply", "NO_REPLY"))
    print("CHAT_PRESENCE:", json.dumps(resp.get("presence", {})))
    print("CHAT_INTELLIGENCE:", json.dumps(resp.get("intelligence", {})))
except Exception as e:
    print("CHAT_ERROR:", str(e))
