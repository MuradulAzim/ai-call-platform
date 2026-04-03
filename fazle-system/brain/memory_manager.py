# ============================================================
# Fazle Brain — Redis-backed Conversation Memory Manager
# Replaces in-memory dict with persistent Redis storage
# ============================================================
import json
import logging
import os
from datetime import datetime
from typing import Optional

import redis

logger = logging.getLogger("fazle-brain")

REDIS_URL = os.getenv(
    "REDIS_URL",
    "redis://:redissecret@redis:6379/1",
)

_redis_client: Optional[redis.Redis] = None


def _get_redis() -> redis.Redis:
    """Lazy-initialize Redis connection."""
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.Redis.from_url(REDIS_URL, decode_responses=True)
    return _redis_client


def _conversation_key(session_id: str) -> str:
    return f"fazle:conv:{session_id}"


def _json_serializer(obj):
    """Handle datetime objects during JSON serialization."""
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")


def conversation_set(session_id: str, data: list[dict], ttl: int = 86400) -> None:
    """Store conversation history in Redis with a TTL (default 24h)."""
    r = _get_redis()
    serialized = json.dumps(data, default=_json_serializer)
    r.setex(_conversation_key(session_id), ttl, serialized)


def conversation_get(session_id: str) -> list[dict]:
    """Retrieve conversation history from Redis. Returns empty list if not found."""
    r = _get_redis()
    raw = r.get(_conversation_key(session_id))
    if raw is None:
        return []
    return json.loads(raw)


# ── User-scoped conversation memory (per-user isolation) ────

def _user_conv_key(platform: str, user_id: str) -> str:
    return f"fazle:user:{platform}:{user_id}:history"


def _user_replies_key(platform: str, user_id: str) -> str:
    return f"fazle:user:{platform}:{user_id}:replies"


def user_history_append(
    platform: str, user_id: str, role: str, content: str,
    max_messages: int = 20, ttl: int = 3600,
) -> None:
    """Append a message to user-scoped conversation history.
    Keeps last *max_messages* entries. TTL 1 hour default."""
    r = _get_redis()
    key = _user_conv_key(platform, user_id)
    entry = json.dumps({"role": role, "content": content, "ts": datetime.utcnow().isoformat()})
    r.rpush(key, entry)
    r.ltrim(key, -max_messages, -1)
    r.expire(key, ttl)


def user_history_get(platform: str, user_id: str, limit: int = 10) -> list[dict]:
    """Get recent conversation history for a specific user.
    Returns [{role, content}, ...] — last *limit* messages."""
    r = _get_redis()
    key = _user_conv_key(platform, user_id)
    raw_list = r.lrange(key, -limit, -1)
    result = []
    for raw in raw_list:
        try:
            entry = json.loads(raw)
            result.append({"role": entry["role"], "content": entry["content"]})
        except (json.JSONDecodeError, KeyError):
            pass
    return result


def user_replies_track(
    platform: str, user_id: str, reply: str,
    max_replies: int = 5, ttl: int = 3600,
) -> None:
    """Track recent AI replies for anti-repetition."""
    r = _get_redis()
    key = _user_replies_key(platform, user_id)
    r.rpush(key, reply)
    r.ltrim(key, -max_replies, -1)
    r.expire(key, ttl)


def user_replies_get(platform: str, user_id: str, limit: int = 5) -> list[str]:
    """Get recent AI replies for anti-repetition check."""
    r = _get_redis()
    key = _user_replies_key(platform, user_id)
    return r.lrange(key, -limit, -1) or []


# ── Owner Conversation State (STEP 6 — Conversational Control) ────

_OWNER_PENDING_KEY = "fazle:owner:pending_action"
_OWNER_PREFS_KEY = "fazle:owner:preferences"
_OWNER_INSTRUCTIONS_KEY = "fazle:owner:instructions"
_OWNER_CONV_KEY = "fazle:owner:conversation"
_OWNER_TONE_KEY = "fazle:owner:tone_profile"
_OWNER_PWD_CHALLENGE_KEY = "fazle:owner:pwd_challenge"


