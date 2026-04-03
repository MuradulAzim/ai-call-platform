# ============================================================
# Fazle Autonomy Engine — Autonomous Decision Engine
# Goal decomposition, proactive monitoring, opportunity detection,
# self-improvement, suggestion generation, and learning loop
# ============================================================
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings
from prometheus_fastapi_instrumentator import Instrumentator
import httpx
import json
import logging
import uuid
import asyncio
import redis
from typing import Optional
from datetime import datetime, timedelta
from enum import Enum
from contextlib import asynccontextmanager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("fazle-autonomy-engine")


class Settings(BaseSettings):
    brain_url: str = "http://fazle-brain:8200"
    memory_url: str = "http://fazle-memory:8300"
    tools_url: str = "http://fazle-web-intelligence:8500"
    task_url: str = "http://fazle-task-engine:8400"
    tool_engine_url: str = "http://fazle-tool-engine:9200"
    knowledge_graph_url: str = "http://fazle-knowledge-graph:9300"
    llm_gateway_url: str = "http://fazle-llm-gateway:8800"
    learning_engine_url: str = "http://fazle-learning-engine:8900"
    redis_url: str = "redis://:UuhN4ehSgOTbeDlLltEnJ8R2tYQa8F@redis:6379/6"
    brain_redis_url: str = "redis://:UuhN4ehSgOTbeDlLltEnJ8R2tYQa8F@redis:6379/1"
    max_plan_steps: int = 10
    max_retries: int = 3
    reflection_enabled: bool = True
    # Autonomous monitoring settings
    monitor_interval_seconds: int = 300  # 5 minutes
    monitor_enabled: bool = True
    suggestion_cooldown_seconds: int = 600  # 10 min between suggestions per user
    auto_improve_enabled: bool = True
    # Intelligence enhancement settings
    confidence_auto_threshold: float = 0.8    # >0.8 auto-execute
    confidence_ask_threshold: float = 0.5     # 0.5-0.8 ask owner, <0.5 skip
    max_followups_per_user_per_day: int = 2   # Smart follow-up control
    drift_max_deviation: float = 0.3          # Max persona drift allowed (0-1)

    class Config:
        env_prefix = "AUTONOMY_"


settings = Settings()

# ── Redis clients ────────────────────────────────────────────
_redis_autonomy: Optional[redis.Redis] = None
_redis_brain: Optional[redis.Redis] = None


def _get_redis() -> redis.Redis:
    global _redis_autonomy
    if _redis_autonomy is None:
        _redis_autonomy = redis.Redis.from_url(settings.redis_url, decode_responses=True)
    return _redis_autonomy


def _get_brain_redis() -> redis.Redis:
    global _redis_brain
    if _redis_brain is None:
        _redis_brain = redis.Redis.from_url(settings.brain_redis_url, decode_responses=True)
    return _redis_brain


# ── Background monitor task ──────────────────────────────────
_monitor_task: Optional[asyncio.Task] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start background monitor on startup, cancel on shutdown."""
    global _monitor_task
    if settings.monitor_enabled:
        _monitor_task = asyncio.create_task(_conversation_monitor_loop())
        logger.info("Autonomous conversation monitor started")
    yield
    if _monitor_task:
        _monitor_task.cancel()
        logger.info("Monitor stopped")


app = FastAPI(title="Fazle Autonomy Engine", version="2.0.0", lifespan=lifespan)
Instrumentator().instrument(app).expose(app, endpoint="/metrics")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://fazle.iamazim.com", "https://iamazim.com"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Models ───────────────────────────────────────────────────

class PlanStatus(str, Enum):
    pending = "pending"
    planning = "planning"
    executing = "executing"
    reflecting = "reflecting"
    completed = "completed"
    failed = "failed"
    paused = "paused"


class PlanStep(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    action: str
    description: str
    tool: Optional[str] = None
    depends_on: list[str] = Field(default_factory=list)
    status: str = "pending"
    result: Optional[str] = None
    error: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None


class AutonomyPlan(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    goal: str
    context: Optional[str] = None
    steps: list[PlanStep] = Field(default_factory=list)
    status: PlanStatus = PlanStatus.pending
    reflection: Optional[str] = None
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    updated_at: Optional[str] = None
    completed_at: Optional[str] = None
    retry_count: int = 0
    user_id: Optional[str] = None


class PlanRequest(BaseModel):
    goal: str
    context: Optional[str] = None
    max_steps: Optional[int] = None
    auto_execute: bool = False
    user_id: Optional[str] = None


class ExecuteRequest(BaseModel):
    plan_id: str
    step_ids: Optional[list[str]] = None


class PlanResponse(BaseModel):
    plan: AutonomyPlan
    message: str


# ── In-memory plan store ─────────────────────────────────────
_plans: dict[str, AutonomyPlan] = {}

# ── Autonomous Decision Engine — Data Models ────────────────

class SuggestionType(str, Enum):
    follow_up = "follow_up"          # High-interest user needs follow-up
    confused_user = "confused_user"    # User seems confused, needs help
    missed_conversion = "missed_conversion"  # Missed business opportunity
    reply_improvement = "reply_improvement"  # AI reply could be better
    tone_adjustment = "tone_adjustment"      # Tone mismatch detected
    repeated_question = "repeated_question"  # Same question asked repeatedly
    negative_reaction = "negative_reaction"  # User showed frustration
    system_issue = "system_issue"            # Failed replies or errors


class ExecutionLevel(str, Enum):
    low = "low"        # Auto-execute immediately (backup + apply)
    medium = "medium"  # Ask once; auto-execute similar types after first approval
    high = "high"      # Always require owner confirmation + sandbox review


# Default execution rules — maps suggestion types to safety levels
_execution_rules: dict[SuggestionType, ExecutionLevel] = {
    SuggestionType.reply_improvement: ExecutionLevel.low,
    SuggestionType.tone_adjustment: ExecutionLevel.low,
    SuggestionType.follow_up: ExecutionLevel.medium,
    SuggestionType.confused_user: ExecutionLevel.medium,
    SuggestionType.repeated_question: ExecutionLevel.medium,
    SuggestionType.missed_conversion: ExecutionLevel.high,
    SuggestionType.negative_reaction: ExecutionLevel.high,
    SuggestionType.system_issue: ExecutionLevel.high,
}


class Suggestion(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:12])
    type: SuggestionType
    user_id: str = ""
    platform: str = ""
    message_bn: str  # Bangla suggestion for owner
    message_en: str  # English summary
    confidence: float = 0.0  # 0.0 - 1.0
    context: dict = Field(default_factory=dict)
    auto_actionable: bool = False  # Can be auto-executed safely
    proposed_action: Optional[str] = None
    status: str = "pending"  # pending / sent_to_owner / approved / rejected / auto_applied
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


class LearningEntry(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:12])
    event_type: str  # improvement_applied / suggestion_approved / suggestion_rejected / reply_failed
    details: dict = Field(default_factory=dict)
    outcome: str = ""  # positive / negative / neutral
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


class ExecutionRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:12])
    suggestion_id: str
    suggestion_type: str
    execution_level: str
    action: str
    status: str = "pending"  # pending / executed / failed / rolled_back
    backup_id: Optional[str] = None
    result: Optional[str] = None
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


class SandboxChange(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:12])
    suggestion_id: str = ""
    change_type: str  # tone_update / reply_improvement / follow_up / etc.
    description: str
    current_state: Optional[str] = None
    proposed_state: str
    diff_summary: str = ""
    status: str = "pending"  # pending / approved / rejected / applied / failed
    backup_id: Optional[str] = None
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


# ── In-memory stores ────────────────────────────────────────
_suggestions: list[Suggestion] = []
_learning_log: list[LearningEntry] = []
_execution_log: list[ExecutionRecord] = []
_sandbox_changes: list[SandboxChange] = []

# Redis keys for autonomy state
_AUTONOMY_PREFIX = "fazle:autonomy:"
_LAST_SCAN_KEY = f"{_AUTONOMY_PREFIX}last_scan"
_SUGGESTION_COOLDOWN_PREFIX = f"{_AUTONOMY_PREFIX}cooldown:"
_IMPROVEMENTS_KEY = f"{_AUTONOMY_PREFIX}improvements"
_LEARNING_KEY = f"{_AUTONOMY_PREFIX}learning"
_DAILY_STATS_KEY = f"{_AUTONOMY_PREFIX}daily_stats"
_EXECUTION_RULES_KEY = f"{_AUTONOMY_PREFIX}execution_rules"
_EXECUTION_LOG_KEY = f"{_AUTONOMY_PREFIX}execution_log"
_BACKUP_PREFIX = f"{_AUTONOMY_PREFIX}backup:"
_SANDBOX_PREFIX = f"{_AUTONOMY_PREFIX}sandbox:"
_MEDIUM_APPROVED_KEY = f"{_AUTONOMY_PREFIX}medium_approved_types"
_EXEC_MEMORY_KEY = f"{_AUTONOMY_PREFIX}exec_memory"
_BASELINE_PERSONA_KEY = f"{_AUTONOMY_PREFIX}baseline_persona"
_USER_PRIORITY_PREFIX = f"{_AUTONOMY_PREFIX}user_priority:"
_FOLLOWUP_COUNT_PREFIX = f"{_AUTONOMY_PREFIX}followup_count:"
_PENDING_RULE_CHANGES_KEY = f"{_AUTONOMY_PREFIX}pending_rule_changes"


# ── INTELLIGENCE ENHANCEMENT FUNCTIONS ───────────────────────

async def _initialize_baseline_persona():
    """STEP 2 (Drift Control): Initialize baseline persona if not already set."""
    r = _get_redis()
    if r.exists(_BASELINE_PERSONA_KEY):
        logger.info("Baseline persona already initialized")
        return
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f"{settings.brain_url}/persona/current")
            if resp.status_code == 200:
                persona_data = resp.json()
                baseline = json.dumps({
                    "tone": persona_data.get("tone", "friendly, professional, Bangla-first"),
                    "style": persona_data.get("style", "helpful assistant"),
                    "key_phrases": persona_data.get("key_phrases", []),
                    "personality": persona_data.get("personality", "Fazle — Azim's AI"),
                }, ensure_ascii=False)
                r.set(_BASELINE_PERSONA_KEY, baseline)
                logger.info("Baseline persona initialized from brain")
                return
    except Exception as e:
        logger.debug(f"Could not fetch persona from brain: {e}")
    default_baseline = json.dumps({
        "tone": "friendly, professional, warm, Bangla-first",
        "style": "helpful, knowledgeable, owner's trusted AI",
        "key_phrases": ["আমি আজিমের AI", "কিভাবে সাহায্য করতে পারি"],
        "personality": "Fazle — Azim's loyal AI assistant, speaks Bangla naturally",
    }, ensure_ascii=False)
    r.set(_BASELINE_PERSONA_KEY, default_baseline)
    logger.info("Baseline persona initialized with defaults")


def _calculate_confidence(suggestion: Suggestion) -> float:
    """STEP 1 (Confidence Engine): Calculate confidence based on past success,
    user history, and action type."""
    base_confidence = suggestion.confidence
    r = _get_redis()
    # Factor 1: Past success rate for this action type from exec memory
    exec_data = r.lrange(_EXEC_MEMORY_KEY, -100, -1)
    type_successes = 0
    type_total = 0
    for raw in exec_data:
        try:
            entry = json.loads(raw)
            if entry.get("action_type") == suggestion.type.value:
                type_total += 1
                if entry.get("success_score", 0) >= 0.5:
                    type_successes += 1
        except json.JSONDecodeError:
            pass
    success_rate = (type_successes / type_total) if type_total > 0 else 0.5
    # Factor 2: User priority adjustment
    priority = _get_user_priority(suggestion.user_id)
    priority_bonus = {"high": 0.1, "medium": 0.0, "low": -0.1}.get(priority, 0.0)
    # Weighted: 50% LLM analysis, 30% history, 20% priority
    calculated = (base_confidence * 0.5) + (success_rate * 0.3) + ((0.5 + priority_bonus) * 0.2)
    return min(max(calculated, 0.0), 1.0)


async def _check_drift(proposed_action: str) -> tuple[bool, float]:
    """STEP 2 (Drift Control): Compare proposed action against baseline persona.
    Returns (is_safe, deviation_score)."""
    r = _get_redis()
    baseline = r.get(_BASELINE_PERSONA_KEY)
    if not baseline:
        return True, 0.0
    try:
        drift_prompt = f"""Compare this proposed AI action against the original persona baseline.

Baseline Persona:
{baseline}

Proposed Action:
{proposed_action}

Rate the deviation from 0.0 (identical to persona) to 1.0 (completely different):
- 0.0-0.2: Same tone, style, within character
- 0.3-0.5: Slight deviation but acceptable
- 0.6-0.8: Significant deviation from persona
- 0.9-1.0: Completely out of character

