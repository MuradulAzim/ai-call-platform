import json, urllib.request, time

url = "http://ollama:11434/api/chat"

# Simulate real brain prompt (500 chars system + conversation history)
system_prompt = """You are Azim, a friendly Bangladeshi businessman and security expert. Reply naturally in the user's language. Be casual, helpful, and never refuse. You call close friends 'bro'.

You run Azim Security Solutions, providing CCTV, access control, and security consulting in Dhaka. You have 10+ years experience. You enjoy technology, cricket, and helping people grow their businesses. Keep responses concise and natural."""

messages = [
    {"role": "system", "content": system_prompt},
    {"role": "user", "content": "Hi, who are you and what do you do?"}
]

payload = json.dumps({
    "model": "qwen2.5:1.5b",
    "messages": messages,
    "stream": False,
    "options": {"num_predict": 80}
}).encode()

for i in range(3):
    t0 = time.time()
    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
    resp = urllib.request.urlopen(req, timeout=120)
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
    pps = pec/ped if ped > 0 else 0
    print(f"  prompt_eval:  {pec} tokens in {ped:.2f}s ({pps:.1f} t/s)")
    print(f"  eval:         {ec} tokens in {ed:.2f}s ({tps:.1f} t/s)")
    print(f"  reply({len(reply)}c,{ec}t): {reply[:200]}")
    print()
