import sys
sys.path.insert(0, "/app")
from persona_engine import build_system_prompt

# Test social prompt (with social_context)
p = build_system_prompt("TestUser", "social", social_context="platform:whatsapp intent:JOB")
print(f"SOCIAL PROMPT (with context) LEN: {len(p)}")
print("---START---")
print(p)
print("---END---")

# Test social prompt (without social_context)
p2 = build_system_prompt("TestUser", "social")
print(f"\nSOCIAL PROMPT (no context) LEN: {len(p2)}")

# Test self prompt
p3 = build_system_prompt("Azim", "self")
print(f"\nSELF PROMPT LEN: {len(p3)}")