Return ONLY a JSON: {{"deviation": 0.0, "reason": "brief explanation"}}"""
        raw = await query_llm(drift_prompt, system="You are a persona consistency checker. Be strict.")
        raw = raw.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        data = json.loads(raw)
        deviation = float(data.get("deviation", 0.0))
        is_safe = deviation <= settings.drift_max_deviation
        if not is_safe:
            logger.warning(f"Drift detected: {deviation:.2f} — {data.get('reason', '')}")
        return is_safe, deviation
    except Exception as e:
        logger.debug(f"Drift check failed: {e}, allowing action")
        return True, 0.0


def _record_execution_memory(action_type: str, action: str, success: bool, success_score: float, user_response: str = ""):
    """STEP 3 (Execution Memory): Record action result for future learning."""
    r = _get_redis()
    entry = {
        "action_type": action_type,
        "action": action[:200],
        "executed": success,
        "success_score": success_score,
        "user_response": user_response[:200],
        "ts": datetime.utcnow().isoformat(),
    }
    r.rpush(_EXEC_MEMORY_KEY, json.dumps(entry))
    r.ltrim(_EXEC_MEMORY_KEY, -500, -1)


def _get_user_priority(user_id: str) -> str:
    """STEP 4 (Action Priority): Get user priority level."""
    r = _get_redis()
    override = r.get(f"{_USER_PRIORITY_PREFIX}{user_id}")
    if override and override in ("high", "medium", "low"):
        return override
    br = _get_brain_redis()
    conv_key = f"fazle:conv:social-whatsapp-{user_id}"
    raw = br.get(conv_key)
    if not raw:
        return "low"
    try:
        conv = json.loads(raw)
        msg_count = len(conv)
        if msg_count >= 20:
            return "high"
        elif msg_count >= 5:
            return "medium"
        return "low"
    except (json.JSONDecodeError, Exception):
        return "low"


def _check_followup_limit(user_id: str) -> bool:
    """STEP 6 (Follow-up Control): Check if user is under daily follow-up limit."""
    r = _get_redis()
    today = datetime.utcnow().strftime("%Y-%m-%d")
    key = f"{_FOLLOWUP_COUNT_PREFIX}{user_id}:{today}"
    count = r.get(key)
    return int(count or 0) < settings.max_followups_per_user_per_day


def _increment_followup_count(user_id: str):
    """STEP 6 (Follow-up Control): Increment daily follow-up counter."""
    r = _get_redis()
    today = datetime.utcnow().strftime("%Y-%m-%d")
    key = f"{_FOLLOWUP_COUNT_PREFIX}{user_id}:{today}"
    r.incr(key)
    r.expire(key, 86400)


async def _check_and_propose_rule_changes():
    """STEP 5 (Adaptive Rules): Analyze exec memory and propose threshold changes."""
    r = _get_redis()
    exec_data = r.lrange(_EXEC_MEMORY_KEY, -200, -1)
    if len(exec_data) < 20:
        return
    type_stats: dict[str, dict] = {}
    for raw in exec_data:
        try:
            entry = json.loads(raw)
            atype = entry.get("action_type", "unknown")
            if atype not in type_stats:
                type_stats[atype] = {"total": 0, "success": 0, "fail": 0}
            type_stats[atype]["total"] += 1
            if entry.get("success_score", 0) >= 0.6:
                type_stats[atype]["success"] += 1
            else:
                type_stats[atype]["fail"] += 1
        except json.JSONDecodeError:
            pass
    valid_types = [s.value for s in SuggestionType]
    for atype, stats in type_stats.items():
        if stats["total"] < 5 or atype not in valid_types:
            continue
        success_rate = stats["success"] / stats["total"]
        current_level = _get_execution_level(SuggestionType(atype)).value
        suggested_level = None
        if success_rate >= 0.9 and current_level in ("medium", "high"):
            suggested_level = "low" if current_level == "medium" else "medium"
        elif success_rate < 0.5 and current_level == "low":
            suggested_level = "medium"
        if suggested_level:
            change_id = str(uuid.uuid4())[:8]
            r.hset(_PENDING_RULE_CHANGES_KEY, change_id, json.dumps({
                "id": change_id,
                "action_type": atype,
                "current_level": current_level,
                "suggested_level": suggested_level,
                "success_rate": round(success_rate, 2),
                "total_samples": stats["total"],
                "reason": f"Success rate {success_rate:.0%} over {stats['total']} executions",
                "created_at": datetime.utcnow().isoformat(),
            }))
    logger.info("Adaptive rule analysis completed")


# ── STEP 1: Context Monitor ─────────────────────────────────

async def _conversation_monitor_loop():
    """Background loop monitoring conversations for issues and opportunities."""
    logger.info("Context monitor loop starting...")
    await asyncio.sleep(30)  # Wait for other services to be ready
    # STEP 2: Initialize baseline persona for drift control
    await _initialize_baseline_persona()

    while True:
        try:
            await _run_monitoring_cycle()
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Monitor cycle error: {e}")
        # Governor v2 cycle
        try:
            await _governor_run_cycle()
        except Exception as e:
            logger.error(f"Governor cycle error: {e}")
        # Strategic Planning Agent — runs once every 24h
        try:
            await _strategic_planning_cycle()
        except Exception as e:
            logger.error(f"Strategic planning cycle error: {e}")
        await asyncio.sleep(settings.monitor_interval_seconds)


async def _run_monitoring_cycle():
    """Single monitoring cycle: scan recent conversations, detect issues, generate suggestions."""
    r = _get_redis()
    br = _get_brain_redis()

    # Get recent conversation keys from brain's Redis
    conv_keys = br.keys("fazle:conv:social-*")
    if not conv_keys:
        return

    now = datetime.utcnow()
    cycle_suggestions: list[Suggestion] = []

    for key in conv_keys[-30:]:  # Process last 30 active conversations
        try:
            raw = br.get(key)
            if not raw:
                continue
            conv = json.loads(raw)
            if not conv or len(conv) < 2:
                continue

            # Extract user identifier from key
            # Key format: fazle:conv:social-whatsapp-<user_id>
            parts = key.split("-", 2)
            platform = parts[1] if len(parts) > 1 else "unknown"
            user_id = parts[2] if len(parts) > 2 else "unknown"

            # Skip if we recently generated a suggestion for this user
            cooldown_key = f"{_SUGGESTION_COOLDOWN_PREFIX}{user_id}"
            if r.exists(cooldown_key):
                continue

            # Analyze the conversation
            suggestions = await _analyze_conversation(conv, user_id, platform)
            cycle_suggestions.extend(suggestions)

        except Exception as e:
            logger.debug(f"Error analyzing conversation {key}: {e}")

    # Process generated suggestions using execution levels + intelligence enhancements
    for suggestion in cycle_suggestions:
        _suggestions.append(suggestion)
        # Set cooldown for this user
        r.setex(
            f"{_SUGGESTION_COOLDOWN_PREFIX}{suggestion.user_id}",
            settings.suggestion_cooldown_seconds,
            "1",
        )

        # STEP 1: Confidence Engine — calculate real confidence
        calculated_confidence = _calculate_confidence(suggestion)
        suggestion.confidence = calculated_confidence

        # STEP 6: Smart Follow-up Control
        if suggestion.type == SuggestionType.follow_up:
            if not _check_followup_limit(suggestion.user_id):
                suggestion.status = "skipped_followup_limit"
                _log_learning("followup_limit_reached", {
                    "user_id": suggestion.user_id,
                    "suggestion_id": suggestion.id,
                }, "neutral")
                continue

        # STEP 1: Skip if confidence too low
        if calculated_confidence < settings.confidence_ask_threshold:
            suggestion.status = "skipped_low_confidence"
            _log_learning("skipped_low_confidence", {
                "suggestion_id": suggestion.id,
                "type": suggestion.type.value,
                "confidence": calculated_confidence,
            }, "neutral")
            continue

        # Determine execution level for this suggestion type
        level = _get_execution_level(suggestion.type)
        can_auto = (
            calculated_confidence >= settings.confidence_auto_threshold
            and settings.auto_improve_enabled
        )

        if level == ExecutionLevel.low and can_auto:
            # LOW + high confidence: Auto-execute with backup
            await _auto_execute_action(suggestion)
        elif level == ExecutionLevel.medium:
            # MEDIUM: Check confidence + prior approval
            if can_auto and _is_medium_auto_approved(suggestion.type.value):
                await _auto_execute_action(suggestion)
            else:
                await _send_suggestion_to_owner(suggestion)
        else:
            # HIGH: Always create sandbox + require owner confirmation
            sandbox = await _create_sandbox_for_review(suggestion)
            suggestion.context["sandbox_id"] = sandbox.id
            await _send_suggestion_to_owner(suggestion)

    # Update scan timestamp
    r.set(_LAST_SCAN_KEY, now.isoformat())

    # Update daily stats
    _update_daily_stats(r, len(cycle_suggestions))

    # STEP 5: Periodically check for adaptive rule changes
    cycle_count = int(r.get(f"{_AUTONOMY_PREFIX}cycle_count") or "0")
    r.set(f"{_AUTONOMY_PREFIX}cycle_count", str(cycle_count + 1))
    if cycle_count > 0 and cycle_count % 10 == 0:
        await _check_and_propose_rule_changes()

    if cycle_suggestions:
        logger.info(f"Monitor cycle: {len(cycle_suggestions)} suggestions generated")


async def _analyze_conversation(conv: list[dict], user_id: str, platform: str) -> list[Suggestion]:
    """Analyze a single conversation for issues and opportunities using LLM."""
    # Only analyze recent messages (last 10)
    recent = conv[-10:]
    if len(recent) < 2:
        return []

    # Build conversation text for LLM analysis
    conv_text = "\n".join(
        f"{'User' if m.get('role') == 'user' else 'AI'}: {m.get('content', '')[:200]}"
        for m in recent
    )

    analysis_prompt = f"""Analyze this conversation between a user and Fazle AI (acting as Azim).

Conversation:
{conv_text}

Detect ALL that apply (return JSON array):
1. high_interest: Is the user interested in a service/product? (buying signals, asking about prices, features)
2. confused: Is the user confused or not getting the help they need?
3. missed_conversion: Did AI miss an opportunity to convert interest into action?
4. bad_reply: Was any AI reply poor quality, too generic, or inappropriate?
5. negative_reaction: Did the user show frustration, anger, or disappointment?
6. repeated_question: Did the user ask the same thing multiple times?
7. tone_mismatch: Is the AI tone wrong for this conversation context?

Return JSON:
{{
  "findings": [
    {{"type": "type_name", "confidence": 0.0-1.0, "evidence": "brief quote", "suggestion_bn": "Bangla suggestion for owner", "suggestion_en": "English summary", "auto_fixable": true/false, "proposed_fix": "what to change"}}
  ]
}}
Return ONLY valid JSON. If nothing found, return {{"findings": []}}"""

    try:
        raw = await query_llm(analysis_prompt, system="You are Fazle's autonomous intelligence analyzer. Be precise, concise, and practical.")
        raw = raw.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        data = json.loads(raw)
    except (json.JSONDecodeError, Exception) as e:
        logger.debug(f"Analysis parse failed for {user_id}: {e}")
        return []

    findings = data.get("findings", [])
    suggestions = []

    type_map = {
        "high_interest": SuggestionType.follow_up,
        "confused": SuggestionType.confused_user,
        "missed_conversion": SuggestionType.missed_conversion,
        "bad_reply": SuggestionType.reply_improvement,
        "negative_reaction": SuggestionType.negative_reaction,
        "repeated_question": SuggestionType.repeated_question,
        "tone_mismatch": SuggestionType.tone_adjustment,
    }

    for f in findings[:3]:  # Max 3 suggestions per conversation
        stype = type_map.get(f.get("type"), SuggestionType.reply_improvement)
        confidence = min(max(float(f.get("confidence", 0.5)), 0.0), 1.0)

        if confidence < 0.4:
            continue  # Skip low-confidence findings

        suggestions.append(Suggestion(
            type=stype,
            user_id=user_id,
            platform=platform,
            message_bn=f.get("suggestion_bn", "একটি সমস্যা ধরা পড়েছে"),
            message_en=f.get("suggestion_en", "Issue detected"),
            confidence=confidence,
            context={"evidence": f.get("evidence", ""), "conversation_tail": conv[-3:]},
            auto_actionable=bool(f.get("auto_fixable", False)) and confidence >= 0.8,
            proposed_action=f.get("proposed_fix"),
        ))

    return suggestions


# ── STEP 2 & 3: Opportunity Detection + Suggestion Engine ────

async def _send_suggestion_to_owner(suggestion: Suggestion):
    """Send a suggestion to the owner via the Brain /chat/owner endpoint."""
    try:
        # Format as a proactive notification
        emoji_map = {
            SuggestionType.follow_up: "🎯",
            SuggestionType.confused_user: "😕",
            SuggestionType.missed_conversion: "💰",
            SuggestionType.reply_improvement: "✏️",
            SuggestionType.tone_adjustment: "🎭",
            SuggestionType.repeated_question: "🔄",
            SuggestionType.negative_reaction: "⚠️",
            SuggestionType.system_issue: "🔧",
        }
        emoji = emoji_map.get(suggestion.type, "💡")

        owner_msg = f"""{emoji} [Autonomous Insight]
{suggestion.message_bn}

User: {suggestion.user_id} ({suggestion.platform})
Confidence: {suggestion.confidence:.0%}
{f"Proposed action: {suggestion.proposed_action}" if suggestion.proposed_action else ""}

অনুমোদন করবেন? (হ্যাঁ/না)"""

        # Store as a pending autonomy suggestion in Redis
        r = _get_redis()
        r.setex(
            f"{_AUTONOMY_PREFIX}pending_suggestion:{suggestion.id}",
            3600,  # 1 hour TTL
            json.dumps({
                "id": suggestion.id,
                "type": suggestion.type.value,
                "user_id": suggestion.user_id,
                "platform": suggestion.platform,
                "proposed_action": suggestion.proposed_action,
                "message_bn": suggestion.message_bn,
                "confidence": suggestion.confidence,
            }),
        )

        # Send notification to owner via brain
        async with httpx.AsyncClient(timeout=15.0) as client:
            await client.post(
                f"{settings.brain_url}/chat/owner",
                json={
                    "message": owner_msg,
                    "sender_id": "autonomy-engine",
                    "platform": "system",
                },
            )
        suggestion.status = "sent_to_owner"
        logger.info(f"Suggestion sent to owner: {suggestion.type.value} for {suggestion.user_id}")

    except Exception as e:
        logger.error(f"Failed to send suggestion to owner: {e}")


# ── STEP 4: Auto-Improvement ────────────────────────────────

async def _auto_apply_improvement(suggestion: Suggestion):
    """Automatically apply safe improvements without owner input."""
    if not suggestion.proposed_action:
        return

    try:
        # Only apply tone/style improvements — these are safe and reversible
        if suggestion.type in (SuggestionType.tone_adjustment, SuggestionType.reply_improvement):
            # Store the improvement as a learning entry for the brain's persona
            async with httpx.AsyncClient(timeout=10.0) as client:
                await client.post(
                    f"{settings.memory_url}/store",
                    json={
                        "type": "knowledge",
                        "user": "autonomy-engine",
                        "content": {
                            "kind": "auto_improvement",
                            "improvement": suggestion.proposed_action,
                            "for_user": suggestion.user_id,
                            "platform": suggestion.platform,
                            "confidence": suggestion.confidence,
                        },
                        "text": f"Auto-improvement: {suggestion.proposed_action}",
                    },
                )

            suggestion.status = "auto_applied"

            # Log the improvement
            _log_learning("improvement_applied", {
                "suggestion_id": suggestion.id,
                "type": suggestion.type.value,
                "action": suggestion.proposed_action,
                "user_id": suggestion.user_id,
            }, "neutral")

            logger.info(f"Auto-improvement applied: {suggestion.type.value} for {suggestion.user_id}")

    except Exception as e:
        logger.error(f"Auto-improvement failed: {e}")


# ── EXECUTION AGENT — Guardrail Functions ────────────────────

def _get_execution_level(suggestion_type: SuggestionType) -> ExecutionLevel:
    """Get the execution level for a suggestion type, checking Redis overrides first."""
    r = _get_redis()
    override = r.hget(_EXECUTION_RULES_KEY, suggestion_type.value)
    if override and override in [e.value for e in ExecutionLevel]:
        return ExecutionLevel(override)
    return _execution_rules.get(suggestion_type, ExecutionLevel.high)


def _is_medium_auto_approved(suggestion_type: str) -> bool:
    """Check if owner has previously approved this medium-level type (ask-once logic)."""
    r = _get_redis()
    return bool(r.sismember(_MEDIUM_APPROVED_KEY, suggestion_type))


def _mark_medium_approved(suggestion_type: str):
    """After owner approves a medium-level suggestion, mark type as auto-approved."""
    r = _get_redis()
    r.sadd(_MEDIUM_APPROVED_KEY, suggestion_type)


# ── AUTO-BACKUP SYSTEM ──────────────────────────────────────

async def _backup_state(change_description: str, state_data: dict) -> str:
    """Create a backup before applying a change. Returns backup_id."""
    backup_id = str(uuid.uuid4())[:12]
    r = _get_redis()
    r.setex(
        f"{_BACKUP_PREFIX}{backup_id}",
        86400 * 3,  # 3-day TTL
        json.dumps({
            "id": backup_id,
            "description": change_description,
            "state": state_data,
            "created_at": datetime.utcnow().isoformat(),
        }),
    )
    logger.info(f"Backup created: {backup_id} — {change_description}")
    return backup_id


async def _restore_backup(backup_id: str) -> bool:
    """Restore from a backup — re-store the backed-up knowledge in memory."""
    r = _get_redis()
    raw = r.get(f"{_BACKUP_PREFIX}{backup_id}")
    if not raw:
        return False
    backup = json.loads(raw)
    state = backup.get("state", {})
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            await client.post(
                f"{settings.memory_url}/store",
                json={
                    "type": "knowledge",
                    "user": "backup-restore",
                    "content": state,
                    "text": f"Restored from backup: {backup.get('description', '')}",
                },
            )
        logger.info(f"Backup restored: {backup_id}")
        return True
    except Exception as e:
        logger.error(f"Backup restore failed: {e}")
        return False


# ── AUTO-EXECUTION PIPELINE ─────────────────────────────────

async def _auto_execute_action(suggestion: Suggestion) -> bool:
    """Execute an action automatically (for LOW and approved MEDIUM levels).
    Flow: backup → execute → log."""
    if not suggestion.proposed_action:
        return False

    # Step 1: Backup current state
    backup_id = await _backup_state(
        f"Before auto-exec: {suggestion.type.value} for {suggestion.user_id}",
        {
            "suggestion_id": suggestion.id,
            "type": suggestion.type.value,
            "proposed_action": suggestion.proposed_action,
        },
    )

    # STEP 2: Drift Control — check persona deviation before executing
    drift_safe, drift_score = await _check_drift(suggestion.proposed_action)
    if not drift_safe:
        suggestion.status = "blocked_drift"
        _log_learning("drift_blocked", {
            "suggestion_id": suggestion.id,
            "type": suggestion.type.value,
            "drift_score": drift_score,
            "action": suggestion.proposed_action[:100],
        }, "neutral")
        logger.warning(f"Drift blocked: {suggestion.type.value} (deviation: {drift_score:.2f})")
        return False

    level = _get_execution_level(suggestion.type).value

    # Step 2: Create sandbox audit trail
    sandbox = SandboxChange(
        suggestion_id=suggestion.id,
        change_type=suggestion.type.value,
        description=suggestion.proposed_action,
        proposed_state=suggestion.proposed_action,
        diff_summary=f"Auto-execute ({level}): {suggestion.proposed_action[:100]}",
        status="applied",
        backup_id=backup_id,
    )
    _sandbox_changes.append(sandbox)

    # Step 3: Execute the action
    try:
        if suggestion.type in (SuggestionType.tone_adjustment, SuggestionType.reply_improvement):
            async with httpx.AsyncClient(timeout=10.0) as client:
                await client.post(
                    f"{settings.memory_url}/store",
                    json={
                        "type": "knowledge",
                        "user": "autonomy-engine",
                        "content": {
                            "kind": "auto_improvement",
                            "improvement": suggestion.proposed_action,
                            "for_user": suggestion.user_id,
                            "platform": suggestion.platform,
                            "confidence": suggestion.confidence,
                            "execution_level": level,
                            "backup_id": backup_id,
                        },
                        "text": f"Auto-executed improvement: {suggestion.proposed_action}",
                    },
                )

        elif suggestion.type == SuggestionType.follow_up and suggestion.user_id:
            _increment_followup_count(suggestion.user_id)
            async with httpx.AsyncClient(timeout=15.0) as client:
                await client.post(
                    f"{settings.brain_url}/autonomy/trigger-followup",
                    json={"user_id": suggestion.user_id, "platform": suggestion.platform},
                )

        elif suggestion.type in (SuggestionType.confused_user, SuggestionType.repeated_question):
            # Store context so next reply is better
            async with httpx.AsyncClient(timeout=10.0) as client:
                await client.post(
                    f"{settings.memory_url}/store",
                    json={
                        "type": "knowledge",
                        "user": "autonomy-engine",
                        "content": {
                            "kind": "context_flag",
                            "flag": suggestion.type.value,
                            "user_id": suggestion.user_id,
                            "action": suggestion.proposed_action,
                            "backup_id": backup_id,
                        },
                        "text": f"Context flag ({suggestion.type.value}): {suggestion.proposed_action}",
                    },
                )

        suggestion.status = "auto_executed"

        # Log execution
        record = ExecutionRecord(
            suggestion_id=suggestion.id,
            suggestion_type=suggestion.type.value,
            execution_level=level,
            action=suggestion.proposed_action,
            status="executed",
            backup_id=backup_id,
        )
        _execution_log.append(record)

        _log_learning("auto_executed", {
            "suggestion_id": suggestion.id,
            "type": suggestion.type.value,
            "action": suggestion.proposed_action,
            "execution_level": level,
            "backup_id": backup_id,
        }, "neutral")

        logger.info(f"Auto-executed ({level}/{suggestion.type.value}): {suggestion.proposed_action[:80]}")

        # STEP 3: Record to execution memory
        _record_execution_memory(suggestion.type.value, suggestion.proposed_action, True, 0.7)

        return True

    except Exception as e:
        logger.error(f"Auto-execution failed: {e}")
        sandbox.status = "failed"
        _execution_log.append(ExecutionRecord(
            suggestion_id=suggestion.id,
            suggestion_type=suggestion.type.value,
            execution_level=level,
            action=suggestion.proposed_action or "",
            status="failed",
            result=str(e)[:200],
            backup_id=backup_id,
        ))
        # STEP 3: Record failed execution to memory
        _record_execution_memory(suggestion.type.value, suggestion.proposed_action or "", False, 0.1)
        return False


# ── SANDBOX EXECUTION ────────────────────────────────────────

async def _create_sandbox_for_review(suggestion: Suggestion) -> SandboxChange:
    """Create a sandbox change entry for owner review (HIGH level).
    Simulates the change and generates a diff for review."""
    diff = f"""--- Current Behavior ---
