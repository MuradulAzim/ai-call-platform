import urllib.request
import json

data = json.dumps({
    "message": "hello",
    "user_name": "Azim",
    "relationship": "family"
}).encode()

req = urllib.request.Request(
    "http://localhost:8200/chat/voice",
    data=data,
    headers={"Content-Type": "application/json"}
)

try:
    resp = urllib.request.urlopen(req, timeout=30)
    print("STATUS:", resp.status)
    print("BODY:", resp.read().decode())
except Exception as e:
    print("ERROR:", e)
