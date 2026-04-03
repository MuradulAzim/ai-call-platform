import httpx
url = "http://fazle-autonomy-engine:9100/governor/stability"
r = httpx.get(url, timeout=10)
print("STABILITY:", r.text)

url2 = "http://fazle-autonomy-engine:9100/governor/dashboard"
r2 = httpx.get(url2, timeout=10)
print("DASHBOARD:", r2.text)