Standard response handling for {suggestion.type.value}

--- Proposed Change ---
{suggestion.proposed_action or 'No specific action defined'}

--- Impact ---
User: {suggestion.user_id} ({suggestion.platform})
Confidence: {suggestion.confidence:.0%}
Evidence: {suggestion.context.get('evidence', 'N/A')}"""

    sandbox = SandboxChange(
        suggestion_id=suggestion.id,
        change_type=suggestion.type.value,
        description=suggestion.message_en,
        current_state="Standard behavior",
        proposed_state=suggestion.proposed_action or suggestion.message_en,
        diff_summary=diff,
        status="pending",
    )
    _sandbox_changes.append(sandbox)

    # Persist in Redis for durability
    r = _get_redis()
    r.setex(
        f"{_SANDBOX_PREFIX}{sandbox.id}",
        7200,  # 2-hour TTL
        json.dumps(sandbox.dict()),
    )

    return sandbox


# ── STEP 5: Permission System ───────────────────────────────

async def approve_suggestion(suggestion_id: str) -> bool:
    """Owner approved a suggestion — execute it with backup + medium-type auto-approval."""
    r = _get_redis()
    raw = r.get(f"{_AUTONOMY_PREFIX}pending_suggestion:{suggestion_id}")
    if not raw:
        return False

    data = json.loads(raw)
    stype_str = data.get("type", "system_issue")

    try:
        # Backup before executing approved action
        backup_id = await _backup_state(
            f"Owner-approved: {stype_str} for {data.get('user_id', 'unknown')}",
            {"suggestion_id": suggestion_id, "type": stype_str, "action": data.get("proposed_action", "")},
        )

        # Execute the approved action
        if data.get("proposed_action"):
            # Store as approved improvement in memory
            async with httpx.AsyncClient(timeout=10.0) as client:
                await client.post(
                    f"{settings.memory_url}/store",
                    json={
                        "type": "knowledge",
                        "user": "owner-approved",
                        "content": {
                            "kind": "approved_improvement",
                            "action": data["proposed_action"],
                            "for_user": data.get("user_id", ""),
                            "suggestion_type": stype_str,
                            "backup_id": backup_id,
                        },
                        "text": f"Owner-approved improvement: {data['proposed_action']}",
                    },
                )

            # If it's a follow-up, trigger it
            if data.get("type") == "follow_up" and data.get("user_id"):
                async with httpx.AsyncClient(timeout=15.0) as client:
                    await client.post(
                        f"{settings.brain_url}/autonomy/trigger-followup",
                        json={"user_id": data["user_id"], "platform": data.get("platform", "whatsapp")},
                    )

        # Mark medium-level types as auto-approved for future (ask-once)
        try:
            stype_enum = SuggestionType(stype_str)
            level = _get_execution_level(stype_enum)
            if level == ExecutionLevel.medium:
                _mark_medium_approved(stype_str)
                logger.info(f"Medium type '{stype_str}' marked as auto-approved for future")
        except ValueError:
            pass

        # Apply any pending sandbox change tied to this suggestion
        for sc in _sandbox_changes:
            if sc.suggestion_id == suggestion_id and sc.status == "pending":
                sc.status = "applied"
                sc.backup_id = backup_id

        # Log approval with execution tracking
        _log_learning("suggestion_approved", {
            "suggestion_id": suggestion_id,
            "type": stype_str,
            "user_id": data.get("user_id"),
            "backup_id": backup_id,
        }, "positive")

        _execution_log.append(ExecutionRecord(
            suggestion_id=suggestion_id,
            suggestion_type=stype_str,
            execution_level=_get_execution_level(SuggestionType(stype_str)).value if stype_str in [s.value for s in SuggestionType] else "high",
            action=data.get("proposed_action", "approved"),
            status="executed",
            backup_id=backup_id,
        ))

        # STEP 3: Record positive execution memory
        _record_execution_memory(stype_str, data.get("proposed_action", ""), True, 0.9)

        # Cleanup
        r.delete(f"{_AUTONOMY_PREFIX}pending_suggestion:{suggestion_id}")

        # Update in-memory suggestion
        for s in _suggestions:
            if s.id == suggestion_id:
                s.status = "approved"
                break

        return True

    except Exception as e:
        logger.error(f"Suggestion approval execution failed: {e}")
        return False


async def reject_suggestion(suggestion_id: str) -> bool:
    """Owner rejected a suggestion — learn from it."""
    r = _get_redis()
    raw = r.get(f"{_AUTONOMY_PREFIX}pending_suggestion:{suggestion_id}")
    if not raw:
        return False

    data = json.loads(raw)

    # STEP 3: Record negative execution memory
    _record_execution_memory(data.get("type", "unknown"), data.get("proposed_action", ""), False, 0.1)

    _log_learning("suggestion_rejected", {
        "suggestion_id": suggestion_id,
        "type": data.get("type"),
        "user_id": data.get("user_id"),
    }, "negative")

    r.delete(f"{_AUTONOMY_PREFIX}pending_suggestion:{suggestion_id}")

    for s in _suggestions:
        if s.id == suggestion_id:
            s.status = "rejected"
            break

    return True


# ── STEP 6: Learning Loop ───────────────────────────────────

def _log_learning(event_type: str, details: dict, outcome: str):
    """Log a learning event for the feedback loop."""
    entry = LearningEntry(
        event_type=event_type,
        details=details,
        outcome=outcome,
    )
    _learning_log.append(entry)

    # Also persist to Redis (keep last 200)
    r = _get_redis()
    r.rpush(_LEARNING_KEY, json.dumps({
        "id": entry.id,
        "event_type": event_type,
        "details": details,
        "outcome": outcome,
        "ts": entry.created_at,
    }))
    r.ltrim(_LEARNING_KEY, -200, -1)


def _update_daily_stats(r: redis.Redis, suggestions_count: int):
    """Update daily monitoring statistics."""
    today = datetime.utcnow().strftime("%Y-%m-%d")
    key = f"{_DAILY_STATS_KEY}:{today}"
    r.hincrby(key, "scan_cycles", 1)
    r.hincrby(key, "suggestions_generated", suggestions_count)
    r.expire(key, 86400 * 7)  # Keep 7 days


# ── STEP 7: Intelligence Report ─────────────────────────────

async def generate_intelligence_report() -> dict:
    """Generate a comprehensive daily intelligence report with execution stats."""
    r = _get_redis()
    today = datetime.utcnow().strftime("%Y-%m-%d")

    # Gather stats
    daily_key = f"{_DAILY_STATS_KEY}:{today}"
    stats = r.hgetall(daily_key)

    # Gather learning log for today
    raw_log = r.lrange(_LEARNING_KEY, -50, -1)
    today_events = []
    for raw in raw_log:
        try:
            entry = json.loads(raw)
            if entry.get("ts", "").startswith(today):
                today_events.append(entry)
        except json.JSONDecodeError:
            pass

    # Count outcomes
    approved = sum(1 for e in today_events if e.get("outcome") == "positive")
    rejected = sum(1 for e in today_events if e.get("outcome") == "negative")
    auto_applied = sum(1 for e in today_events if e.get("event_type") == "improvement_applied")
    auto_executed = sum(1 for e in today_events if e.get("event_type") == "auto_executed")

    # Recent suggestions summary
    recent_suggestions = [s for s in _suggestions[-20:]]
    suggestion_types = {}
    for s in recent_suggestions:
        t = s.type.value
        suggestion_types[t] = suggestion_types.get(t, 0) + 1

    # Execution stats
    exec_stats = {
        "auto_executed_low": sum(1 for e in _execution_log if e.execution_level == "low"),
        "auto_executed_medium": sum(1 for e in _execution_log if e.execution_level == "medium"),
        "owner_confirmed_high": sum(1 for e in _execution_log if e.execution_level == "high"),
        "sandbox_pending": sum(1 for s in _sandbox_changes if s.status == "pending"),
        "sandbox_applied": sum(1 for s in _sandbox_changes if s.status == "applied"),
        "execution_failures": sum(1 for e in _execution_log if e.status == "failed"),
    }
    medium_approved = list(r.smembers(_MEDIUM_APPROVED_KEY) or [])

    # STEP 7: Execution Memory stats — success rate, failed actions, top performers
    exec_mem_data = r.lrange(_EXEC_MEMORY_KEY, -200, -1)
    exec_mem_total = len(exec_mem_data)
    exec_mem_successes = 0
    type_performance: dict[str, dict] = {}
    failed_actions_today = []
    drift_blocked = sum(1 for e in today_events if e.get("event_type") == "drift_blocked")
    low_confidence_skipped = sum(1 for e in today_events if e.get("event_type") == "skipped_low_confidence")
    followup_limited = sum(1 for e in today_events if e.get("event_type") == "followup_limit_reached")

    for raw_em in exec_mem_data:
        try:
            em = json.loads(raw_em)
            atype = em.get("action_type", "unknown")
            if atype not in type_performance:
                type_performance[atype] = {"total": 0, "success": 0}
            type_performance[atype]["total"] += 1
            if em.get("success_score", 0) >= 0.5:
                exec_mem_successes += 1
                type_performance[atype]["success"] += 1
            else:
                if em.get("ts", "").startswith(today):
                    failed_actions_today.append({"type": atype, "action": em.get("action", "")[:80]})
        except json.JSONDecodeError:
            pass

    overall_success_rate = round((exec_mem_successes / exec_mem_total * 100), 1) if exec_mem_total > 0 else 0
    top_performers = sorted(
        [(k, round(v["success"] / v["total"] * 100, 1) if v["total"] > 0 else 0, v["total"])
         for k, v in type_performance.items() if v["total"] >= 3],
        key=lambda x: x[1], reverse=True
    )[:5]

    # Pending adaptive rule changes
    pending_changes = r.hgetall(_PENDING_RULE_CHANGES_KEY) or {}

    # Generate LLM intelligence report
    report_prompt = f"""Generate a concise daily intelligence report in Bangla for the AI system owner.

Today's Data:
- Scan cycles: {stats.get('scan_cycles', 0)}
- Suggestions generated: {stats.get('suggestions_generated', 0)}
- Owner approved: {approved}
- Owner rejected: {rejected}
- Auto-applied improvements: {auto_applied}
- Auto-executed actions: {auto_executed}
- Suggestion breakdown: {json.dumps(suggestion_types)}
- Active in-memory suggestions: {len(_suggestions)}

Execution Agent Stats:
- LOW level (auto-executed): {exec_stats['auto_executed_low']}
- MEDIUM level (ask-once, auto after approval): {exec_stats['auto_executed_medium']}
- HIGH level (always confirmed): {exec_stats['owner_confirmed_high']}
- Medium types now auto-approved: {medium_approved}
- Sandbox changes pending: {exec_stats['sandbox_pending']}
- Sandbox changes applied: {exec_stats['sandbox_applied']}
- Execution failures: {exec_stats['execution_failures']}

Intelligence Enhancement Stats:
- Overall execution success rate: {overall_success_rate}%
- Failed actions today: {len(failed_actions_today)}
- Top performing action types: {json.dumps([(t[0], f"{t[1]}%", t[2]) for t in top_performers])}
- Drift control blocks: {drift_blocked}
- Low confidence skipped: {low_confidence_skipped}
- Follow-up limit hits: {followup_limited}
- Pending adaptive rule changes: {len(pending_changes)}

Recent learning events: {len(today_events)}

