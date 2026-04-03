import redis, json, os
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/1")
r = redis.Redis.from_url(REDIS_URL, decode_responses=True)

# Check user-scoped keys
keys = r.keys("fazle:user:*")
print(f"User-scoped keys ({len(keys)}):")
for k in sorted(keys):
    t = r.type(k)
    if t == "list":
        length = r.llen(k)
        ttl = r.ttl(k)
        print(f"  {k} -> list({length}), TTL={ttl}s")
        # Show last entry
        last = r.lrange(k, -1, -1)
        if last:
            entry = json.loads(last[0])
            print(f"    last: {entry.get('role','?')}: {entry.get('content','')[:80]}")
    elif t == "string":
        print(f"  {k} -> string, TTL={r.ttl(k)}s")
print()

# Check conversation keys
conv_keys = r.keys("fazle:conv:social-*")
print(f"Conversation keys ({len(conv_keys)}):")
for k in sorted(conv_keys):
    history = json.loads(r.get(k) or "[]")
    print(f"  {k} -> {len(history)} messages")
print()
print("DONE")
