import httpx, asyncio, json

async def test():
    async with httpx.AsyncClient(timeout=30.0) as c:
        r = await c.post(
            "http://ollama:11434/api/chat",
            json={
                "model": "qwen2.5:1.5b",
                "messages": [{"role": "user", "content": "hi"}],
                "stream": False
            }
        )
        print(f"Status: {r.status_code}")
        print(f"Body: {r.text[:500]}")

asyncio.run(test())