Guidelines:
1. Start with key insights (Bangla)
2. Highlight execution agent performance + success rate
3. List problems detected and actions taken
4. Report failed actions and drift blocks
5. Note what the system did automatically vs what needed owner approval
6. Mention top performing action types
7. End with a confidence score for AI performance today
8. Be brief — max 22 lines"""

    try:
        report_text = await query_llm(
            report_prompt,
            system="You are Fazle's intelligence reporting system. Write in Bangla. Be concise and actionable.",
        )
    except Exception:
        report_text = "রিপোর্ট তৈরি করা যায়নি।"

    return {
        "report": report_text,
        "date": today,
        "stats": {
            "scan_cycles": int(stats.get("scan_cycles", 0)),
            "suggestions_generated": int(stats.get("suggestions_generated", 0)),
            "approved": approved,
            "rejected": rejected,
            "auto_applied": auto_applied,
            "auto_executed": auto_executed,
            "suggestion_types": suggestion_types,
        },
        "execution": exec_stats,
        "medium_auto_approved": medium_approved,
        "learning_events_today": len(today_events),
        "intelligence": {
            "overall_success_rate": overall_success_rate,
            "exec_memory_total": exec_mem_total,
            "failed_actions_today": failed_actions_today[:10],
            "top_performers": [{"type": t[0], "success_rate": t[1], "samples": t[2]} for t in top_performers],
            "drift_blocked": drift_blocked,
            "low_confidence_skipped": low_confidence_skipped,
            "followup_limited": followup_limited,
            "pending_rule_changes": len(pending_changes),
        },
    }


# ── LLM helper ──────────────────────────────────────────────

async def query_llm(prompt: str, system: str = "") -> str:
    """Route LLM queries through the gateway."""
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    else:
        messages.append({"role": "system", "content": "You are Fazle's autonomy planning engine. Decompose goals into concrete actionable steps."})
    messages.append({"role": "user", "content": prompt})

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            resp = await client.post(
                f"{settings.llm_gateway_url}/generate",
                json={
                    "messages": messages,
                    "temperature": 0.3,
                    "caller": "autonomy-engine",
                },
            )
            resp.raise_for_status()
            data = resp.json()
            return data.get("content", data.get("response", data.get("text", "")))
        except Exception as e:
            logger.error(f"LLM query failed: {e}")
            raise HTTPException(status_code=502, detail="LLM gateway unreachable")


async def retrieve_context(goal: str) -> str:
    """Pull relevant memories for planning context."""
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.post(
                f"{settings.memory_url}/search",
                json={"query": goal, "top_k": 5},
            )
            if resp.status_code == 200:
                results = resp.json()
                if isinstance(results, list):
                    return "\n".join(r.get("content", "") for r in results[:5])
                return str(results)
        except Exception:
            logger.warning("Memory retrieval failed, proceeding without context")
    return ""


# ── Plan Generation ─────────────────────────────────────────

async def generate_plan(goal: str, context: Optional[str] = None, max_steps: int = 10) -> list[PlanStep]:
    """Use LLM to decompose a goal into executable steps."""
    memory_context = await retrieve_context(goal)

    prompt = f"""Decompose the following goal into concrete, executable steps.

Goal: {goal}

{"Additional context: " + context if context else ""}
{"Relevant memories: " + memory_context if memory_context else ""}

Return a JSON array of steps. Each step must have:
- "action": short action name (e.g., "web_search", "analyze", "store_memory", "notify", "code_execute", "summarize")
- "description": what this step does
- "tool": which tool to use (one of: web_search, memory_store, memory_search, code_sandbox, http_request, summarize, notify, none)
- "depends_on": array of step indices (0-based) this step depends on

Maximum {max_steps} steps. Return ONLY valid JSON array, no markdown."""

    raw = await query_llm(prompt)

    # Parse JSON from response
    try:
        # Try to extract JSON array from response
        raw = raw.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        steps_data = json.loads(raw)
    except json.JSONDecodeError:
        # Fallback: single-step plan
        logger.warning("Failed to parse plan from LLM, using single-step fallback")
        steps_data = [{"action": "execute", "description": goal, "tool": "none", "depends_on": []}]

    steps = []
    for i, s in enumerate(steps_data[:max_steps]):
        step = PlanStep(
            action=s.get("action", f"step_{i}"),
            description=s.get("description", ""),
            tool=s.get("tool"),
            depends_on=[steps[d].id for d in s.get("depends_on", []) if d < len(steps)],
        )
        steps.append(step)

    return steps


# ── Step Execution ───────────────────────────────────────────

async def execute_step(plan: AutonomyPlan, step: PlanStep) -> str:
    """Execute a single plan step using the appropriate tool."""
    step.status = "executing"
    step.started_at = datetime.utcnow().isoformat()

    try:
        result = ""
        async with httpx.AsyncClient(timeout=30.0) as client:
            if step.tool == "web_search":
                resp = await client.post(
                    f"{settings.tools_url}/search",
                    json={"query": step.description, "max_results": 5},
                )
                result = resp.text if resp.status_code == 200 else f"Search failed: {resp.status_code}"

            elif step.tool == "memory_store":
                resp = await client.post(
                    f"{settings.memory_url}/store",
                    json={"content": step.description, "type": "autonomy_result"},
                )
                result = "Stored in memory" if resp.status_code == 200 else f"Store failed: {resp.status_code}"

            elif step.tool == "memory_search":
                resp = await client.post(
                    f"{settings.memory_url}/search",
                    json={"query": step.description, "top_k": 5},
                )
                result = resp.text if resp.status_code == 200 else f"Search failed: {resp.status_code}"

            elif step.tool == "summarize":
                # Gather previous step results for summarization
                prev_results = "\n".join(
                    f"Step '{s.action}': {s.result}"
                    for s in plan.steps if s.result and s.id != step.id
                )
                result = await query_llm(
                    f"Summarize these results:\n{prev_results}\n\nFor goal: {plan.goal}",
                    system="Provide a concise summary.",
                )

            elif step.tool in ("code_sandbox", "http_request"):
                # Route to tool execution engine
                resp = await client.post(
                    f"{settings.tool_engine_url}/tools/execute",
                    json={"tool_name": step.tool, "parameters": {"description": step.description}},
                )
                result = resp.text if resp.status_code == 200 else f"Tool exec failed: {resp.status_code}"

            else:
                # Generic: ask LLM to perform the step
                result = await query_llm(
                    f"Perform this step: {step.description}\nContext: {plan.goal}",
                )

        step.status = "completed"
        step.result = result[:2000]  # Truncate large results
        step.completed_at = datetime.utcnow().isoformat()
        return result

    except Exception as e:
        step.status = "failed"
        step.error = str(e)[:500]
        step.completed_at = datetime.utcnow().isoformat()
        raise


# ── Reflection ───────────────────────────────────────────────

async def reflect_on_plan(plan: AutonomyPlan) -> str:
    """Self-reflect on plan execution results."""
    results_summary = "\n".join(
        f"Step '{s.action}' ({s.status}): {s.result or s.error or 'no output'}"
        for s in plan.steps
    )

    prompt = f"""Reflect on this autonomous plan execution:

Goal: {plan.goal}
Steps and Results:
{results_summary}

Evaluate:
1. Was the goal achieved?
2. What worked well?
3. What could be improved?
4. Any follow-up actions needed?

