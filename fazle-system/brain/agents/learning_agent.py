# ============================================================
# Learning Agent — Handles learning, memory storage, and corrections
# Coordinates with learning engine + memory for knowledge evolution
# ============================================================
import logging
import httpx
from .base import BaseAgent, AgentContext, AgentResult
from .identity_core import IdentityProfile

logger = logging.getLogger("fazle-agents.learning")

_LEARNING_KEYWORDS = frozenset([
    "remember", "forget", "learn", "correct", "correction",
    "মনে রাখো", "শিখো", "ভুল", "ঠিক করো",
    "save", "store", "training", "preference",
    "instruction", "rule",
])


class LearningAgent(BaseAgent):
    """Handles learning from conversations, corrections, and memory management."""

    name = "learning"
    description = "Learning, memory storage, correction processing, and knowledge evolution"

    def __init__(
        self,
        learning_engine_url: str,
        memory_url: str,
        identity: IdentityProfile,
    ):
        self.learning_engine_url = learning_engine_url
        self.memory_url = memory_url
        self.identity = identity

    async def can_handle(self, ctx: AgentContext) -> bool:
        """Learning agent handles memory/learning keywords or correction intents."""
        msg_lower = ctx.message.lower()
        if any(kw in msg_lower for kw in _LEARNING_KEYWORDS):
            return True
        intent = ctx.metadata.get("detected_intent")
        return intent in (
            "correction_learning", "set_permanent_memory",
            "set_instruction", "set_preference",
        )

    async def execute(self, ctx: AgentContext) -> AgentResult:
        """Process learning task."""
        try:
            intent = ctx.metadata.get("detected_intent", "learn")
            result = {}

            if intent == "correction_learning":
                result = await self._process_correction(ctx)
            elif intent == "set_permanent_memory":
                result = await self._store_permanent(ctx)
            elif intent in ("set_instruction", "set_preference"):
                result = await self._store_instruction(ctx)
            else:
                # General learning — store conversation for future training
                result = await self._learn_from_conversation(ctx)

            ctx.metadata["learning_result"] = result
            ctx.metadata["identity_enforced"] = True

            return AgentResult(
                content=result,
                metadata={"agent": self.name, "intent": intent},
            )
        except Exception as e:
            logger.error(f"Learning agent error: {e}")
            return AgentResult(error=str(e))

    async def learn_async(
        self,
        transcript: str,
        user_name: str,
        conversation_id: str,
    ) -> None:
        """Fire-and-forget learning from a conversation (called by strategy agent)."""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                await client.post(
                    f"{self.learning_engine_url}/learn",
                    json={
                        "transcript": transcript,
                        "user": user_name,
                        "conversation_id": conversation_id,
                    },
                )
        except Exception:
            pass  # Non-critical

    async def store_memories(
        self,
        updates: list[dict],
        user_id: str | None = None,
        user_name: str = "Azim",
    ) -> None:
        """Store memory updates via memory service."""
        for update in updates:
            body = {
                "type": update.get("type", "general"),
                "user": user_name,
                "content": update.get("content", update),
                "text": update.get("text", str(update.get("content", ""))),
            }
            if user_id:
                body["user_id"] = user_id
            try:
                async with httpx.AsyncClient(timeout=5.0) as client:
                    await client.post(f"{self.memory_url}/store", json=body)
            except Exception as e:
                logger.debug(f"Memory store failed: {e}")

    async def _process_correction(self, ctx: AgentContext) -> dict:
        """Process owner correction as training data."""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(
                    f"{self.memory_url}/store",
                    json={
                        "type": "knowledge",
                        "user": "Azim",
                        "user_id": "owner",
                        "content": {
                            "kind": "owner_training",
                            "correction": ctx.message,
                            "context": ctx.metadata.get("original_context", ""),
                        },
                        "text": f"Owner correction: {ctx.message}",
                    },
                )
                return {"stored": resp.status_code == 200}
        except Exception as e:
            return {"error": str(e)}

    async def _store_permanent(self, ctx: AgentContext) -> dict:
        """Store a permanent memory."""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(
                    f"{self.memory_url}/store",
                    json={
                        "type": "personal",
                        "user": ctx.user_name,
                        "user_id": ctx.user_id or "owner",
                        "content": {"fact": ctx.message},
                        "text": ctx.message,
                    },
                )
                return {"stored": resp.status_code == 200}
        except Exception as e:
            return {"error": str(e)}

    async def _store_instruction(self, ctx: AgentContext) -> dict:
        """Store owner instruction (delegated to memory_manager by caller)."""
        return {
            "action": "store_instruction",
            "message": ctx.message,
            "params": ctx.metadata.get("params", {}),
        }

    async def _learn_from_conversation(self, ctx: AgentContext) -> dict:
        """General learning from conversation context."""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                await client.post(
                    f"{self.learning_engine_url}/learn",
                    json={
                        "transcript": ctx.message,
                        "user": ctx.user_name,
                        "conversation_id": ctx.conversation_id or "",
                    },
                )
                return {"learned": True}
        except Exception:
            return {"learned": False}
