import urllib.request, json, sys

endpoints = [
    ("stats", "http://localhost:9800/stats"),
    ("reply-stats", "http://localhost:9800/reply-stats"),
    ("health", "http://localhost:9800/health"),
    ("feedback", "http://localhost:9800/feedback"),
]

for name, url in endpoints:
    try:
        resp = urllib.request.urlopen(url, timeout=10)
        data = resp.read().decode()
        print(f"=== {name} === {data[:300]}")
    except Exception as e:
        print(f"=== {name} === ERROR: {e}")