Be concise."""

    return await query_llm(prompt, system="You are Fazle's reflection engine. Evaluate plan execution honestly.")


# ── Plan Execution Orchestrator ──────────────────────────────

async def execute_plan(plan_id: str, step_ids: Optional[list[str]] = None):
    """Execute a plan (all steps or specific ones)."""
    plan = _plans.get(plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")

    plan.status = PlanStatus.executing
    plan.updated_at = datetime.utcnow().isoformat()

    steps_to_run = plan.steps
    if step_ids:
        steps_to_run = [s for s in plan.steps if s.id in step_ids]

    # Execute steps respecting dependencies
    completed_ids = {s.id for s in plan.steps if s.status == "completed"}

    for step in steps_to_run:
        if step.status == "completed":
            continue

        # Wait for dependencies
        for dep_id in step.depends_on:
            if dep_id not in completed_ids:
                dep_step = next((s for s in plan.steps if s.id == dep_id), None)
                if dep_step and dep_step.status == "failed":
                    step.status = "skipped"
                    step.error = f"Dependency {dep_id} failed"
                    continue

        try:
            await execute_step(plan, step)
            completed_ids.add(step.id)
        except Exception as e:
            logger.error(f"Step {step.id} failed: {e}")
            if plan.retry_count < settings.max_retries:
                plan.retry_count += 1
                step.status = "pending"  # Allow retry
            else:
                step.status = "failed"

    # Reflection
    if settings.reflection_enabled:
        plan.status = PlanStatus.reflecting
        try:
            plan.reflection = await reflect_on_plan(plan)
        except Exception as e:
            logger.error(f"Reflection failed: {e}")

    # Update final status
    failed_steps = [s for s in plan.steps if s.status == "failed"]
    if failed_steps:
        plan.status = PlanStatus.failed if len(failed_steps) == len(plan.steps) else PlanStatus.completed
    else:
        plan.status = PlanStatus.completed

    plan.completed_at = datetime.utcnow().isoformat()
    plan.updated_at = datetime.utcnow().isoformat()


# ── Endpoints ────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "healthy", "service": "autonomy-engine", "plans_count": len(_plans)}


@app.post("/autonomy/plan", response_model=PlanResponse)
async def create_plan(req: PlanRequest):
    """Generate an autonomous execution plan from a goal."""
    max_steps = min(req.max_steps or settings.max_plan_steps, settings.max_plan_steps)

    plan = AutonomyPlan(
        goal=req.goal,
        context=req.context,
        status=PlanStatus.planning,
        user_id=req.user_id,
    )
    _plans[plan.id] = plan

    try:
        plan.steps = await generate_plan(req.goal, req.context, max_steps)
        plan.status = PlanStatus.pending
        plan.updated_at = datetime.utcnow().isoformat()
    except Exception as e:
        plan.status = PlanStatus.failed
        plan.updated_at = datetime.utcnow().isoformat()
        raise HTTPException(status_code=500, detail=f"Plan generation failed: {e}")

    # Auto-execute if requested
    if req.auto_execute:
        asyncio.create_task(execute_plan(plan.id))
        return PlanResponse(plan=plan, message="Plan generated and execution started")

    return PlanResponse(plan=plan, message=f"Plan generated with {len(plan.steps)} steps")


@app.post("/autonomy/execute", response_model=PlanResponse)
async def trigger_execution(req: ExecuteRequest):
    """Execute a previously generated plan."""
    if req.plan_id not in _plans:
        raise HTTPException(status_code=404, detail="Plan not found")

    asyncio.create_task(execute_plan(req.plan_id, req.step_ids))
    plan = _plans[req.plan_id]
    return PlanResponse(plan=plan, message="Execution started")


@app.get("/autonomy/plan/{plan_id}", response_model=PlanResponse)
async def get_plan(plan_id: str):
    """Get plan status and details."""
    plan = _plans.get(plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    return PlanResponse(plan=plan, message=f"Plan status: {plan.status}")


@app.get("/autonomy/plans")
async def list_plans(limit: int = 20, status: Optional[str] = None):
    """List all plans, optionally filtered by status."""
    plans = list(_plans.values())
    if status:
        plans = [p for p in plans if p.status == status]
    plans.sort(key=lambda p: p.created_at, reverse=True)
    return {"plans": plans[:limit], "total": len(plans)}


@app.delete("/autonomy/plan/{plan_id}")
async def delete_plan(plan_id: str):
    """Delete a plan."""
    if plan_id not in _plans:
        raise HTTPException(status_code=404, detail="Plan not found")
    del _plans[plan_id]
    return {"message": "Plan deleted"}


@app.post("/autonomy/plan/{plan_id}/pause")
async def pause_plan(plan_id: str):
    """Pause an executing plan."""
    plan = _plans.get(plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    plan.status = PlanStatus.paused
    plan.updated_at = datetime.utcnow().isoformat()
    return {"message": "Plan paused", "plan_id": plan_id}


# ═══════════════════════════════════════════════════════════════
# Autonomous Decision Engine — API Endpoints
# ═══════════════════════════════════════════════════════════════

@app.post("/autonomy/monitor/trigger")
async def trigger_monitor_cycle():
    """Manually trigger a monitoring cycle (for testing or on-demand)."""
    try:
        await _run_monitoring_cycle()
        return {"message": "Monitor cycle completed", "suggestions_count": len(_suggestions)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/autonomy/suggestions")
async def get_suggestions(status: Optional[str] = None, limit: int = 20):
    """Get recent suggestions, optionally filtered by status."""
    result = _suggestions[-limit:]
    if status:
        result = [s for s in result if s.status == status]
    return {"suggestions": [s.dict() for s in result], "total": len(_suggestions)}


@app.post("/autonomy/suggestions/{suggestion_id}/approve")
async def api_approve_suggestion(suggestion_id: str):
    """Owner approves a suggestion."""
    ok = await approve_suggestion(suggestion_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Suggestion not found or expired")
    return {"message": "Suggestion approved and executed", "id": suggestion_id}


@app.post("/autonomy/suggestions/{suggestion_id}/reject")
async def api_reject_suggestion(suggestion_id: str):
    """Owner rejects a suggestion."""
    ok = await reject_suggestion(suggestion_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Suggestion not found or expired")
    return {"message": "Suggestion rejected — learning recorded", "id": suggestion_id}


@app.get("/autonomy/learning")
async def get_learning_log(limit: int = 50):
    """Get recent learning events."""
    return {"events": [e.dict() for e in _learning_log[-limit:]], "total": len(_learning_log)}


@app.get("/autonomy/intelligence-report")
async def get_intelligence_report():
    """Generate and return the daily intelligence report."""
    report = await generate_intelligence_report()
    return report


@app.get("/autonomy/monitor/status")
async def monitor_status():
    """Get the current monitor status with execution agent info."""
    r = _get_redis()
    last_scan = r.get(_LAST_SCAN_KEY)
    medium_approved = list(r.smembers(_MEDIUM_APPROVED_KEY) or [])
    return {
        "monitor_enabled": settings.monitor_enabled,
        "monitor_running": _monitor_task is not None and not _monitor_task.done(),
        "monitor_interval_seconds": settings.monitor_interval_seconds,
        "suggestion_cooldown_seconds": settings.suggestion_cooldown_seconds,
        "auto_improve_enabled": settings.auto_improve_enabled,
        "last_scan": last_scan,
        "total_suggestions": len(_suggestions),
        "pending_suggestions": sum(1 for s in _suggestions if s.status == "pending"),
        "execution_agent": {
            "total_executions": len(_execution_log),
            "sandbox_pending": sum(1 for s in _sandbox_changes if s.status == "pending"),
            "medium_auto_approved_types": medium_approved,
        },
    }


# ═══════════════════════════════════════════════════════════════
# Execution Agent — API Endpoints
# ═══════════════════════════════════════════════════════════════

@app.get("/autonomy/execution-rules")
async def get_execution_rules():
    """Get current execution rules (which levels apply to which suggestion types)."""
    r = _get_redis()
    rules = {}
    for stype in SuggestionType:
        override = r.hget(_EXECUTION_RULES_KEY, stype.value)
        level = override if override else _execution_rules.get(stype, ExecutionLevel.high).value
        rules[stype.value] = level
    medium_approved = list(r.smembers(_MEDIUM_APPROVED_KEY) or [])
    return {
        "rules": rules,
        "medium_auto_approved": medium_approved,
        "levels": {"low": "Auto-execute", "medium": "Ask once", "high": "Always confirm"},
    }


class UpdateRuleRequest(BaseModel):
    level: str  # low / medium / high


@app.put("/autonomy/execution-rules/{suggestion_type}")
async def update_execution_rule(suggestion_type: str, req: UpdateRuleRequest):
    """Owner updates the execution level for a suggestion type."""
    if suggestion_type not in [s.value for s in SuggestionType]:
        raise HTTPException(status_code=400, detail="Invalid suggestion type")
    if req.level not in [e.value for e in ExecutionLevel]:
        raise HTTPException(status_code=400, detail="Invalid level (low/medium/high)")
    r = _get_redis()
    r.hset(_EXECUTION_RULES_KEY, suggestion_type, req.level)
    return {"message": f"Rule updated: {suggestion_type} → {req.level}"}


@app.get("/autonomy/sandbox")
async def get_sandbox_changes(status: Optional[str] = None, limit: int = 20):
    """Get sandbox changes pending review."""
    result = _sandbox_changes[-limit:]
    if status:
        result = [s for s in result if s.status == status]
    return {"changes": [s.dict() for s in result], "total": len(_sandbox_changes)}


@app.get("/autonomy/sandbox/{change_id}/diff")
async def get_sandbox_diff(change_id: str):
    """Get the diff/details of a sandbox change."""
    sandbox = next((s for s in _sandbox_changes if s.id == change_id), None)
    if not sandbox:
        raise HTTPException(status_code=404, detail="Sandbox change not found")
    return {
        "id": sandbox.id,
        "change_type": sandbox.change_type,
        "description": sandbox.description,
        "current_state": sandbox.current_state,
        "proposed_state": sandbox.proposed_state,
        "diff": sandbox.diff_summary,
        "status": sandbox.status,
        "backup_id": sandbox.backup_id,
    }


@app.post("/autonomy/sandbox/{change_id}/apply")
async def apply_sandbox_change(change_id: str):
    """Apply a reviewed sandbox change (with auto-backup)."""
    sandbox = next((s for s in _sandbox_changes if s.id == change_id), None)
    if not sandbox:
        raise HTTPException(status_code=404, detail="Sandbox change not found")
    if sandbox.status != "pending":
        raise HTTPException(status_code=400, detail=f"Change already {sandbox.status}")

    # Backup before applying
    backup_id = await _backup_state(
        f"Sandbox apply: {sandbox.change_type}",
        {"sandbox_id": sandbox.id, "current_state": sandbox.current_state},
    )
    sandbox.backup_id = backup_id

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            await client.post(
                f"{settings.memory_url}/store",
                json={
                    "type": "knowledge",
                    "user": "sandbox-approved",
                    "content": {
                        "kind": "sandbox_improvement",
                        "change_type": sandbox.change_type,
                        "improvement": sandbox.proposed_state,
                        "backup_id": backup_id,
                    },
                    "text": f"Sandbox-approved: {sandbox.proposed_state}",
                },
            )
        sandbox.status = "applied"
        _log_learning("sandbox_applied", {"sandbox_id": sandbox.id, "type": sandbox.change_type}, "positive")
        return {"message": "Change applied", "backup_id": backup_id}
    except Exception as e:
        sandbox.status = "failed"
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/autonomy/sandbox/{change_id}/reject")
async def reject_sandbox_change(change_id: str):
    """Reject a sandbox change."""
    sandbox = next((s for s in _sandbox_changes if s.id == change_id), None)
    if not sandbox:
        raise HTTPException(status_code=404, detail="Sandbox change not found")
    sandbox.status = "rejected"
    _log_learning("sandbox_rejected", {"sandbox_id": sandbox.id, "type": sandbox.change_type}, "negative")
    return {"message": "Change rejected"}


@app.get("/autonomy/backups")
async def list_backups(limit: int = 20):
    """List recent backups."""
    r = _get_redis()
    keys = r.keys(f"{_BACKUP_PREFIX}*")
    backups = []
    for key in sorted(keys, reverse=True)[:limit]:
        raw = r.get(key)
        if raw:
            backups.append(json.loads(raw))
    return {"backups": backups, "total": len(keys)}


@app.post("/autonomy/backups/{backup_id}/restore")
async def restore_from_backup(backup_id: str):
    """Restore system state from a backup."""
    ok = await _restore_backup(backup_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Backup not found or restore failed")
    _log_learning("backup_restored", {"backup_id": backup_id}, "neutral")
    return {"message": f"Restored from backup {backup_id}"}


@app.get("/autonomy/execution-stats")
async def get_execution_stats():
    """Get execution agent statistics."""
    r = _get_redis()
    medium_approved = list(r.smembers(_MEDIUM_APPROVED_KEY) or [])
    return {
        "total_executions": len(_execution_log),
        "by_level": {
            "low_auto": sum(1 for e in _execution_log if e.execution_level == "low"),
            "medium_auto": sum(1 for e in _execution_log if e.execution_level == "medium"),
            "high_confirmed": sum(1 for e in _execution_log if e.execution_level == "high"),
        },
        "by_status": {
            "executed": sum(1 for e in _execution_log if e.status == "executed"),
            "failed": sum(1 for e in _execution_log if e.status == "failed"),
            "rolled_back": sum(1 for e in _execution_log if e.status == "rolled_back"),
        },
        "sandbox": {
            "total": len(_sandbox_changes),
            "pending": sum(1 for s in _sandbox_changes if s.status == "pending"),
            "applied": sum(1 for s in _sandbox_changes if s.status == "applied"),
            "rejected": sum(1 for s in _sandbox_changes if s.status == "rejected"),
        },
        "backups_count": len(r.keys(f"{_BACKUP_PREFIX}*")),
        "medium_auto_approved_types": medium_approved,
        "recent_executions": [e.dict() for e in _execution_log[-10:]],
    }


# ═══════════════════════════════════════════════════════════════
# Intelligence Enhancement — API Endpoints
# ═══════════════════════════════════════════════════════════════

@app.get("/autonomy/confidence/{suggestion_type}")
async def get_confidence_stats(suggestion_type: str):
    """Get confidence/success stats for a suggestion type."""
    if suggestion_type not in [s.value for s in SuggestionType]:
        raise HTTPException(status_code=400, detail="Invalid suggestion type")
    r = _get_redis()
    exec_data = r.lrange(_EXEC_MEMORY_KEY, -200, -1)
    total = 0
    successes = 0
    scores = []
    for raw in exec_data:
        try:
            entry = json.loads(raw)
            if entry.get("action_type") == suggestion_type:
                total += 1
                score = entry.get("success_score", 0)
                scores.append(score)
                if score >= 0.5:
                    successes += 1
        except json.JSONDecodeError:
            pass
    avg_score = round(sum(scores) / len(scores), 2) if scores else 0
    return {
        "suggestion_type": suggestion_type,
        "total_executions": total,
        "successes": successes,
        "failures": total - successes,
        "success_rate": round(successes / total * 100, 1) if total > 0 else 0,
        "avg_confidence_score": avg_score,
        "current_execution_level": _get_execution_level(SuggestionType(suggestion_type)).value,
    }


@app.get("/autonomy/drift/status")
async def get_drift_status():
    """Get current drift control status."""
    r = _get_redis()
    baseline = r.get(_BASELINE_PERSONA_KEY)
    today = datetime.utcnow().strftime("%Y-%m-%d")
    raw_log = r.lrange(_LEARNING_KEY, -50, -1)
    drift_blocks_today = 0
    for raw in raw_log:
        try:
            entry = json.loads(raw)
            if entry.get("event_type") == "drift_blocked" and entry.get("ts", "").startswith(today):
                drift_blocks_today += 1
        except json.JSONDecodeError:
            pass
    return {
        "baseline_set": baseline is not None,
        "baseline_preview": baseline[:200] if baseline else None,
        "max_deviation": settings.drift_max_deviation,
        "drift_blocks_today": drift_blocks_today,
    }


@app.post("/autonomy/drift/reset-baseline")
async def reset_baseline_persona():
    """Reset the baseline persona (re-initializes from brain)."""
    r = _get_redis()
    r.delete(_BASELINE_PERSONA_KEY)
    await _initialize_baseline_persona()
    baseline = r.get(_BASELINE_PERSONA_KEY)
    return {"message": "Baseline persona reset", "baseline": baseline}


@app.get("/autonomy/user-priority/{user_id}")
async def get_user_priority_endpoint(user_id: str):
    """Get user priority level."""
    priority = _get_user_priority(user_id)
    r = _get_redis()
    is_override = r.exists(f"{_USER_PRIORITY_PREFIX}{user_id}")
    return {"user_id": user_id, "priority": priority, "is_manual_override": bool(is_override)}


class SetPriorityRequest(BaseModel):
    priority: str  # high / medium / low


@app.put("/autonomy/user-priority/{user_id}")
async def set_user_priority_endpoint(user_id: str, req: SetPriorityRequest):
    """Manually set user priority level."""
    if req.priority not in ("high", "medium", "low"):
        raise HTTPException(status_code=400, detail="Invalid priority (high/medium/low)")
    r = _get_redis()
    r.set(f"{_USER_PRIORITY_PREFIX}{user_id}", req.priority)
    return {"message": f"User {user_id} priority set to {req.priority}"}


@app.get("/autonomy/adaptive-rules")
async def get_pending_rule_changes():
    """Get pending adaptive rule change proposals."""
    r = _get_redis()
    raw = r.hgetall(_PENDING_RULE_CHANGES_KEY) or {}
    changes = []
    for raw_val in raw.values():
        try:
            changes.append(json.loads(raw_val))
        except json.JSONDecodeError:
            pass
    changes.sort(key=lambda c: c.get("created_at", ""), reverse=True)
    return {"pending_changes": changes, "total": len(changes)}


@app.post("/autonomy/adaptive-rules/{change_id}/approve")
async def approve_rule_change(change_id: str):
    """Owner approves an adaptive rule change."""
    r = _get_redis()
    raw = r.hget(_PENDING_RULE_CHANGES_KEY, change_id)
    if not raw:
        raise HTTPException(status_code=404, detail="Rule change not found")
    change = json.loads(raw)
    # Apply the rule change
    r.hset(_EXECUTION_RULES_KEY, change["action_type"], change["suggested_level"])
    r.hdel(_PENDING_RULE_CHANGES_KEY, change_id)
    _log_learning("adaptive_rule_approved", {
        "action_type": change["action_type"],
        "from": change["current_level"],
        "to": change["suggested_level"],
        "success_rate": change["success_rate"],
    }, "positive")
    return {"message": f"Rule updated: {change['action_type']} → {change['suggested_level']}"}


@app.post("/autonomy/adaptive-rules/{change_id}/reject")
async def reject_rule_change(change_id: str):
    """Owner rejects an adaptive rule change."""
    r = _get_redis()
    raw = r.hget(_PENDING_RULE_CHANGES_KEY, change_id)
    if not raw:
        raise HTTPException(status_code=404, detail="Rule change not found")
    change = json.loads(raw)
    r.hdel(_PENDING_RULE_CHANGES_KEY, change_id)
    _log_learning("adaptive_rule_rejected", {
        "action_type": change["action_type"],
        "suggested": change["suggested_level"],
    }, "negative")
    return {"message": f"Rule change rejected for {change['action_type']}"}


@app.get("/autonomy/exec-memory/stats")
async def get_exec_memory_stats():
    """Get execution memory statistics."""
    r = _get_redis()
    exec_data = r.lrange(_EXEC_MEMORY_KEY, -500, -1)
    type_stats: dict[str, dict] = {}
    for raw in exec_data:
        try:
            entry = json.loads(raw)
            atype = entry.get("action_type", "unknown")
            if atype not in type_stats:
                type_stats[atype] = {"total": 0, "success": 0, "fail": 0, "avg_score": 0, "scores": []}
            type_stats[atype]["total"] += 1
            score = entry.get("success_score", 0)
            type_stats[atype]["scores"].append(score)
            if score >= 0.5:
                type_stats[atype]["success"] += 1
            else:
                type_stats[atype]["fail"] += 1
        except json.JSONDecodeError:
            pass
    # Calculate averages and clean up
    result = {}
    for atype, stats in type_stats.items():
        result[atype] = {
            "total": stats["total"],
            "success": stats["success"],
            "fail": stats["fail"],
            "success_rate": round(stats["success"] / stats["total"] * 100, 1) if stats["total"] > 0 else 0,
            "avg_score": round(sum(stats["scores"]) / len(stats["scores"]), 2) if stats["scores"] else 0,
        }
    return {"total_records": len(exec_data), "by_type": result}


@app.get("/autonomy/followup-status/{user_id}")
async def get_followup_status(user_id: str):
    """Get follow-up usage status for a user."""
    r = _get_redis()
    today = datetime.utcnow().strftime("%Y-%m-%d")
    key = f"{_FOLLOWUP_COUNT_PREFIX}{user_id}:{today}"
    count = int(r.get(key) or 0)
    return {
        "user_id": user_id,
        "followups_today": count,
        "max_per_day": settings.max_followups_per_user_per_day,
        "remaining": max(0, settings.max_followups_per_user_per_day - count),
    }


# ═══════════════════════════════════════════════════════════════
# Self-Development Engine — Code Scanner, Improvement Detector,
# Patch Generator, Diff Viewer, Owner Approval, Safe Apply,
# Learning from Changes
# ═══════════════════════════════════════════════════════════════

_SELFDEV_PREFIX = f"{_AUTONOMY_PREFIX}selfdev:"
_SELFDEV_PATCHES_KEY = f"{_SELFDEV_PREFIX}patches"
_SELFDEV_HISTORY_KEY = f"{_SELFDEV_PREFIX}history"
_SELFDEV_SCAN_KEY = f"{_SELFDEV_PREFIX}last_scan"

# In-memory patch store (backed by Redis)
_selfdev_patches: list[dict] = []

# File extensions to scan
_SCAN_EXTENSIONS = {".py", ".yaml", ".yml", ".sh", ".json", ".toml"}
# Directories to scan (relative to project root inside container)
# Inside Docker: /app has the service code; also check mounted source if available
_SCAN_DIRS = ["."]
# Max file size to scan (50KB)
_SCAN_MAX_SIZE = 50_000


class SelfDevPatch(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:12])
    file_path: str
    issue_type: str  # duplicate_logic, unused_code, inefficiency, performance, bug, refactor
    description: str
    before_code: str
    after_code: str
    impact: str = ""
    confidence: float = 0.0
    status: str = "pending"  # pending / approved / rejected / applied / failed
    backup_id: Optional[str] = None
    scan_id: Optional[str] = None
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    applied_at: Optional[str] = None
    outcome: Optional[str] = None  # positive / negative / neutral (after apply)


class SelfDevScanResult(BaseModel):
    scan_id: str = Field(default_factory=lambda: str(uuid.uuid4())[:12])
    files_scanned: int = 0
    issues_found: int = 0
    patches_generated: int = 0
    summary: str = ""
    issues: list[dict] = Field(default_factory=list)
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


# ── STEP 1: Code Scanner ────────────────────────────────────

async def _scan_project_files() -> list[dict]:
    """Scan project files and collect code for analysis.
    Works inside Docker container — scans /app (own code) and
    /source if mounted (for cross-service scanning)."""
    import os
    files_content = []
    project_root = "/app"

    # Scan paths: own code + optional mounted source
    scan_roots = [project_root]
    # If /source is mounted (contains all services), scan it too
    if os.path.isdir("/source"):
        scan_roots.append("/source")

    for scan_root in scan_roots:
        for root, _dirs, filenames in os.walk(scan_root):
            # Skip __pycache__, .git, node_modules, .venv
            if any(skip in root for skip in ("__pycache__", ".git", "node_modules", ".venv")):
                continue
            for fname in filenames:
                ext = os.path.splitext(fname)[1]
                if ext not in _SCAN_EXTENSIONS:
                    continue
                fpath = os.path.join(root, fname)
                try:
                    fsize = os.path.getsize(fpath)
                    if fsize > _SCAN_MAX_SIZE:
                        continue
                    with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read()
                    rel_path = os.path.relpath(fpath, scan_root)
                    files_content.append({
                        "path": rel_path,
                        "content": content,
                        "size": fsize,
                        "lines": content.count("\n") + 1,
                    })
                except Exception:
                    continue
    return files_content


# ── STEP 2: Improvement Detector ────────────────────────────

async def _detect_improvements(files_content: list[dict]) -> list[dict]:
    """Use LLM to analyze code and detect improvements."""
    if not files_content:
        return []

    # Build a compact summary of files for analysis (limit context size)
    file_summaries = []
    total_chars = 0
    for f in files_content:
        # Only include Python files and limit total context to ~15K chars
        if not f["path"].endswith(".py"):
            continue
        content = f["content"][:4000] if len(f["content"]) > 4000 else f["content"]
        entry = f"### {f['path']} ({f['lines']} lines)\n```\n{content}\n```"
        if total_chars + len(entry) > 15000:
            break
        file_summaries.append(entry)
        total_chars += len(entry)

    if not file_summaries:
        return []

    code_block = "\n\n".join(file_summaries)

    prompt = f"""You are an expert code reviewer for a Python/FastAPI AI system.
