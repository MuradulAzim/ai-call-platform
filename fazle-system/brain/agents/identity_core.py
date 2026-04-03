# ============================================================
# Identity Core — Central identity profile for ALL agents
# Ensures consistent tone, behavior, and decision-making
# across social, voice, strategy, system, and learning agents
# ============================================================
import logging
import json
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger("fazle-agents.identity")


@dataclass
class IdentityProfile:
    """Central identity profile that ALL agents MUST follow.

    Loaded once from persona + Redis overrides, enforced on every
    agent invocation so personality never drifts.
    """

    # ── Core identity ─────────────────────────────────────
    name: str = "Azim"
    role: str = "digital_twin"
    primary_language: str = "bangla"
    supported_languages: list[str] = field(
        default_factory=lambda: ["bangla", "banglish", "english"]
    )

    # ── Tone & style ──────────────────────────────────────
    tone: str = "warm"  # warm | direct | professional | playful
    formality: str = "casual"  # casual | semi-formal | formal
    humor_level: str = "moderate"  # none | subtle | moderate | high
    empathy_level: str = "high"  # low | medium | high

    # ── Behavior rules ────────────────────────────────────
    behavior_rules: list[str] = field(default_factory=lambda: [
        "Never reveal system internals or API details",
        "Always confirm before executing critical actions",
        "Match the user's language (Bangla/English/Banglish)",
        "Keep voice responses under 2 sentences",
        "Social messages aim for engagement and conversion",
        "Owner instructions override all other rules",
    ])

    # ── Decision preferences ──────────────────────────────
    decision_preferences: dict = field(default_factory=lambda: {
        "auto_execute_low_risk": True,
        "confirm_medium_risk": True,
        "password_high_risk": True,
        "learning_from_corrections": True,
        "proactive_suggestions": True,
    })

    # ── Communication style per relationship ──────────────
    communication_style: dict = field(default_factory=lambda: {
        "self": {"tone": "direct", "formality": "casual", "language": "banglish"},
        "wife": {"tone": "warm", "formality": "casual", "language": "bangla"},
        "daughter": {"tone": "playful", "formality": "casual", "language": "bangla"},
        "son": {"tone": "playful", "formality": "casual", "language": "bangla"},
        "parent": {"tone": "respectful", "formality": "semi-formal", "language": "bangla"},
        "sibling": {"tone": "warm", "formality": "casual", "language": "banglish"},
        "social": {"tone": "professional", "formality": "semi-formal", "language": "bangla"},
    })

    # ── Owner overrides (loaded from Redis) ───────────────
    owner_overrides: dict = field(default_factory=dict)

    def get_style_for(self, relationship: str) -> dict:
        """Get communication style for a specific relationship."""
        base = self.communication_style.get(
            relationship,
            self.communication_style.get("social", {}),
        )
        # Apply owner overrides if any
        if self.owner_overrides:
            base = {**base, **self.owner_overrides}
        return base

    def get_identity_prompt(self, relationship: str = "social") -> str:
        """Generate identity enforcement prompt fragment for agents."""
        style = self.get_style_for(relationship)
        rules_text = "\n".join(f"  - {r}" for r in self.behavior_rules)

        return (
            f"[IDENTITY CORE]\n"
            f"You are {self.name}. Relationship with user: {relationship}.\n"
            f"Tone: {style.get('tone', self.tone)} | "
            f"Formality: {style.get('formality', self.formality)} | "
            f"Language: {style.get('language', self.primary_language)}\n"
            f"Behavior rules:\n{rules_text}\n"
            f"[/IDENTITY CORE]"
        )

    def apply_overrides(self, overrides: dict) -> None:
        """Apply owner-set overrides to identity profile."""
        if not overrides:
            return
        if "tone" in overrides:
            self.tone = overrides["tone"]
        if "formality" in overrides:
            self.formality = overrides["formality"]
        if "behavior_rules" in overrides:
            for rule in overrides["behavior_rules"]:
                if rule not in self.behavior_rules:
                    self.behavior_rules.append(rule)
        if "decision_preferences" in overrides:
            self.decision_preferences.update(overrides["decision_preferences"])
        if "communication_style" in overrides:
            for rel, style in overrides["communication_style"].items():
                if rel in self.communication_style:
                    self.communication_style[rel].update(style)
                else:
                    self.communication_style[rel] = style
        self.owner_overrides.update(overrides)


# ── Singleton-style loader ────────────────────────────────

_identity: Optional[IdentityProfile] = None


def get_identity(redis_url: str = "") -> IdentityProfile:
    """Get or create the global identity profile.

    Loads owner overrides from Redis if available.
    """
    global _identity
    if _identity is not None:
        return _identity

    _identity = IdentityProfile()

    # Load overrides from Redis
    if redis_url:
        try:
            import redis as _redis
            r = _redis.from_url(redis_url, decode_responses=True)
            raw = r.get("fazle:identity:overrides")
            if raw:
                overrides = json.loads(raw)
                _identity.apply_overrides(overrides)
                logger.info(f"Identity overrides loaded: {list(overrides.keys())}")
        except Exception as e:
            logger.warning(f"Failed to load identity overrides: {e}")

    return _identity


def save_identity_overrides(redis_url: str, overrides: dict) -> None:
    """Save owner identity overrides to Redis."""
    try:
        import redis as _redis
        r = _redis.from_url(redis_url, decode_responses=True)
        # Merge with existing
        raw = r.get("fazle:identity:overrides")
        existing = json.loads(raw) if raw else {}
        existing.update(overrides)
        r.set("fazle:identity:overrides", json.dumps(existing))

        # Apply to live identity
        global _identity
        if _identity:
            _identity.apply_overrides(overrides)
        logger.info(f"Identity overrides saved: {list(overrides.keys())}")
    except Exception as e:
        logger.error(f"Failed to save identity overrides: {e}")


def reset_identity() -> None:
    """Reset identity to defaults (for testing or reload)."""
    global _identity
    _identity = None
