import httpx
r = httpx.get("http://127.0.0.1:8200/health")
print("HEALTH:", r.status_code, r.text[:100])