Analyze the following codebase and identify concrete, actionable improvements.

Focus on:
1. DUPLICATE LOGIC — identical or near-identical code blocks across files
2. UNUSED CODE — functions, imports, variables that are never used
3. INEFFICIENCY — unnecessary loops, repeated API calls, missing caching
4. PERFORMANCE — slow operations, blocking calls in async code, N+1 queries
5. BUG RISKS — unhandled exceptions, race conditions, resource leaks
6. REFACTOR — complex functions that should be split, magic numbers, poor naming

For EACH issue found, respond in this exact JSON format (one per line in a JSON array):
[
  {{
    "file_path": "path/to/file.py",
    "issue_type": "duplicate_logic|unused_code|inefficiency|performance|bug|refactor",
    "description": "Clear explanation of the issue",
    "before_code": "exact code that needs changing (10-30 lines max)",
    "after_code": "improved version of the code",
    "impact": "What improves: speed/reliability/readability/security",
    "confidence": 0.0 to 1.0
  }}
]

RULES:
- Only suggest changes you are HIGHLY confident about
- before_code must be EXACT text from the file (copy-paste accuracy)
- after_code must be a drop-in replacement
- Maximum 10 issues per scan
- Skip trivial style-only changes
- Do NOT suggest adding comments or docstrings

Codebase:
{code_block}

Respond ONLY with the JSON array. No extra text."""

    try:
        # Use longer timeout for code analysis
        messages = [
            {"role": "system", "content": "You are a precise code analysis engine. Output valid JSON only."},
            {"role": "user", "content": prompt},
        ]
        async with httpx.AsyncClient(timeout=90.0) as client:
            resp = await client.post(
                f"{settings.llm_gateway_url}/generate",
                json={
                    "messages": messages,
                    "temperature": 0.2,
                    "caller": "autonomy-engine-selfdev",
                },
            )
            resp.raise_for_status()
            data = resp.json()
            raw = data.get("content", data.get("response", data.get("text", "")))

        raw = raw.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
            if raw.endswith("```"):
                raw = raw[:-3]
            raw = raw.strip()
        issues = json.loads(raw)
        if not isinstance(issues, list):
            issues = [issues]
        # Validate and filter
        valid_issues = []
        for issue in issues[:10]:
            if all(k in issue for k in ("file_path", "issue_type", "before_code", "after_code", "description")):
                issue.setdefault("confidence", 0.5)
                issue.setdefault("impact", "")
                valid_issues.append(issue)
        return valid_issues
    except (json.JSONDecodeError, Exception) as e:
        logger.error(f"Self-dev improvement detection failed: {e}")
        return []


# ── STEP 3: Patch Generator ─────────────────────────────────

def _create_patches_from_issues(issues: list[dict], scan_id: str) -> list[SelfDevPatch]:
    """Convert detected issues into reviewable patches."""
    patches = []
    for issue in issues:
        patch = SelfDevPatch(
            file_path=issue["file_path"],
            issue_type=issue.get("issue_type", "refactor"),
            description=issue["description"],
            before_code=issue["before_code"],
            after_code=issue["after_code"],
            impact=issue.get("impact", ""),
            confidence=float(issue.get("confidence", 0.5)),
            status="pending",
            scan_id=scan_id,
        )
        patches.append(patch)
    return patches


def _persist_patch(patch: SelfDevPatch):
    """Save a patch to Redis for durability."""
    r = _get_redis()
    r.hset(
        _SELFDEV_PATCHES_KEY,
        patch.id,
        json.dumps(patch.dict()),
    )


def _load_patches_from_redis() -> list[SelfDevPatch]:
    """Load all patches from Redis."""
    r = _get_redis()
    all_raw = r.hgetall(_SELFDEV_PATCHES_KEY)
    patches = []
    for raw in all_raw.values():
        try:
            patches.append(SelfDevPatch(**json.loads(raw)))
        except Exception:
            continue
    return sorted(patches, key=lambda p: p.created_at, reverse=True)


# ── STEP 4: Diff Viewer (uses existing sandbox) ─────────────

def _format_diff(patch: SelfDevPatch) -> str:
    """Generate a readable diff view for a patch."""
    diff = f"""═══ SELF-DEV PATCH: {patch.id} ═══
File: {patch.file_path}
Type: {patch.issue_type}
Confidence: {patch.confidence:.0%}

── Description ──
{patch.description}

── Impact ──
{patch.impact}

── BEFORE (current code) ──
{patch.before_code}

── AFTER (proposed change) ──
{patch.after_code}

Status: {patch.status.upper()}
Created: {patch.created_at}"""
    return diff


# ── STEP 5 & 6: Owner Approval + Safe Apply ─────────────────

async def _apply_patch_safe(patch: SelfDevPatch) -> dict:
    """Safely apply a patch: backup → verify → apply → test.
    Uses the existing backup system. Writes to /source (mounted volume)."""
    import os

    # Use /source (mounted project root) for writes, or /app if no mount
    project_root = "/source" if os.path.isdir("/source") else "/app"
    file_path = os.path.join(project_root, patch.file_path)

    # Verify file exists
    if not os.path.isfile(file_path):
        return {"success": False, "error": f"File not found: {patch.file_path}"}

    # Read current file content
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            current_content = f.read()
    except Exception as e:
        return {"success": False, "error": f"Cannot read file: {e}"}

    # Verify the before_code exists in the file
    if patch.before_code.strip() not in current_content:
        return {"success": False, "error": "before_code not found in file — file may have changed since scan"}

    # STEP 6a: Create backup using existing backup system
    backup_id = await _backup_state(
        f"Self-dev patch {patch.id}: {patch.issue_type} in {patch.file_path}",
        {
            "patch_id": patch.id,
            "file_path": patch.file_path,
            "original_content": current_content,
            "patch_description": patch.description,
        },
    )
    patch.backup_id = backup_id

    # STEP 6b: Apply the change
    try:
        new_content = current_content.replace(patch.before_code.strip(), patch.after_code.strip(), 1)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(new_content)
    except Exception as e:
        return {"success": False, "error": f"Write failed: {e}", "backup_id": backup_id}

    # STEP 6c: Syntax verification (for Python files)
    if patch.file_path.endswith(".py"):
        import subprocess
        try:
            result = subprocess.run(
                ["python3", "-c", f"import ast; ast.parse(open('{file_path}').read())"],
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode != 0:
                # Syntax error — rollback immediately
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(current_content)
                return {
                    "success": False,
                    "error": f"Syntax error after patch — rolled back: {result.stderr[:200]}",
                    "backup_id": backup_id,
                    "rolled_back": True,
                }
        except Exception as e:
            # Rollback on test failure
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(current_content)
            return {
                "success": False,
                "error": f"Syntax check failed — rolled back: {e}",
                "backup_id": backup_id,
                "rolled_back": True,
            }

    # Success
    patch.status = "applied"
    patch.applied_at = datetime.utcnow().isoformat()
    _persist_patch(patch)

    # Create sandbox audit trail using existing system
    sandbox = SandboxChange(
        suggestion_id=f"selfdev-{patch.id}",
        change_type=f"selfdev_{patch.issue_type}",
        description=f"Self-dev: {patch.description}",
        current_state=patch.before_code[:200],
        proposed_state=patch.after_code[:200],
        diff_summary=_format_diff(patch),
        status="applied",
        backup_id=backup_id,
    )
    _sandbox_changes.append(sandbox)

    # Log to learning system
    _log_learning("selfdev_patch_applied", {
        "patch_id": patch.id,
        "file": patch.file_path,
        "type": patch.issue_type,
        "backup_id": backup_id,
    }, "positive")

    return {
        "success": True,
        "backup_id": backup_id,
        "file": patch.file_path,
        "patch_id": patch.id,
    }


async def _rollback_patch(patch: SelfDevPatch) -> dict:
    """Rollback a previously applied patch using the backup system."""
    if not patch.backup_id:
        return {"success": False, "error": "No backup_id for this patch"}

    r = _get_redis()
    raw = r.get(f"{_BACKUP_PREFIX}{patch.backup_id}")
    if not raw:
        return {"success": False, "error": "Backup expired or not found"}

    backup = json.loads(raw)
    original_content = backup.get("state", {}).get("original_content")
    if not original_content:
        return {"success": False, "error": "Backup does not contain original file content"}

    import os
    file_path = os.path.join("/source" if os.path.isdir("/source") else "/app", patch.file_path)
    try:
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(original_content)
        patch.status = "failed"
        patch.outcome = "negative"
        _persist_patch(patch)

        _log_learning("selfdev_patch_rolled_back", {
            "patch_id": patch.id,
            "file": patch.file_path,
            "type": patch.issue_type,
            "backup_id": patch.backup_id,
        }, "negative")

        return {"success": True, "rolled_back": True, "file": patch.file_path}
    except Exception as e:
        return {"success": False, "error": f"Rollback write failed: {e}"}


# ── STEP 7: Learning from Changes ───────────────────────────

def _record_selfdev_history(patch_id: str, action: str, outcome: str, details: dict = None):
    """Track self-dev change history for learning."""
    r = _get_redis()
    entry = {
        "patch_id": patch_id,
        "action": action,  # applied / rejected / rolled_back / positive_outcome / negative_outcome
        "outcome": outcome,
        "details": details or {},
        "ts": datetime.utcnow().isoformat(),
    }
    r.rpush(_SELFDEV_HISTORY_KEY, json.dumps(entry))
    r.ltrim(_SELFDEV_HISTORY_KEY, -200, -1)


# ═══════════════════════════════════════════════════════════════
# Self-Development Engine — API Endpoints
# ═══════════════════════════════════════════════════════════════

@app.post("/autonomy/self-dev/scan")
async def selfdev_scan():
    """STEP 1+2+3: Full scan → detect improvements → generate patches."""
    try:
        # Step 1: Scan files
        files = await _scan_project_files()
        if not files:
            return {"scan_id": None, "error": "No files found to scan"}

        # Step 2: Detect improvements via LLM
        issues = await _detect_improvements(files)

        scan_id = str(uuid.uuid4())[:12]

        # Step 3: Generate patches
        patches = _create_patches_from_issues(issues, scan_id)

        # Persist patches
        for p in patches:
            _selfdev_patches.append(p)
            _persist_patch(p)

        # Save scan result
        scan_result = SelfDevScanResult(
            scan_id=scan_id,
            files_scanned=len(files),
            issues_found=len(issues),
            patches_generated=len(patches),
            summary=f"Scanned {len(files)} files, found {len(issues)} issues, generated {len(patches)} patches",
            issues=[{"id": p.id, "file": p.file_path, "type": p.issue_type, "desc": p.description[:100]} for p in patches],
        )

        r = _get_redis()
        r.setex(_SELFDEV_SCAN_KEY, 86400, json.dumps(scan_result.dict()))

        _record_selfdev_history(scan_id, "scan_completed", "neutral", {
            "files_scanned": len(files),
            "issues_found": len(issues),
            "patches": len(patches),
        })

        logger.info(f"Self-dev scan complete: {len(files)} files, {len(issues)} issues, {len(patches)} patches")

        return scan_result.dict()

    except Exception as e:
        logger.error(f"Self-dev scan failed: {e}")
        raise HTTPException(status_code=500, detail=f"Scan failed: {str(e)[:200]}")


@app.get("/autonomy/self-dev/patches")
async def selfdev_list_patches(status: Optional[str] = None):
    """List all self-dev patches, optionally filtered by status."""
    # Refresh from Redis
    patches = _load_patches_from_redis()
    if status:
        patches = [p for p in patches if p.status == status]
    return {
        "total": len(patches),
        "patches": [p.dict() for p in patches[:50]],
    }


@app.get("/autonomy/self-dev/patch/{patch_id}")
async def selfdev_get_patch(patch_id: str):
    """Get a specific patch with full diff view."""
    r = _get_redis()
    raw = r.hget(_SELFDEV_PATCHES_KEY, patch_id)
    if not raw:
        raise HTTPException(status_code=404, detail="Patch not found")
    patch = SelfDevPatch(**json.loads(raw))
    return {
        "patch": patch.dict(),
        "diff": _format_diff(patch),
    }


@app.post("/autonomy/self-dev/patch/{patch_id}/approve")
async def selfdev_approve_patch(patch_id: str):
    """Owner approves a patch — marks it ready for apply."""
    r = _get_redis()
    raw = r.hget(_SELFDEV_PATCHES_KEY, patch_id)
    if not raw:
        raise HTTPException(status_code=404, detail="Patch not found")

    patch = SelfDevPatch(**json.loads(raw))
    if patch.status != "pending":
        return {"error": f"Patch is already {patch.status}", "patch_id": patch_id}

    patch.status = "approved"
    _persist_patch(patch)

    _record_selfdev_history(patch_id, "approved", "positive", {
        "file": patch.file_path,
        "type": patch.issue_type,
    })

    _log_learning("selfdev_patch_approved", {
        "patch_id": patch_id,
        "file": patch.file_path,
        "type": patch.issue_type,
    }, "positive")

    return {"status": "approved", "patch_id": patch_id, "message": "Patch approved. Use /apply to apply it."}


@app.post("/autonomy/self-dev/patch/{patch_id}/reject")
async def selfdev_reject_patch(patch_id: str):
    """Owner rejects a patch."""
    r = _get_redis()
    raw = r.hget(_SELFDEV_PATCHES_KEY, patch_id)
    if not raw:
        raise HTTPException(status_code=404, detail="Patch not found")

    patch = SelfDevPatch(**json.loads(raw))
    patch.status = "rejected"
    _persist_patch(patch)

    _record_selfdev_history(patch_id, "rejected", "negative", {
        "file": patch.file_path,
        "type": patch.issue_type,
    })

    _log_learning("selfdev_patch_rejected", {
        "patch_id": patch_id,
        "file": patch.file_path,
        "type": patch.issue_type,
    }, "negative")

    return {"status": "rejected", "patch_id": patch_id}


@app.post("/autonomy/self-dev/patch/{patch_id}/apply")
async def selfdev_apply_patch(patch_id: str):
    """STEP 6: Safely apply an approved patch (backup → verify → apply → test)."""
    r = _get_redis()
    raw = r.hget(_SELFDEV_PATCHES_KEY, patch_id)
    if not raw:
        raise HTTPException(status_code=404, detail="Patch not found")

    patch = SelfDevPatch(**json.loads(raw))
    if patch.status not in ("approved",):
        return {"error": f"Patch must be 'approved' before applying (current: {patch.status})", "patch_id": patch_id}

    result = await _apply_patch_safe(patch)

    _record_selfdev_history(patch_id, "applied" if result["success"] else "apply_failed",
                            "positive" if result["success"] else "negative", result)

    return result


@app.post("/autonomy/self-dev/patch/{patch_id}/rollback")
async def selfdev_rollback_patch(patch_id: str):
    """Rollback a previously applied patch."""
    r = _get_redis()
    raw = r.hget(_SELFDEV_PATCHES_KEY, patch_id)
    if not raw:
        raise HTTPException(status_code=404, detail="Patch not found")

    patch = SelfDevPatch(**json.loads(raw))
    if patch.status != "applied":
        return {"error": f"Can only rollback applied patches (current: {patch.status})", "patch_id": patch_id}

    result = await _rollback_patch(patch)

    _record_selfdev_history(patch_id, "rolled_back" if result["success"] else "rollback_failed",
                            "negative", result)

    return result


@app.post("/autonomy/self-dev/patch/{patch_id}/outcome")
async def selfdev_record_outcome(patch_id: str, outcome: str = "positive"):
    """STEP 7: Record whether an applied patch had a positive or negative effect."""
    r = _get_redis()
    raw = r.hget(_SELFDEV_PATCHES_KEY, patch_id)
    if not raw:
        raise HTTPException(status_code=404, detail="Patch not found")

    patch = SelfDevPatch(**json.loads(raw))
    if patch.status != "applied":
        return {"error": "Can only record outcome for applied patches"}

    outcome = outcome.lower()
    if outcome not in ("positive", "negative", "neutral"):
        outcome = "neutral"

    patch.outcome = outcome
    _persist_patch(patch)

    _record_selfdev_history(patch_id, f"{outcome}_outcome", outcome, {
        "file": patch.file_path,
        "type": patch.issue_type,
    })

    _log_learning(f"selfdev_{outcome}_outcome", {
        "patch_id": patch_id,
        "file": patch.file_path,
        "type": patch.issue_type,
    }, outcome)

    # Record to execution memory for future confidence
    _record_execution_memory(
        f"selfdev_{patch.issue_type}",
        patch.description,
        outcome == "positive",
        1.0 if outcome == "positive" else 0.0,
    )

    return {"status": "recorded", "patch_id": patch_id, "outcome": outcome}


@app.get("/autonomy/self-dev/history")
async def selfdev_history(limit: int = 50):
    """STEP 7: Get self-development change history for learning."""
    r = _get_redis()
    raw_list = r.lrange(_SELFDEV_HISTORY_KEY, -limit, -1)
    history = []
    for raw in raw_list:
        try:
            history.append(json.loads(raw))
        except Exception:
            continue

    # Also compute stats
    patches = _load_patches_from_redis()
    stats = {
        "total_patches": len(patches),
        "pending": sum(1 for p in patches if p.status == "pending"),
        "approved": sum(1 for p in patches if p.status == "approved"),
        "applied": sum(1 for p in patches if p.status == "applied"),
        "rejected": sum(1 for p in patches if p.status == "rejected"),
        "failed": sum(1 for p in patches if p.status == "failed"),
        "positive_outcomes": sum(1 for p in patches if p.outcome == "positive"),
        "negative_outcomes": sum(1 for p in patches if p.outcome == "negative"),
    }

    return {"history": list(reversed(history)), "stats": stats}


# ═══════════════════════════════════════════════════════════════
# STRATEGIC PLANNING AGENT — Daily Analysis, Trend Detection,
# Missed Opportunities, Behavior Patterns, Action Plans
# ═══════════════════════════════════════════════════════════════

_STRATEGY_PREFIX = f"{_AUTONOMY_PREFIX}strategy:"
_STRATEGY_REPORTS_KEY = f"{_STRATEGY_PREFIX}reports"
_STRATEGY_LAST_RUN_KEY = f"{_STRATEGY_PREFIX}last_run"
_STRATEGY_INTERVAL_HOURS = 24


async def _strategic_planning_cycle():
    """Run strategic analysis once every 24 hours.
    Analyzes conversation data, usage patterns, quality scores,
    detects trends, missed opportunities, and generates action plans."""
    r = _get_redis()
    br = _get_brain_redis()

    # Check if 24h since last run
    last_run = r.get(_STRATEGY_LAST_RUN_KEY)
    if last_run:
        try:
            last_dt = datetime.fromisoformat(last_run)
            hours_since = (datetime.utcnow() - last_dt).total_seconds() / 3600
            if hours_since < _STRATEGY_INTERVAL_HOURS:
                return  # Not time yet
        except Exception:
            pass

    logger.info("Strategic Planning Agent: Starting daily analysis...")

    # ── Gather data from last 24h + 7 days ──
    now = datetime.utcnow()
    today = now.strftime("%Y-%m-%d")

    # 1. Conversation volume & patterns (from brain Redis)
    conv_keys = br.keys("fazle:conv:social-*")
    total_conversations = len(conv_keys) if conv_keys else 0

    # Analyze conversation content for patterns
    conv_summaries = []
    platform_counts = {}
    for key in (conv_keys or [])[-50:]:  # Last 50 conversations
        try:
            raw = br.get(key)
            if not raw:
                continue
            conv = json.loads(raw)
            msg_count = len(conv) if isinstance(conv, list) else 0
            # Extract platform from key format: fazle:conv:social-<platform>-<user>
            parts = key.split("-", 2)
            plat = parts[1] if len(parts) > 1 else "unknown"
            platform_counts[plat] = platform_counts.get(plat, 0) + 1
            conv_summaries.append({
                "platform": plat,
                "messages": msg_count,
                "last_msg": conv[-1].get("content", "")[:100] if isinstance(conv, list) and conv else "",
            })
        except Exception:
            continue

    # 2. Usage stats (from brain Redis — intelligence tuning data)
    usage_data = {}
    for d in range(7):
        day = (now - timedelta(days=d)).strftime("%Y-%m-%d")
        daily_key = f"fazle:intel:usage_daily:{day}"
        raw = br.hgetall(daily_key)
        if raw:
            usage_data[day] = raw

    # 3. Quality scores from governor
    quality_raw = br.lrange("fazle:governor:quality_scores", -20, -1)
    quality_scores = []
    for q in (quality_raw or []):
        try:
            quality_scores.append(json.loads(q))
        except Exception:
            continue

    # 4. Identity scores
    identity_raw = br.lrange("fazle:governor:identity_scores", -20, -1)
    identity_scores = []
    for i in (identity_raw or []):
        try:
            identity_scores.append(json.loads(i))
        except Exception:
            continue

    # 5. Drift alerts
    drift_raw = br.lrange("fazle:governor:drift_alerts", -10, -1)
    drift_alerts = []
    for d_a in (drift_raw or []):
        try:
            drift_alerts.append(json.loads(d_a))
        except Exception:
            continue

    # 6. Owner feedback
    feedback_raw = br.lrange("fazle:governor:owner_feedback", -10, -1)
    feedback_entries = []
    for f_e in (feedback_raw or []):
        try:
            feedback_entries.append(json.loads(f_e))
        except Exception:
            continue

    # ── Build analysis prompt ──
    analysis_data = {
        "total_conversations": total_conversations,
        "platform_distribution": platform_counts,
        "conversation_samples": conv_summaries[:10],
        "usage_stats_7d": usage_data,
        "quality_scores_recent": quality_scores[-10:],
        "identity_scores_recent": identity_scores[-10:],
        "drift_alerts": drift_alerts,
        "owner_feedback": feedback_entries,
        "analysis_date": today,
    }

    analysis_prompt = f"""You are the Strategic Planning Agent for Fazle AI — Azim's personal AI system.

