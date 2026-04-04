import httpx
import sys

# Pull qwen2.5:1.5b via Ollama API
print("Starting pull of qwen2.5:1.5b...")
with httpx.Client(timeout=600) as client:
    r = client.post(
        "http://172.22.0.2:11434/api/pull",
        json={"name": "qwen2.5:1.5b"},
        timeout=600
    )
    for line in r.text.strip().split("\n"):
        if "completed" in line or "error" in line or "success" in line:
            print(line)
    print("Done. Status:", r.status_code)