def owner_pending_action_set(action: dict, ttl: int = 600) -> None:
    """Store a pending action awaiting owner confirmation (10 min TTL)."""
    r = _get_redis()
    r.setex(_OWNER_PENDING_KEY, ttl, json.dumps(action, default=_json_serializer))


def owner_pending_action_get() -> Optional[dict]:
    """Retrieve pending action. Returns None if no pending action or expired."""
    r = _get_redis()
    raw = r.get(_OWNER_PENDING_KEY)
    if raw:
        return json.loads(raw)
    return None


def owner_pending_action_clear() -> None:
    """Clear the pending action after execution or rejection."""
    r = _get_redis()
    r.delete(_OWNER_PENDING_KEY)


def owner_preference_set(key: str, value: str) -> None:
    """Store an owner preference persistently."""
    r = _get_redis()
    r.hset(_OWNER_PREFS_KEY, key, value)


def owner_preference_get(key: str) -> Optional[str]:
    """Get a specific owner preference."""
    r = _get_redis()
    return r.hget(_OWNER_PREFS_KEY, key)


def owner_preferences_all() -> dict:
    """Get all owner preferences."""
    r = _get_redis()
    return r.hgetall(_OWNER_PREFS_KEY) or {}


def owner_instruction_store(instruction: str, priority: str = "medium", instruction_type: str = "permanent", ttl_seconds: int = 0) -> None:
    """Append a standing instruction from the owner with priority and type.
    Priority: high / medium / low — high overrides others.
    Type: permanent (affects long-term learning, no expiry) / temporary (expires after TTL).
    Default TTL for temporary: 3600 seconds (1 hour)."""
    if priority not in ("high", "medium", "low"):
        priority = "medium"
    if instruction_type not in ("permanent", "temporary"):
        instruction_type = "permanent"
    r = _get_redis()
    entry = json.dumps({
        "instruction": instruction,
        "priority": priority,
        "type": instruction_type,
        "ts": datetime.utcnow().isoformat(),
    })
    if instruction_type == "temporary" and ttl_seconds > 0:
        # Temporary instructions go to a separate key with TTL
        temp_key = f"{_OWNER_INSTRUCTIONS_KEY}:temp:{datetime.utcnow().timestamp()}"
        r.set(temp_key, entry, ex=ttl_seconds or 3600)
    else:
        r.rpush(_OWNER_INSTRUCTIONS_KEY, entry)
        r.ltrim(_OWNER_INSTRUCTIONS_KEY, -50, -1)


def owner_instructions_get(limit: int = 20) -> list[dict]:
    """Get recent owner instructions with priority and type.
    Returns [{instruction, priority, type}, ...] sorted: high → medium → low.
    Includes both permanent and active temporary instructions."""
    r = _get_redis()
    # Permanent instructions
    raw_list = r.lrange(_OWNER_INSTRUCTIONS_KEY, -limit, -1)
    result = []
    for raw in raw_list:
        try:
            entry = json.loads(raw)
            result.append({
                "instruction": entry["instruction"],
                "priority": entry.get("priority", "medium"),
                "type": entry.get("type", "permanent"),
            })
        except (json.JSONDecodeError, KeyError):
            pass
    # Temporary instructions (scan for active temp keys)
    try:
        for key in r.scan_iter(f"{_OWNER_INSTRUCTIONS_KEY}:temp:*"):
            raw = r.get(key)
            if raw:
                try:
                    entry = json.loads(raw)
                    entry_dict = {
                        "instruction": entry["instruction"],
                        "priority": entry.get("priority", "medium"),
                        "type": "temporary",
                    }
                    result.append(entry_dict)
                except (json.JSONDecodeError, KeyError):
                    pass
    except Exception:
        pass
    # Sort by priority: high first, then medium, then low
    order = {"high": 0, "medium": 1, "low": 2}
    result.sort(key=lambda x: order.get(x["priority"], 1))
    return result


