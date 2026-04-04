import json, urllib.request, time

url = "http://ollama:11434/api/chat"
payload = json.dumps({
    "model": "qwen2.5:1.5b",
    "messages": [
        {"role": "system", "content": "You are Azim, a friendly Bangladeshi businessman. Reply briefly."},
        {"role": "user", "content": "Hi, who are you?"}
    ],
    "stream": False,
    "options": {"num_predict": 80}
}).encode()

for i in range(3):
    t0 = time.time()
    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
    resp = urllib.request.urlopen(req, timeout=60)
    d = json.loads(resp.read())
    wall = time.time() - t0
    
    td = d.get("total_duration", 0) / 1e9
    ld = d.get("load_duration", 0) / 1e9
    pec = d.get("prompt_eval_count", 0)
    ped = d.get("prompt_eval_duration", 0) / 1e9
    ec = d.get("eval_count", 0)
    ed = d.get("eval_duration", 0) / 1e9
    tps = ec / ed if ed > 0 else 0
    reply = d.get("message", {}).get("content", "")
    
    print(f"--- Run {i+1} ---")
    print(f"  wall_time:    {wall:.2f}s")
    print(f"  total:        {td:.2f}s")
    print(f"  load:         {ld:.4f}s")
    print(f"  prompt_eval:  {pec} tokens in {ped:.2f}s ({pec/ped:.1f} t/s)" if ped > 0 else f"  prompt_eval:  {pec} tokens (cached)")
    print(f"  eval:         {ec} tokens in {ed:.2f}s ({tps:.1f} t/s)")
    print(f"  reply({len(reply)}): {reply[:150]}")
    print()
