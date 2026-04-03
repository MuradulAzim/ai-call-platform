import httpx
import os

API_KEY = os.getenv("FAZLE_API_KEY", "2aMFFfIaGDfgfP6JiXaevEgMRx9aZtgAzYriHGRcpvdEcWCtp7Xpqul0BYdjFchq")
url = "http://127.0.0.1:8100/fazle/voice/clone"

# Test 1: No file → should get 422 (validation error)
r = httpx.post(url, headers={"X-API-Key": API_KEY})
print(f"Test 1 (no file): {r.status_code} -> {r.text[:200]}")

# Test 2: Wrong file type → should get 400
r2 = httpx.post(url, headers={"X-API-Key": API_KEY}, files={"file": ("test.txt", b"hello", "text/plain")})
print(f"Test 2 (wrong ext): {r2.status_code} -> {r2.text[:200]}")

# Test 3: API-key auth → should get 400 (JWT required)
r3 = httpx.post(url, headers={"X-API-Key": API_KEY}, files={"file": ("test.mp3", b"fake-audio-data", "audio/mpeg")})
print(f"Test 3 (api-key auth): {r3.status_code} -> {r3.text[:200]}")