def owner_conversation_append(role: str, content: str, max_msgs: int = 30, ttl: int = 86400) -> None:
    """Append to persistent owner conversation (24h TTL, 30 messages)."""
    r = _get_redis()
    entry = json.dumps({"role": role, "content": content, "ts": datetime.utcnow().isoformat()})
    r.rpush(_OWNER_CONV_KEY, entry)
    r.ltrim(_OWNER_CONV_KEY, -max_msgs, -1)
    r.expire(_OWNER_CONV_KEY, ttl)


def owner_conversation_get(limit: int = 20) -> list[dict]:
    """Get owner conversation history."""
    r = _get_redis()
    raw_list = r.lrange(_OWNER_CONV_KEY, -limit, -1)
    result = []
    for raw in raw_list:
        try:
            entry = json.loads(raw)
            result.append({"role": entry["role"], "content": entry["content"]})
        except (json.JSONDecodeError, KeyError):
            pass
    return result


# ── Owner Tone Profile ─────────────────────────────────────

def owner_tone_profile_update(tone: str, weight: int = 1) -> None:
    """Increment a tone counter in the owner's tone profile.
    Valid tones: aggressive, polite, direct, normal, client, escort,
    security_guard, job_seeker, old_employee, office_staff."""
    r = _get_redis()
    r.hincrby(_OWNER_TONE_KEY, tone, weight)


def owner_tone_profile_get() -> dict:
    """Get the full tone profile as {tone: count_str}."""
    r = _get_redis()
    return r.hgetall(_OWNER_TONE_KEY) or {}


def owner_tone_dominant() -> str:
    """Get the dominant tone from the owner's profile."""
    profile = owner_tone_profile_get()
    if not profile:
        return "normal"
    return max(profile, key=lambda k: int(profile[k]))


# ── Owner Password Challenge (Critical Action Safety) ──────

def owner_pwd_challenge_set(action_data: dict, ttl: int = 120) -> None:
    """Store a password-protected action awaiting password confirmation (2 min TTL)."""
    r = _get_redis()
    r.setex(_OWNER_PWD_CHALLENGE_KEY, ttl, json.dumps(action_data, default=_json_serializer))


def owner_pwd_challenge_get() -> Optional[dict]:
    """Get the current password-protected pending action."""
    r = _get_redis()
    raw = r.get(_OWNER_PWD_CHALLENGE_KEY)
    if raw:
        return json.loads(raw)
    return None


def owner_pwd_challenge_clear() -> None:
    """Clear the password challenge after success or timeout."""
    r = _get_redis()
    r.delete(_OWNER_PWD_CHALLENGE_KEY)


# ── Azim Identity Profile (STEP 1 — Identity Grounding) ────

_AZIM_PROFILE_KEY = "fazle:azim:profile"
_AZIM_INTERVIEW_KEY = "fazle:azim:interview:pending"
_AZIM_INTERVIEW_ANSWERED_KEY = "fazle:azim:interview:answered"


def azim_profile_set(field: str, value: str) -> None:
    """Set a single field in Azim's identity profile (persistent, no TTL)."""
    r = _get_redis()
    r.hset(_AZIM_PROFILE_KEY, field, value)


def azim_profile_get(field: str) -> Optional[str]:
    """Get a single field from Azim's identity profile."""
    r = _get_redis()
    return r.hget(_AZIM_PROFILE_KEY, field)


def azim_profile_all() -> dict:
    """Get the full Azim identity profile as a dict."""
    r = _get_redis()
    return r.hgetall(_AZIM_PROFILE_KEY) or {}


def azim_profile_update(data: dict) -> None:
    """Bulk update Azim's identity profile with multiple fields."""
    if not data:
        return
    r = _get_redis()
    r.hset(_AZIM_PROFILE_KEY, mapping={k: str(v) for k, v in data.items()})


def interview_question_push(question: str, category: str = "general") -> None:
    """Queue a question for the owner interview system."""
    r = _get_redis()
    entry = json.dumps({"question": question, "category": category, "ts": datetime.utcnow().isoformat()})
    # Avoid duplicate questions
    existing = r.lrange(_AZIM_INTERVIEW_KEY, 0, -1)
    for raw in existing:
        try:
            if json.loads(raw).get("question") == question:
                return
        except (json.JSONDecodeError, KeyError):
            pass
    r.rpush(_AZIM_INTERVIEW_KEY, entry)
    r.ltrim(_AZIM_INTERVIEW_KEY, -20, -1)  # max 20 pending


