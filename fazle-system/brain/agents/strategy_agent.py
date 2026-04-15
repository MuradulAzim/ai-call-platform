# ============================================================
# Strategy Agent — Central decision maker and coordinator
# Receives context → decides action → assigns to domain agents
# Orchestrates: social, voice, system, learning agents
# ============================================================
import asyncio
import logging
from enum import Enum
from typing import Optional

from .base import AgentContext, AgentResult
from .identity_core import IdentityProfile

logger = logging.getLogger("fazle-agents.strategy")


class DomainRoute(str, Enum):
    """High-level domain routing (ABOVE utility-level routing)."""
    SOCIAL = "social"          # Social media interaction
    VOICE = "voice"            # Voice call interaction
    OWNER = "owner"            # Direct owner conversation
    SYSTEM = "system"          # System/infra task
    LEARNING = "learning"      # Learning/memory task
    WBOM = "wbom"              # Business operations (WhatsApp Business Ops)
    CONVERSATION = "conversation"  # General conversation (family etc.)


class AgentTask:
    """A task assigned by strategy agent to a domain agent."""

    def __init__(self, agent_name: str, action: str, priority: int = 5, params: dict | None = None):
        self.agent_name = agent_name
        self.action = action
        self.priority = priority  # 1=highest, 10=lowest
        self.params = params or {}
        self.result: Optional[AgentResult] = None


class StrategyAgent:
    """Central coordinator — receives context, decides which agents to invoke,
    manages multi-agent fan-out, and merges results.

    This is NOT a BaseAgent subclass — it's the orchestrator that sits above
    all domain and utility agents.
    """

    def __init__(self, identity: IdentityProfile):
        self.identity = identity
        # Domain agents are registered after init
        self._domain_agents: dict = {}

    def register_agent(self, name: str, agent) -> None:
        """Register a domain agent for coordination."""
        self._domain_agents[name] = agent

    # ── Routing ───────────────────────────────────────────

    def route(self, ctx: AgentContext) -> DomainRoute:
        """Determine which domain should handle this request.

        Routing priority:
        1. Explicit source metadata (voice, owner)
        2. Relationship-based (social)
        3. Content-based (system keywords, learning keywords)
        4. Default to conversation
        """
        source = ctx.metadata.get("source", "text")
        relationship = ctx.relationship

        # Voice calls → voice agent
        if source == "voice":
            return DomainRoute.VOICE

        # Owner messages → owner flow
        if source == "owner" or relationship == "self":
            return DomainRoute.OWNER

        # Social media → social agent
        if relationship == "social":
            return DomainRoute.SOCIAL

        # Check for system keywords
        msg_lower = ctx.message.lower()
        system_agent = self._domain_agents.get("system")
        if system_agent and hasattr(system_agent, "can_handle"):
            # Use a sync check to avoid async in routing
            from .system_agent import _SYSTEM_KEYWORDS
            if any(kw in msg_lower for kw in _SYSTEM_KEYWORDS):
                return DomainRoute.SYSTEM

        # Check for WBOM (business operations) keywords
        from .wbom_agent import _WBOM_KEYWORDS
        if any(kw in msg_lower for kw in _WBOM_KEYWORDS):
            return DomainRoute.WBOM

        # Check for learning keywords
        from .learning_agent import _LEARNING_KEYWORDS
        if any(kw in msg_lower for kw in _LEARNING_KEYWORDS):
            return DomainRoute.LEARNING

        # Default: general conversation (family, friends)
        return DomainRoute.CONVERSATION

    # ── Coordination ──────────────────────────────────────

    async def coordinate(self, ctx: AgentContext, route: DomainRoute) -> dict:
        """Execute the coordination plan for a given route.

        Strategy patterns:
        - SOCIAL: social_agent(prompt) + learning_agent(store) [parallel]
        - VOICE: voice_agent(prompt) — single, fast
        - OWNER: handled by main.py /chat/owner directly
        - SYSTEM: system_agent(execute) + learning_agent(log) [sequential]
        - LEARNING: learning_agent(process)
        - CONVERSATION: identity prompt only, LLM handles rest
        """
        tasks = self._plan_tasks(ctx, route)
        results = await self._execute_tasks(ctx, tasks)

        return {
            "route": route.value,
            "tasks_executed": [t.agent_name for t in tasks],
            "results": results,
            "identity_enforced": True,
        }

    def _plan_tasks(self, ctx: AgentContext, route: DomainRoute) -> list[AgentTask]:
        """Create a task plan based on the domain route."""
        tasks = []

        if route == DomainRoute.SOCIAL:
            tasks.append(AgentTask("social", "build_prompt", priority=1))
            tasks.append(AgentTask("learning", "learn_async", priority=5))

        elif route == DomainRoute.VOICE:
            tasks.append(AgentTask("voice", "build_prompt", priority=1))

        elif route == DomainRoute.SYSTEM:
            tasks.append(AgentTask("system", "execute", priority=1))
            tasks.append(AgentTask("learning", "log", priority=5))

        elif route == DomainRoute.LEARNING:
            tasks.append(AgentTask("learning", "execute", priority=1))

        elif route == DomainRoute.WBOM:
            tasks.append(AgentTask("wbom", "build_prompt", priority=1))
            tasks.append(AgentTask("learning", "log", priority=5))

        elif route == DomainRoute.CONVERSATION:
            # No domain agent needed — identity prompt + LLM
            pass

        elif route == DomainRoute.OWNER:
            # Owner flow is handled by /chat/owner directly
            pass

        return sorted(tasks, key=lambda t: t.priority)

    async def _execute_tasks(self, ctx: AgentContext, tasks: list[AgentTask]) -> dict:
        """Execute planned tasks, running same-priority tasks in parallel."""
        results = {}
        if not tasks:
            return results

        # Group by priority for parallel execution
        priority_groups: dict[int, list[AgentTask]] = {}
        for task in tasks:
            priority_groups.setdefault(task.priority, []).append(task)

        for priority in sorted(priority_groups.keys()):
            group = priority_groups[priority]

            # Run same-priority tasks in parallel
            coros = []
            for task in group:
                agent = self._domain_agents.get(task.agent_name)
                if not agent:
                    logger.warning(f"Agent not found: {task.agent_name}")
                    continue
                coros.append(self._run_agent_task(agent, ctx, task))

            if coros:
                await asyncio.gather(*coros, return_exceptions=True)

            for task in group:
                if task.result:
                    results[task.agent_name] = {
                        "content": task.result.content,
                        "error": task.result.error,
                        "metadata": task.result.metadata,
                    }

        return results

    async def _run_agent_task(self, agent, ctx: AgentContext, task: AgentTask) -> None:
        """Run a single agent task and store the result."""
        try:
            result = await agent.execute(ctx)
            task.result = result
        except Exception as e:
            logger.error(f"Agent {task.agent_name} failed: {e}")
            task.result = AgentResult(error=str(e))

    # ── Identity enforcement ──────────────────────────────

    def get_identity_prompt(self, relationship: str = "social") -> str:
        """Get the identity enforcement prompt for any agent."""
        return self.identity.get_identity_prompt(relationship)

    def enforce_identity(self, system_prompt: str, relationship: str) -> str:
        """Prepend identity core to any system prompt."""
        identity_prompt = self.identity.get_identity_prompt(relationship)
        return f"{identity_prompt}\n\n{system_prompt}"
