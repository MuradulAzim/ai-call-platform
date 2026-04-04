import json, urllib.request, time

url = "http://localhost:8200/chat"
payload = json.dumps({
    "message": "Assalamu alaikum bhai, ki obostha?",
    "user": "WhatsAppTest",
    "relationship": "social",
    "conversation_id": "social-whatsapp-01700000001"
}).encode()

t0 = time.time()
req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
resp = urllib.request.urlopen(req, timeout=55)
d = json.loads(resp.read())
elapsed = time.time() - t0

reply = d.get("reply", "")
route = d.get("route", "?")
print(f"Time: {elapsed:.1f}s")
print(f"Route: {route}")
print(f"Reply({len(reply)}c): {reply[:400]}")