def interview_question_pop() -> Optional[dict]:
    """Pop the next pending interview question."""
    r = _get_redis()
    raw = r.lpop(_AZIM_INTERVIEW_KEY)
    if raw:
        return json.loads(raw)
    return None


def interview_questions_pending() -> list[dict]:
    """Get all pending interview questions without removing them."""
    r = _get_redis()
    raw_list = r.lrange(_AZIM_INTERVIEW_KEY, 0, -1)
    result = []
    for raw in raw_list:
        try:
            result.append(json.loads(raw))
        except (json.JSONDecodeError, KeyError):
            pass
    return result


def interview_answer_store(question: str, answer: str) -> None:
    """Store an answered interview question for history."""
    r = _get_redis()
    entry = json.dumps({"question": question, "answer": answer, "ts": datetime.utcnow().isoformat()})
    r.rpush(_AZIM_INTERVIEW_ANSWERED_KEY, entry)
    r.ltrim(_AZIM_INTERVIEW_ANSWERED_KEY, -100, -1)


# ── System Governor v2 State ────────────────────────────────

_GOV_PREFIX = "fazle:governor:"
_GOV_QUALITY_SCORES_KEY = f"{_GOV_PREFIX}quality_scores"
_GOV_IDENTITY_SCORES_KEY = f"{_GOV_PREFIX}identity_scores"
_GOV_SAFE_MODE_KEY = f"{_GOV_PREFIX}safe_mode"
_GOV_ERROR_LOG_KEY = f"{_GOV_PREFIX}errors"
_GOV_DRIFT_ALERTS_KEY = f"{_GOV_PREFIX}drift_alerts"
_GOV_FEEDBACK_KEY = f"{_GOV_PREFIX}feedback"
_GOV_PATCH_BASELINES_KEY = f"{_GOV_PREFIX}patch_baselines"


def governor_quality_score_push(score: float, metadata: dict = None) -> None:
    """Record a response quality score (0-1). Keeps last 100."""
    r = _get_redis()
    entry = json.dumps({"score": round(score, 3), "meta": metadata or {}, "ts": datetime.utcnow().isoformat()})
    r.rpush(_GOV_QUALITY_SCORES_KEY, entry)
    r.ltrim(_GOV_QUALITY_SCORES_KEY, -100, -1)


def governor_quality_scores_get(count: int = 100) -> list[dict]:
    r = _get_redis()
    return [json.loads(x) for x in r.lrange(_GOV_QUALITY_SCORES_KEY, -count, -1)]


def governor_identity_score_push(score: float, details: str = "") -> None:
    """Record identity alignment score (0-1). Keeps last 100."""
    r = _get_redis()
    entry = json.dumps({"score": round(score, 3), "details": details[:200], "ts": datetime.utcnow().isoformat()})
    r.rpush(_GOV_IDENTITY_SCORES_KEY, entry)
    r.ltrim(_GOV_IDENTITY_SCORES_KEY, -100, -1)


def governor_identity_scores_get(count: int = 100) -> list[dict]:
    r = _get_redis()
    return [json.loads(x) for x in r.lrange(_GOV_IDENTITY_SCORES_KEY, -count, -1)]


def governor_safe_mode_get() -> bool:
    """Check if governor safe mode is active."""
    return _get_redis().get(_GOV_SAFE_MODE_KEY) == "1"


def governor_safe_mode_set(active: bool) -> None:
    _get_redis().set(_GOV_SAFE_MODE_KEY, "1" if active else "0")


def governor_error_log(error_type: str, details: str) -> None:
    """Log a governor error. Keeps last 200."""
    r = _get_redis()
    entry = json.dumps({"type": error_type, "details": details[:300], "ts": datetime.utcnow().isoformat()})
    r.rpush(_GOV_ERROR_LOG_KEY, entry)
    r.ltrim(_GOV_ERROR_LOG_KEY, -200, -1)


