import httpx, json, asyncio

async def main():
    endpoints = [
        ("Tree browse", "GET", "http://fazle-memory:8300/tree/browse", None),
        ("Tree search: security pricing", "POST", "http://fazle-memory:8300/tree/search", {"query": "security guard salary price", "limit": 3}),
        ("Tree search: pricing branch", "POST", "http://fazle-memory:8300/tree/search", {"query": "how much cost", "tree_path": "azim/business/al-aqsa-security/pricing", "limit": 3}),
        ("Tree branch: business", "GET", "http://fazle-memory:8300/tree/branch?path=azim/business&limit=10", None),
        ("KG tree structure", "GET", "http://fazle-knowledge-graph:9300/tree/structure", None),
        ("Brain proxy: tree/browse", "GET", "http://localhost:8200/tree/browse", None),
        ("Brain proxy: tree/search", "POST", "http://localhost:8200/tree/search", {"query": "Fazle Azim phone number", "limit": 3}),
    ]
    async with httpx.AsyncClient(timeout=30.0) as client:
        for name, method, url, body in endpoints:
            try:
                if method == "GET":
                    r = await client.get(url)
                else:
                    r = await client.post(url, json=body)
                data = r.json()
                out = json.dumps(data, indent=2, ensure_ascii=False)
                print(f"\n[OK] {name}:")
                print(out[:400])
            except Exception as e:
                print(f"\n[FAIL] {name}: {e}")

asyncio.run(main())