Analyze the following system data from the last 24 hours and 7-day trends. Produce a strategic report.

DATA:
{json.dumps(analysis_data, indent=2, default=str)}

Produce your analysis in this JSON format:
{{
  "summary": "2-3 sentence executive summary of system state",
  "trends": [
    {{"trend": "description", "direction": "up/down/stable", "significance": "high/medium/low"}}
  ],
  "missed_opportunities": [
    {{"opportunity": "description", "potential_impact": "high/medium/low", "suggested_action": "what to do"}}
  ],
  "behavior_patterns": [
    {{"pattern": "description", "user_segment": "which users", "insight": "what this means"}}
  ],
  "action_plan": [
    {{"action": "specific action to take", "priority": "high/medium/low", "timeline": "immediate/this_week/this_month"}}
  ],
  "health_score": 0.0-1.0,
  "key_insight": "one most important insight for the owner"
}}"""

    try:
        messages = [
            {"role": "system", "content": "You are a strategic analyst. Respond ONLY with valid JSON."},
            {"role": "user", "content": analysis_prompt},
        ]
        result = await query_llm(messages)

        # Store the report
        report = {
            "report": result,
            "data_snapshot": {
                "total_conversations": total_conversations,
                "platforms": platform_counts,
                "usage_days": list(usage_data.keys()),
                "quality_avg": sum(q.get("score", 0) for q in quality_scores) / max(len(quality_scores), 1),
                "identity_avg": sum(i.get("score", 0) for i in identity_scores) / max(len(identity_scores), 1),
            },
            "ts": now.isoformat(),
        }

        # Store in autonomy Redis
        r.rpush(_STRATEGY_REPORTS_KEY, json.dumps(report, default=str))
        r.ltrim(_STRATEGY_REPORTS_KEY, -30, -1)
        r.set(_STRATEGY_LAST_RUN_KEY, now.isoformat())

        # Also store in brain Redis for memory_manager access
        br.rpush("fazle:strategy:reports", json.dumps(report, default=str))
        br.ltrim("fazle:strategy:reports", -30, -1)
        br.set("fazle:strategy:last_run", now.isoformat())

        logger.info(f"Strategic Planning Agent: Report generated — health={result.get('health_score', 'N/A')}")

        _log_learning("strategic_planning_report", {
            "health_score": result.get("health_score"),
            "trends_count": len(result.get("trends", [])),
            "actions_count": len(result.get("action_plan", [])),
        }, "positive")

    except Exception as e:
        logger.error(f"Strategic Planning Agent failed: {e}")
        _log_learning("strategic_planning_error", {"error": str(e)[:200]}, "negative")


@app.get("/strategy/report")
async def strategy_get_report(count: int = 1):
    """Get latest strategic planning reports."""
    r = _get_redis()
    raw_list = r.lrange(_STRATEGY_REPORTS_KEY, -count, -1)
    reports = []
    for raw in (raw_list or []):
        try:
            reports.append(json.loads(raw))
        except Exception:
            continue
    return {"reports": reports, "count": len(reports)}


@app.get("/strategy/insights")
async def strategy_get_insights():
    """Get the latest strategic insights summary."""
    r = _get_redis()
    # Get latest report
    raw_list = r.lrange(_STRATEGY_REPORTS_KEY, -1, -1)
    if not raw_list:
        return {"insights": None, "message": "No strategic reports generated yet. First report runs after 24h."}

    try:
        report = json.loads(raw_list[0])
        analysis = report.get("report", {})
        return {
            "key_insight": analysis.get("key_insight"),
            "health_score": analysis.get("health_score"),
            "trends": analysis.get("trends", []),
            "action_plan": analysis.get("action_plan", []),
            "missed_opportunities": analysis.get("missed_opportunities", []),
            "last_run": report.get("ts"),
        }
    except Exception:
        return {"insights": None, "message": "Error parsing latest report"}


@app.post("/strategy/trigger")
async def strategy_trigger():
    """Manually trigger strategic analysis (resets the 24h cooldown)."""
    r = _get_redis()
    r.delete(_STRATEGY_LAST_RUN_KEY)
    asyncio.create_task(_strategic_planning_cycle())
    return {"triggered": True, "message": "Strategic analysis started"}


# ═══════════════════════════════════════════════════════════════
# SYSTEM GOVERNOR v2 — Identity Consistency, Quality Scoring,
# Auto-Correction, Patch Impact, Stability, Safe Mode,
# Owner Feedback, Dashboard
# ═══════════════════════════════════════════════════════════════

_GOV_PREFIX = f"{_AUTONOMY_PREFIX}governor:"
_GOV_STABILITY_KEY = f"{_GOV_PREFIX}stability"
_GOV_SAFE_MODE_KEY = f"{_GOV_PREFIX}safe_mode"
_GOV_FEEDBACK_LAST_KEY = f"{_GOV_PREFIX}feedback_last"
_GOV_CORRECTION_LAST_KEY = f"{_GOV_PREFIX}correction_last"

# Thresholds
_GOV_STABILITY_THRESHOLD = 40     # Below this → safe mode ON
_GOV_IDENTITY_THRESHOLD = 0.5     # Below this → safe mode ON
_GOV_STABILITY_RECOVER = 55       # Above this → safe mode OFF
_GOV_IDENTITY_RECOVER = 0.65      # Above this → safe mode OFF
_GOV_FEEDBACK_INTERVAL = 3600 * 6 # Ask owner every 6 hours
_GOV_CORRECTION_COOLDOWN = 3600   # 1 hour between auto-corrections

# ── Brain-Redis governor keys (read cross-DB) ───────────────
_BR_GOV_QUALITY = "fazle:governor:quality_scores"
_BR_GOV_IDENTITY = "fazle:governor:identity_scores"
_BR_GOV_ERRORS = "fazle:governor:errors"
_BR_GOV_SAFE_MODE = "fazle:governor:safe_mode"
_BR_GOV_DRIFT_ALERTS = "fazle:governor:drift_alerts"
_BR_GOV_FEEDBACK = "fazle:governor:feedback"
_BR_GOV_PATCH_BASELINES = "fazle:governor:patch_baselines"


async def _governor_calculate_stability() -> dict:
    """STEP 7: Calculate stability_score (0-100) from all sub-scores."""
    br = _get_brain_redis()
    r = _get_redis()

    # Identity alignment
    identity_raw = br.lrange(_BR_GOV_IDENTITY, -50, -1)
    identity_scores = []
    for raw in identity_raw:
        try:
            identity_scores.append(json.loads(raw).get("score", 0.5))
        except Exception:
            pass
    avg_identity = sum(identity_scores) / len(identity_scores) if identity_scores else 0.7

    # Quality scores
    quality_raw = br.lrange(_BR_GOV_QUALITY, -50, -1)
    quality_scores = []
    for raw in quality_raw:
        try:
            quality_scores.append(json.loads(raw).get("score", 0.5))
        except Exception:
            pass
    avg_quality = sum(quality_scores) / len(quality_scores) if quality_scores else 0.7

    # Error rate (errors in last hour)
    errors_raw = br.lrange(_BR_GOV_ERRORS, -50, -1)
    now = datetime.utcnow()
    recent_errors = 0
    for raw in errors_raw:
        try:
            entry = json.loads(raw)
            ts = datetime.fromisoformat(entry.get("ts", "2020-01-01"))
            if (now - ts).total_seconds() < 3600:
                recent_errors += 1
        except Exception:
            pass
    error_factor = max(0.0, 1.0 - (recent_errors / 20))

    # Drift blocks from learning log
    drift_raw = r.lrange(_LEARNING_KEY, -100, -1)
    drift_blocks = 0
    for raw in drift_raw:
        try:
            entry = json.loads(raw)
            if entry.get("event_type") == "drift_blocked":
                drift_blocks += 1
        except Exception:
            pass
    drift_factor = max(0.0, 1.0 - (drift_blocks / 10))

    stability = int(
        (avg_identity * 30) +
        (avg_quality * 30) +
        (error_factor * 20) +
        (drift_factor * 20)
    )
    stability = max(0, min(100, stability))

    result = {
        "stability_score": stability,
        "identity_alignment": round(avg_identity, 3),
        "quality_score": round(avg_quality, 3),
        "error_rate": recent_errors,
        "drift_blocks": drift_blocks,
        "error_factor": round(error_factor, 3),
        "drift_factor": round(drift_factor, 3),
        "identity_samples": len(identity_scores),
        "quality_samples": len(quality_scores),
        "ts": now.isoformat(),
    }
    r.set(_GOV_STABILITY_KEY, json.dumps(result))
    return result


async def _governor_check_safe_mode(stability_data: dict) -> bool:
    """STEP 8: Activate/deactivate safe mode based on stability."""
    r = _get_redis()
    br = _get_brain_redis()

    stability = stability_data.get("stability_score", 100)
    identity = stability_data.get("identity_alignment", 1.0)
    currently_safe = r.get(_GOV_SAFE_MODE_KEY) == "1"

    should_activate = stability < _GOV_STABILITY_THRESHOLD or identity < _GOV_IDENTITY_THRESHOLD
    can_deactivate = stability >= _GOV_STABILITY_RECOVER and identity >= _GOV_IDENTITY_RECOVER

    if should_activate and not currently_safe:
        r.set(_GOV_SAFE_MODE_KEY, "1")
        br.set(_BR_GOV_SAFE_MODE, "1")
        settings.auto_improve_enabled = False

        reason = f"stability={stability}, identity={identity:.2f}"
        _log_learning("governor_safe_mode_on", {"stability": stability, "identity": round(identity, 3), "reason": reason}, "negative")
        logger.warning(f"Governor safe mode ACTIVATED: {reason}")

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                await client.post(
                    f"{settings.brain_url}/chat/owner",
                    json={
                        "message": (
                            f"⚠️ [Governor Safe Mode ACTIVATED]\n"
                            f"স্থিতিশীলতা: {stability}/100\n"
                            f"পরিচয় মিল: {identity:.0%}\n\n"
                            f"Auto-execution ও auto-learning বন্ধ করা হয়েছে।"
                        ),
                        "sender_id": "governor",
                        "platform": "system",
                    },
                )
        except Exception:
            pass
        return True

    elif currently_safe and can_deactivate:
        r.set(_GOV_SAFE_MODE_KEY, "0")
        br.set(_BR_GOV_SAFE_MODE, "0")
        settings.auto_improve_enabled = True
        _log_learning("governor_safe_mode_off", {"stability": stability, "identity": round(identity, 3)}, "positive")
        logger.info(f"Governor safe mode deactivated: stability={stability}, identity={identity:.2f}")

    return r.get(_GOV_SAFE_MODE_KEY) == "1"


async def _governor_auto_correction():
    """STEP 5: Repeated low quality → trigger prompt/tone adjustment."""
    r = _get_redis()
    br = _get_brain_redis()

    # Cooldown check
    last_correction = r.get(_GOV_CORRECTION_LAST_KEY)
    now = datetime.utcnow()
    if last_correction:
        try:
            if (now - datetime.fromisoformat(last_correction)).total_seconds() < _GOV_CORRECTION_COOLDOWN:
                return
        except Exception:
            pass

    quality_raw = br.lrange(_BR_GOV_QUALITY, -20, -1)
    if len(quality_raw) < 10:
        return

    scores = []
    for raw in quality_raw:
        try:
            scores.append(json.loads(raw).get("score", 0.5))
        except Exception:
            pass
    if not scores:
        return

    recent_avg = sum(scores[-5:]) / len(scores[-5:])
    if recent_avg >= 0.5:
        return

    # Trigger correction via learning engine
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            await client.post(
                f"{settings.learning_engine_url}/learn",
                json={
                    "transcript": (
                        f"[GOVERNOR AUTO-CORRECTION] Recent quality avg: {recent_avg:.2f}. "
                        f"Improve: more relevant, accurate, identity-aligned responses. "
                        f"Stay consistent with Azim's personality and knowledge."
                    ),
                    "user": "governor",
                    "conversation_id": "governor-correction",
                },
            )
        r.set(_GOV_CORRECTION_LAST_KEY, now.isoformat())
        _log_learning("governor_auto_correction", {
            "recent_avg": round(recent_avg, 3),
            "action": "learning_engine_adjustment",
        }, "neutral")
        logger.info(f"Governor auto-correction triggered: recent_avg={recent_avg:.2f}")
    except Exception as e:
        logger.debug(f"Governor auto-correction failed: {e}")


async def _governor_patch_impact():
    """STEP 6: Compare quality before vs after patches; rollback if degraded."""
    br = _get_brain_redis()
    r = _get_redis()

    patches_raw = r.hgetall(_SELFDEV_PATCHES_KEY)
    now = datetime.utcnow()

    for patch_id_bytes, raw in patches_raw.items():
        try:
            patch_id = patch_id_bytes if isinstance(patch_id_bytes, str) else patch_id_bytes.decode()
            patch = json.loads(raw)
            if patch.get("status") != "applied" or patch.get("outcome"):
                continue
            applied_at = patch.get("applied_at", "")
            if not applied_at:
                continue

            applied_dt = datetime.fromisoformat(applied_at)
            hours_since = (now - applied_dt).total_seconds() / 3600
            if hours_since < 1:
                continue

            baseline_raw = br.hget(_BR_GOV_PATCH_BASELINES, patch_id)
            if not baseline_raw:
                continue
            baseline = json.loads(baseline_raw)
            baseline_quality = baseline.get("avg_quality", 0.7)

            # Quality since patch
            quality_raw = br.lrange(_BR_GOV_QUALITY, -30, -1)
            post_scores = []
            for qr in quality_raw:
                try:
                    entry = json.loads(qr)
                    ts = datetime.fromisoformat(entry.get("ts", "2020-01-01"))
                    if ts >= applied_dt:
                        post_scores.append(entry.get("score", 0.5))
                except Exception:
                    pass

            if len(post_scores) < 5:
                continue

            post_avg = sum(post_scores) / len(post_scores)

            if post_avg < baseline_quality - 0.15:
                logger.warning(f"Governor: Patch {patch_id} degraded quality ({baseline_quality:.2f} → {post_avg:.2f})")
                patch_obj = SelfDevPatch(**{k: v for k, v in patch.items() if k in SelfDevPatch.model_fields})
                await _rollback_patch(patch_obj)
                _log_learning("governor_patch_rollback", {
                    "patch_id": patch_id,
                    "baseline_quality": round(baseline_quality, 3),
                    "post_quality": round(post_avg, 3),
                }, "negative")
                try:
                    async with httpx.AsyncClient(timeout=10.0) as client:
                        await client.post(
                            f"{settings.brain_url}/chat/owner",
                            json={
                                "message": (
                                    f"⚠️ [Governor Patch Rollback]\n"
                                    f"Patch {patch_id}: quality drop\n"
                                    f"Before: {baseline_quality:.0%} → After: {post_avg:.0%}\n"
                                    f"Auto-rollback applied."
                                ),
                                "sender_id": "governor",
                                "platform": "system",
                            },
                        )
                except Exception:
                    pass
            elif hours_since >= 4:
                outcome = "positive" if post_avg >= baseline_quality else "neutral"
                patch["outcome"] = outcome
                r.hset(_SELFDEV_PATCHES_KEY, patch_id, json.dumps(patch))
                _record_selfdev_history(patch_id, f"{outcome}_outcome_auto", outcome)

        except Exception as e:
            logger.debug(f"Governor patch impact check error: {e}")


async def _governor_owner_feedback():
    """STEP 9: Periodically ask owner for accuracy feedback."""
    r = _get_redis()
    now = datetime.utcnow()

    last_feedback = r.get(_GOV_FEEDBACK_LAST_KEY)
    if last_feedback:
        try:
            if (now - datetime.fromisoformat(last_feedback)).total_seconds() < _GOV_FEEDBACK_INTERVAL:
                return
        except Exception:
            pass

    stability_raw = r.get(_GOV_STABILITY_KEY)
    stability = json.loads(stability_raw) if stability_raw else {}

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            await client.post(
                f"{settings.brain_url}/chat/owner",
                json={
                    "message": (
                        f"🔍 [Governor Feedback]\n"
                        f"আমার উত্তরগুলো কি ঠিক হচ্ছে?\n\n"
                        f"স্থিতিশীলতা: {stability.get('stability_score', 'N/A')}/100\n"
                        f"পরিচয় মিল: {stability.get('identity_alignment', 'N/A')}\n"
                        f"মান: {stability.get('quality_score', 'N/A')}\n\n"
                        f"আপনার মতামত জানান (ভালো/খারাপ/পরামর্শ)"
                    ),
                    "sender_id": "governor",
                    "platform": "system",
                },
            )
        r.set(_GOV_FEEDBACK_LAST_KEY, now.isoformat())
    except Exception:
        pass


async def _governor_run_cycle():
    """Run all governor checks in sequence (called from monitor loop)."""
    try:
        stability = await _governor_calculate_stability()
        await _governor_check_safe_mode(stability)
        await _governor_auto_correction()
        await _governor_patch_impact()
        await _governor_owner_feedback()
        logger.info(f"Governor cycle: stability={stability.get('stability_score', 'N/A')}")
    except Exception as e:
        logger.error(f"Governor cycle error: {e}")


# ── Governor v2 API Endpoints ────────────────────────────────

@app.get("/governor/dashboard")
async def governor_dashboard():
    """STEP 10: Expose all governor scores and alerts."""
    r = _get_redis()
    br = _get_brain_redis()

    stability_raw = r.get(_GOV_STABILITY_KEY)
    stability = json.loads(stability_raw) if stability_raw else {}
    safe_mode = r.get(_GOV_SAFE_MODE_KEY) == "1"

    quality_raw = br.lrange(_BR_GOV_QUALITY, -20, -1)
    quality_scores = []
    for raw in quality_raw:
        try:
            quality_scores.append(json.loads(raw))
        except Exception:
            pass

    identity_raw = br.lrange(_BR_GOV_IDENTITY, -20, -1)
    identity_scores = []
    for raw in identity_raw:
        try:
            identity_scores.append(json.loads(raw))
        except Exception:
            pass

    errors_raw = br.lrange(_BR_GOV_ERRORS, -20, -1)
    errors = []
    for raw in errors_raw:
        try:
            errors.append(json.loads(raw))
        except Exception:
            pass

    drift_raw = br.lrange(_BR_GOV_DRIFT_ALERTS, -10, -1)
    drift_alerts = []
    for raw in drift_raw:
        try:
            drift_alerts.append(json.loads(raw))
        except Exception:
            pass

    feedback_raw = br.lrange(_BR_GOV_FEEDBACK, -10, -1)
    feedback = []
    for raw in feedback_raw:
        try:
            feedback.append(json.loads(raw))
        except Exception:
            pass

    return {
        "stability": stability,
        "safe_mode": safe_mode,
        "auto_improve_enabled": settings.auto_improve_enabled,
        "recent_quality_scores": list(reversed(quality_scores)),
        "recent_identity_scores": list(reversed(identity_scores)),
        "recent_errors": list(reversed(errors)),
        "drift_alerts": list(reversed(drift_alerts)),
        "owner_feedback": list(reversed(feedback)),
        "intelligence_tuning": _get_intel_stats_from_brain(br),
    }


def _get_intel_stats_from_brain(br) -> dict:
    """Pull Intelligence Tuning Layer usage stats from brain Redis."""
    try:
        from datetime import datetime as _dt
        today = _dt.utcnow().strftime("%Y-%m-%d")
        daily_key = f"fazle:intel:usage_daily:{today}"
        raw = br.hgetall(daily_key)
        owner_priority = br.exists("fazle:intel:owner_priority") == 1
        return {"today_usage": raw or {}, "owner_priority_active": owner_priority}
    except Exception:
        return {}


@app.get("/governor/stability")
async def governor_stability():
    """Get current stability score."""
    r = _get_redis()
    raw = r.get(_GOV_STABILITY_KEY)
    if raw:
        return json.loads(raw)
    return await _governor_calculate_stability()


@app.post("/governor/safe-mode")
async def governor_safe_mode_toggle(active: bool = True):
    """Manually toggle safe mode."""
    r = _get_redis()
    br = _get_brain_redis()
    r.set(_GOV_SAFE_MODE_KEY, "1" if active else "0")
    br.set(_BR_GOV_SAFE_MODE, "1" if active else "0")
    settings.auto_improve_enabled = not active
    _log_learning("governor_safe_mode_manual", {"active": active}, "neutral")
    return {"safe_mode": active, "auto_improve_enabled": settings.auto_improve_enabled}


@app.post("/governor/validate-learning")
async def governor_validate_learning(data: dict):
    """STEP 2: Validate new knowledge against azim_profile before storing."""
    br = _get_brain_redis()
    new_knowledge = data.get("knowledge", "")
    field = data.get("field", "")
    if not new_knowledge:
        return {"valid": True, "reason": "empty"}

    profile_raw = br.hgetall("fazle:azim:profile")
    if not profile_raw:
        return {"valid": True, "reason": "no_profile"}

    profile_str = "; ".join(
        f"{k if isinstance(k, str) else k.decode()}={v if isinstance(v, str) else v.decode()}"
        for k, v in profile_raw.items()
    )

    prompt = (
        f"Check if new knowledge contradicts existing owner profile.\n"
        f"Profile: {profile_str}\n"
        f"New knowledge (field={field}): {new_knowledge}\n\n"
        f'Return JSON: {{"valid": true/false, "reason": "brief explanation"}}'
    )

    try:
        result = await _query_llm(prompt, caller="governor-validate")
        parsed = json.loads(result)
        is_valid = parsed.get("valid", True)
        reason = parsed.get("reason", "")
        if not is_valid:
            _log_learning("governor_learning_blocked", {
                "field": field, "knowledge": new_knowledge[:200], "reason": reason,
            }, "negative")
        return {"valid": is_valid, "reason": reason}
    except Exception:
        return {"valid": True, "reason": "validation_error_passthrough"}


@app.post("/governor/validate-multimodal")
async def governor_validate_multimodal(data: dict):
    """STEP 3: Validate multimodal extraction confidence."""
    extracted_text = data.get("extracted_text", "")
    media_type = data.get("media_type", "image")
    confidence = data.get("confidence", 0.5)

    is_reliable = True
    issues = []

    if media_type == "image":
        if not extracted_text or len(extracted_text.strip()) < 5:
            is_reliable = False
            issues.append("extracted_text too short or empty")
        if confidence < 0.4:
            is_reliable = False
            issues.append(f"low OCR confidence: {confidence}")
    elif media_type == "audio":
        if not extracted_text or len(extracted_text.strip()) < 3:
            is_reliable = False
            issues.append("transcript too short")
        if confidence < 0.3:
            is_reliable = False
            issues.append(f"low transcription confidence: {confidence}")

    if not is_reliable:
        br = _get_brain_redis()
        entry = json.dumps({
            "alert": f"Unreliable {media_type}: {'; '.join(issues)}",
            "ts": datetime.utcnow().isoformat(),
        })
        br.rpush(_BR_GOV_DRIFT_ALERTS, entry)
        br.ltrim(_BR_GOV_DRIFT_ALERTS, -50, -1)

    return {"reliable": is_reliable, "issues": issues, "confidence": confidence}


@app.post("/governor/feedback")
async def governor_submit_feedback(data: dict):
    """STEP 9: Store owner feedback and adjust scores."""
    br = _get_brain_redis()
    feedback_text = data.get("feedback", "")
    score = data.get("score", 0.0)

    if not feedback_text:
        return {"error": "no feedback provided"}

    entry = json.dumps({
        "feedback": feedback_text[:500],
        "score": score,
        "ts": datetime.utcnow().isoformat(),
    })
    br.rpush(_BR_GOV_FEEDBACK, entry)
    br.ltrim(_BR_GOV_FEEDBACK, -50, -1)

    # If negative feedback, push low quality score
    if score < 0 or any(w in feedback_text.lower() for w in ["খারাপ", "bad", "wrong", "ভুল"]):
        q_entry = json.dumps({
            "score": 0.3, "meta": {"source": "owner_feedback"},
            "ts": datetime.utcnow().isoformat(),
        })
        br.rpush(_BR_GOV_QUALITY, q_entry)
        br.ltrim(_BR_GOV_QUALITY, -100, -1)

    _log_learning("governor_owner_feedback", {
        "feedback": feedback_text[:200], "score": score,
    }, "positive" if score > 0 else "negative")

    return {"stored": True}
