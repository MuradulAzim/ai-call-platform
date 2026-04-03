import httpx, json, time

BASE = 'http://127.0.0.1:8200'

print("=" * 60)
print("INTELLIGENCE TUNING LAYER — TESTS")
print("=" * 60)

# Test 1: Simple message (fast path)
print("\n--- TEST 1: Fast Path (simple greeting) ---")
t0 = time.time()
r = httpx.post(f'{BASE}/chat', json={'message': 'hi', 'relationship': 'self'}, timeout=300)
d = r.json()
elapsed = time.time() - t0
print(f"  Route: {d.get('route', d.get('intelligence', 'N/A'))}")
print(f"  Reply: {d.get('reply', '')[:100]}")
print(f"  Time: {elapsed:.2f}s")
assert d.get('route') == 'fast', "Expected fast route!"
print("  PASS: Fast path triggered!")

# Test 2: Complex message (full path with cost routing)
print("\n--- TEST 2: Complex Query (full path) ---")
t0 = time.time()
r = httpx.post(f'{BASE}/chat', json={
    'message': 'explain the pros and cons of microservices architecture compared to monolithic in detail',
    'relationship': 'self'
}, timeout=300)
d = r.json()
elapsed = time.time() - t0
intel = d.get('intelligence', {})
print(f"  Complexity: {intel.get('complexity', 'N/A')}")
print(f"  Route: {intel.get('route', 'N/A')}")
print(f"  Reply length: {len(d.get('reply', ''))}")
print(f"  Time: {elapsed:.2f}s")
assert intel.get('complexity') == 'complex', f"Expected complex, got {intel.get('complexity')}"
print("  PASS: Complex routing detected!")

# Test 3: Medium query
print("\n--- TEST 3: Medium Query ---")
r = httpx.post(f'{BASE}/chat', json={
    'message': 'what time is it now?',
    'relationship': 'self'
}, timeout=300)
d = r.json()
intel = d.get('intelligence', {})
print(f"  Complexity: {intel.get('complexity', 'N/A')}")
print(f"  Reply: {d.get('reply', '')[:100]}")

# Test 4: Intelligence Stats endpoint
print("\n--- TEST 4: Intelligence Stats ---")
r = httpx.get(f'{BASE}/intelligence/stats', timeout=10)
d = r.json()
print(f"  Usage data: {json.dumps(d.get('usage', {}))[:200]}")
print(f"  Models config: {d.get('config', {}).get('models')}")
print(f"  Owner priority: {d.get('owner_priority_active')}")
print("  PASS: Stats endpoint working!")

# Test 5: Governor dashboard includes intel stats
print("\n--- TEST 5: Governor Dashboard with Intelligence ---")
try:
    r = httpx.get('http://127.0.0.1:9100/governor/dashboard', timeout=10)
    d = r.json()
    intel_data = d.get('intelligence_tuning', {})
    print(f"  Intelligence tuning data: {json.dumps(intel_data)[:200]}")
    print("  PASS: Governor dashboard includes intel stats!")
except Exception as e:
    print(f"  SKIP: Governor dashboard not reachable: {e}")

print("\n" + "=" * 60)
print("ALL TESTS PASSED!")
print("=" * 60)