def governor_errors_get(count: int = 50) -> list[dict]:
    r = _get_redis()
    return [json.loads(x) for x in r.lrange(_GOV_ERROR_LOG_KEY, -count, -1)]


def governor_drift_alert(alert: str) -> None:
    """Store a drift alert. Keeps last 50."""
    r = _get_redis()
    entry = json.dumps({"alert": alert[:300], "ts": datetime.utcnow().isoformat()})
    r.rpush(_GOV_DRIFT_ALERTS_KEY, entry)
    r.ltrim(_GOV_DRIFT_ALERTS_KEY, -50, -1)


def governor_drift_alerts_get(count: int = 20) -> list[dict]:
    r = _get_redis()
    return [json.loads(x) for x in r.lrange(_GOV_DRIFT_ALERTS_KEY, -count, -1)]


def governor_feedback_store(feedback: str, score: float = 0.0) -> None:
    """Store owner feedback response."""
    r = _get_redis()
    entry = json.dumps({"feedback": feedback[:500], "score": score, "ts": datetime.utcnow().isoformat()})
    r.rpush(_GOV_FEEDBACK_KEY, entry)
    r.ltrim(_GOV_FEEDBACK_KEY, -50, -1)


def governor_feedback_get(count: int = 20) -> list[dict]:
    r = _get_redis()
    return [json.loads(x) for x in r.lrange(_GOV_FEEDBACK_KEY, -count, -1)]


def governor_patch_baseline_set(patch_id: str, avg_quality: float) -> None:
    """Store quality baseline before a patch is applied."""
    r = _get_redis()
    r.hset(_GOV_PATCH_BASELINES_KEY, patch_id, json.dumps({
        "avg_quality": round(avg_quality, 3), "ts": datetime.utcnow().isoformat(),
    }))


def governor_patch_baseline_get(patch_id: str) -> Optional[dict]:
    r = _get_redis()
    raw = r.hget(_GOV_PATCH_BASELINES_KEY, patch_id)
    return json.loads(raw) if raw else None


# ── Intelligence Tuning Layer — Usage Tracking & Owner Priority ──

_INTEL_PREFIX = "fazle:intel:"
_INTEL_USAGE_KEY = f"{_INTEL_PREFIX}usage"
_INTEL_USAGE_DAILY_KEY = f"{_INTEL_PREFIX}usage_daily"
_INTEL_OWNER_PRIORITY_KEY = f"{_INTEL_PREFIX}owner_priority"


def intel_usage_track(model: str, prompt_tokens: int = 0, completion_tokens: int = 0, route: str = "full") -> None:
    """Track LLM usage per model. Keeps daily counters + rolling log."""
    r = _get_redis()
    today = datetime.utcnow().strftime("%Y-%m-%d")
    daily_key = f"{_INTEL_USAGE_DAILY_KEY}:{today}"
    # Increment daily counters per model
    r.hincrby(daily_key, f"{model}:calls", 1)
    r.hincrby(daily_key, f"{model}:prompt_tokens", prompt_tokens)
    r.hincrby(daily_key, f"{model}:completion_tokens", completion_tokens)
    r.hincrby(daily_key, f"route:{route}", 1)
    r.expire(daily_key, 604800)  # 7 day TTL
    # Rolling log (last 200 entries)
    entry = json.dumps({
        "model": model, "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens, "route": route,
        "ts": datetime.utcnow().isoformat(),
    })
    r.rpush(_INTEL_USAGE_KEY, entry)
    r.ltrim(_INTEL_USAGE_KEY, -200, -1)


def intel_usage_stats(days: int = 1) -> dict:
    """Get usage stats for last N days."""
    r = _get_redis()
    result = {}
    for d in range(days):
        day = (datetime.utcnow() - __import__("datetime").timedelta(days=d)).strftime("%Y-%m-%d")
        daily_key = f"{_INTEL_USAGE_DAILY_KEY}:{day}"
        raw = r.hgetall(daily_key)
        if raw:
            result[day] = raw
    return result


