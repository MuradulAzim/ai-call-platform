import redis, json, os
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/1")
r = redis.Redis.from_url(REDIS_URL, decode_responses=True)
keys = r.keys("fazle:user:whatsapp:*")
print(f"WhatsApp user keys ({len(keys)}):")
for k in sorted(keys):
    t = r.type(k)
    if t == "list":
        length = r.llen(k)
        print(f"  {k} -> {length} items")
print()

# Check conversation keys with message counts
conv_keys = r.keys("fazle:conv:social-*")
print(f"Stable conversation keys ({len(conv_keys)}):")
for k in sorted(conv_keys):
    raw = r.get(k)
    if raw:
        history = json.loads(raw)
        print(f"  {k} -> {len(history)} messages")
print("DONE")
