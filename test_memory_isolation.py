"""Test STEP 5: Memory Isolation + Conversation Intelligence"""
import httpx
import json
import time

BRAIN = "http://127.0.0.1:8200"

print("=" * 60)
print("TEST 1: Same user, two messages — should get conversation continuity")
print("=" * 60)

# Simulate WhatsApp user "0171234567" sending two messages
conv_id = "social-whatsapp-0171234567"

r1 = httpx.post(f"{BRAIN}/chat", json={
    "message": "কাজ কি?",
    "user": "Test User",
    "relationship": "social",
    "conversation_id": conv_id,
    "context": "Platform: whatsapp. Reply naturally.",
}, timeout=60)
print(f"MSG 1 status: {r1.status_code}")
reply1 = r1.json().get("reply", "")
print(f"MSG 1 reply: {reply1[:200]}")
print()

time.sleep(2)

r2 = httpx.post(f"{BRAIN}/chat", json={
    "message": "বেতন কত?",
    "user": "Test User",
    "relationship": "social",
    "conversation_id": conv_id,
    "context": "Platform: whatsapp. Reply naturally.",
}, timeout=60)
print(f"MSG 2 status: {r2.status_code}")
reply2 = r2.json().get("reply", "")
print(f"MSG 2 reply: {reply2[:200]}")
print()

print("=" * 60)
print("TEST 2: Same question twice — should get DIFFERENT wording")
print("=" * 60)

conv_id2 = "social-whatsapp-0179999999"

r3 = httpx.post(f"{BRAIN}/chat", json={
    "message": "কাজ কি?",
    "user": "Another User",
    "relationship": "social",
    "conversation_id": conv_id2,
    "context": "Platform: whatsapp. Reply naturally.",
}, timeout=60)
reply3 = r3.json().get("reply", "")
print(f"User2 MSG 1: {reply3[:200]}")

time.sleep(2)

r4 = httpx.post(f"{BRAIN}/chat", json={
    "message": "কাজ কি?",
    "user": "Another User",
    "relationship": "social",
    "conversation_id": conv_id2,
    "context": "Platform: whatsapp. Reply naturally.",
}, timeout=60)
reply4 = r4.json().get("reply", "")
print(f"User2 MSG 2 (SAME question): {reply4[:200]}")
print()

same = reply3.strip() == reply4.strip()
print(f"Replies identical? {same}")
if same:
    print("WARNING: Anti-repetition may not be working")
else:
    print("OK: Replies are different (anti-repetition working)")

print()
print("=" * 60)
print("TEST 3: Different user — NO memory leakage")
print("=" * 60)

conv_id3 = "social-whatsapp-0178888888"
r5 = httpx.post(f"{BRAIN}/chat", json={
    "message": "আমি কি আগে কথা বলেছি?",
    "user": "Brand New User",
    "relationship": "social",
    "conversation_id": conv_id3,
    "context": "Platform: whatsapp. Reply naturally.",
}, timeout=60)
reply5 = r5.json().get("reply", "")
print(f"New user reply: {reply5[:200]}")
print()
print("(Should NOT reference other users' conversations)")
print()
print("ALL TESTS COMPLETE")