def intel_owner_priority_set(active: bool) -> None:
    """Set/clear owner priority flag."""
    r = _get_redis()
    if active:
        r.setex(_INTEL_OWNER_PRIORITY_KEY, 30, "1")  # auto-expire in 30s
    else:
        r.delete(_INTEL_OWNER_PRIORITY_KEY)


def intel_owner_priority_active() -> bool:
    """Check if owner has an active priority request."""
    r = _get_redis()
    return r.exists(_INTEL_OWNER_PRIORITY_KEY) == 1


# ── Strategic Planning Agent — Report Storage ────────────────

_STRATEGY_PREFIX = "fazle:strategy:"
_STRATEGY_REPORTS_KEY = f"{_STRATEGY_PREFIX}reports"
_STRATEGY_LAST_RUN_KEY = f"{_STRATEGY_PREFIX}last_run"


def strategy_report_store(report: dict) -> None:
    """Store a strategic planning report. Keeps last 30 reports."""
    r = _get_redis()
    entry = json.dumps({**report, "ts": datetime.utcnow().isoformat()})
    r.rpush(_STRATEGY_REPORTS_KEY, entry)
    r.ltrim(_STRATEGY_REPORTS_KEY, -30, -1)
    r.set(_STRATEGY_LAST_RUN_KEY, datetime.utcnow().isoformat())


def strategy_report_get(count: int = 1) -> list[dict]:
    """Get latest N strategic reports."""
    r = _get_redis()
    raw_list = r.lrange(_STRATEGY_REPORTS_KEY, -count, -1)
    return [json.loads(x) for x in raw_list] if raw_list else []


def strategy_last_run() -> Optional[str]:
    """Get timestamp of last strategic planning run."""
    r = _get_redis()
    return r.get(_STRATEGY_LAST_RUN_KEY)


# ── Contact Memory Enrichment ───────────────────────────────

_CONTACT_MEM_PREFIX = "fazle:contact:"


def contact_interaction_track(platform: str, phone: str, message: str, direction: str = "incoming") -> None:
    """Track a contact interaction in Redis for enrichment analytics.
    Stores recent messages per contact to enable behavior analysis."""
    r = _get_redis()
    key = f"{_CONTACT_MEM_PREFIX}{platform}:{phone}:interactions"
    entry = json.dumps({
        "direction": direction,
        "message": message[:500],
        "ts": datetime.utcnow().isoformat(),
    })
    r.rpush(key, entry)
    r.ltrim(key, -50, -1)  # Keep last 50 interactions
    r.expire(key, 604800)  # 7 day TTL


def contact_interactions_get(platform: str, phone: str, limit: int = 20) -> list[dict]:
    """Get recent interactions for a specific contact."""
    r = _get_redis()
    key = f"{_CONTACT_MEM_PREFIX}{platform}:{phone}:interactions"
    raw_list = r.lrange(key, -limit, -1)
    result = []
    for raw in raw_list:
        try:
            result.append(json.loads(raw))
        except (json.JSONDecodeError, KeyError):
            pass
    return result


def contact_topic_track(platform: str, phone: str, topic: str) -> None:
    """Track what topics a contact is interested in (for personalization)."""
    r = _get_redis()
    key = f"{_CONTACT_MEM_PREFIX}{platform}:{phone}:topics"
    r.hincrby(key, topic, 1)
    r.expire(key, 2592000)  # 30 day TTL


def contact_topics_get(platform: str, phone: str) -> dict:
    """Get topic frequency map for a contact."""
    r = _get_redis()
    key = f"{_CONTACT_MEM_PREFIX}{platform}:{phone}:topics"
    return r.hgetall(key) or {}


def contact_note_set(platform: str, phone: str, note: str) -> None:
    """Store a note about a contact in Redis (for quick access, mirrors DB)."""
    r = _get_redis()
    key = f"{_CONTACT_MEM_PREFIX}{platform}:{phone}:note"
    r.set(key, note, ex=2592000)  # 30 day TTL


def contact_note_get(platform: str, phone: str) -> Optional[str]:
    """Get a stored note about a contact."""
    r = _get_redis()
    key = f"{_CONTACT_MEM_PREFIX}{platform}:{phone}:note"
    return r.get(key)
