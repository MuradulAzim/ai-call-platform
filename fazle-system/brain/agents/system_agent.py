# ============================================================
# System Agent — Handles system-level tasks and autonomy coordination
# Wraps autonomy engine interactions with identity enforcement
# ============================================================
import logging
import httpx
from .base import BaseAgent, AgentContext, AgentResult
from .identity_core import IdentityProfile

logger = logging.getLogger("fazle-agents.system")

_SYSTEM_KEYWORDS = frozenset([
    "system", "status", "health", "deploy", "restart", "backup",
    "rollback", "container", "docker", "server", "uptime",
    "monitor", "alert", "log", "error", "fix", "repair",
    "report", "stats", "statistics", "autonomy", "sandbox",
    "execution", "rule", "level",
    # Self-development keywords
    "scan", "improve", "patch", "optimize", "refactor",
    "code", "analyze", "diff", "self-dev", "codebase",
    "improvement", "duplicate", "unused", "inefficiency",
    "performance", "bug",
    # Governor keywords
    "governor", "stability", "safe_mode", "safe mode",
    "quality", "alignment", "feedback",
])


class SystemAgent(BaseAgent):
    """Handles system monitoring, autonomy decisions, infrastructure tasks,
    and self-development engine (code scanning, patching, improvement)."""

    name = "system"
    description = "System monitoring, autonomy coordination, infrastructure management, and self-development engine"

    def __init__(
        self,
        autonomy_engine_url: str,
        identity: IdentityProfile,
    ):
        self.autonomy_engine_url = autonomy_engine_url
        self.identity = identity

    async def can_handle(self, ctx: AgentContext) -> bool:
        """System agent handles system/infra keywords or owner system commands."""
        msg_lower = ctx.message.lower()
        if any(kw in msg_lower for kw in _SYSTEM_KEYWORDS):
            return True
        # Owner requesting reports or system actions
        intent = ctx.metadata.get("detected_intent")
        return intent in (
            "generate_report", "system_control",
            "approve_sandbox", "reject_sandbox",
            "update_execution_rule", "restore_backup",
            # Self-dev intents
            "scan_codebase", "list_patches", "view_patch",
            "approve_patch", "reject_patch", "apply_patch",
            "rollback_patch", "patch_outcome", "selfdev_history",
            # Governor intents
            "governor_status", "governor_safe_mode", "governor_feedback",
        )

    async def execute(self, ctx: AgentContext) -> AgentResult:
        """Execute system-level task via autonomy engine."""
        try:
            intent = ctx.metadata.get("detected_intent", "status_check")
            result = {}

            if intent == "generate_report":
                result = await self._get_report()
            elif intent in ("approve_sandbox", "reject_sandbox"):
                result = await self._handle_sandbox(intent, ctx)
            elif intent == "update_execution_rule":
                result = await self._update_rule(ctx)
            elif intent == "restore_backup":
                result = await self._restore_backup(ctx)
            # ── Self-Development Engine intents ──
            elif intent == "scan_codebase":
                result = await self._scan_codebase()
            elif intent == "list_patches":
                result = await self._list_patches(ctx)
            elif intent == "view_patch":
                result = await self._view_patch(ctx)
            elif intent == "approve_patch":
                result = await self._approve_patch(ctx)
            elif intent == "reject_patch":
                result = await self._reject_patch(ctx)
            elif intent == "apply_patch":
                result = await self._apply_patch(ctx)
            elif intent == "rollback_patch":
                result = await self._rollback_patch(ctx)
            elif intent == "patch_outcome":
                result = await self._patch_outcome(ctx)
            elif intent == "selfdev_history":
                result = await self._selfdev_history()
            # ── Governor v2 intents ──
            elif intent == "governor_status":
                result = await self._governor_dashboard()
            elif intent == "governor_safe_mode":
                result = await self._governor_toggle_safe_mode(ctx)
            elif intent == "governor_feedback":
                result = await self._governor_submit_feedback(ctx)
            else:
                # General system status
                result = await self._get_status()

            ctx.metadata["system_result"] = result
            ctx.metadata["identity_enforced"] = True

            return AgentResult(
                content=result,
                metadata={"agent": self.name, "intent": intent},
            )
        except Exception as e:
            logger.error(f"System agent error: {e}")
            return AgentResult(error=str(e))

    async def _get_status(self) -> dict:
        """Get system health status."""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(f"{self.autonomy_engine_url}/health")
                if resp.status_code == 200:
                    return resp.json()
        except Exception as e:
            logger.debug(f"Status check failed: {e}")
        return {"status": "unknown"}

    async def _get_report(self) -> dict:
        """Get intelligence report from autonomy engine."""
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(f"{self.autonomy_engine_url}/report")
                if resp.status_code == 200:
                    return resp.json()
        except Exception as e:
            logger.debug(f"Report fetch failed: {e}")
        return {"error": "Report unavailable"}

    async def _handle_sandbox(self, intent: str, ctx: AgentContext) -> dict:
        """Approve or reject a sandbox change."""
        action = "approve" if intent == "approve_sandbox" else "reject"
        change_id = ctx.metadata.get("change_id", "")
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(
                    f"{self.autonomy_engine_url}/sandbox/{action}",
                    json={"change_id": change_id},
                )
                if resp.status_code == 200:
                    return resp.json()
        except Exception as e:
            logger.debug(f"Sandbox {action} failed: {e}")
        return {"error": f"Sandbox {action} failed"}

    async def _update_rule(self, ctx: AgentContext) -> dict:
        """Update an execution rule."""
        params = ctx.metadata.get("params", {})
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(
                    f"{self.autonomy_engine_url}/execution-rules/update",
                    json=params,
                )
                if resp.status_code == 200:
                    return resp.json()
        except Exception as e:
            logger.debug(f"Rule update failed: {e}")
        return {"error": "Rule update failed"}

    async def _restore_backup(self, ctx: AgentContext) -> dict:
        """Restore from a backup."""
        backup_id = ctx.metadata.get("backup_id", "")
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(
                    f"{self.autonomy_engine_url}/backup/restore",
                    json={"backup_id": backup_id},
                )
                if resp.status_code == 200:
                    return resp.json()
        except Exception as e:
            logger.debug(f"Backup restore failed: {e}")
        return {"error": "Restore failed"}

    # ── Self-Development Engine Methods ──────────────────────

    async def _scan_codebase(self) -> dict:
        """Trigger a full codebase scan → detect improvements → generate patches."""
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                resp = await client.post(f"{self.autonomy_engine_url}/autonomy/self-dev/scan")
                if resp.status_code == 200:
                    return resp.json()
                return {"error": f"Scan returned {resp.status_code}"}
        except Exception as e:
            logger.error(f"Codebase scan failed: {e}")
            return {"error": f"Scan failed: {e}"}

    async def _list_patches(self, ctx: AgentContext) -> dict:
        """List all self-dev patches, optionally filtered by status."""
        status = ctx.metadata.get("params", {}).get("status", "")
        try:
            url = f"{self.autonomy_engine_url}/autonomy/self-dev/patches"
            if status:
                url += f"?status={status}"
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(url)
                if resp.status_code == 200:
                    return resp.json()
        except Exception as e:
            logger.debug(f"List patches failed: {e}")
        return {"error": "Failed to list patches"}

    async def _view_patch(self, ctx: AgentContext) -> dict:
        """View a specific patch with full diff."""
        patch_id = ctx.metadata.get("params", {}).get("patch_id", "")
        if not patch_id:
            return {"error": "patch_id required"}
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(f"{self.autonomy_engine_url}/autonomy/self-dev/patch/{patch_id}")
                if resp.status_code == 200:
                    return resp.json()
                return {"error": f"Patch {patch_id} not found"}
        except Exception as e:
            logger.debug(f"View patch failed: {e}")
        return {"error": "Failed to view patch"}

    async def _approve_patch(self, ctx: AgentContext) -> dict:
        """Owner approves a self-dev patch."""
        patch_id = ctx.metadata.get("params", {}).get("patch_id", "")
        if not patch_id:
            return {"error": "patch_id required"}
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(f"{self.autonomy_engine_url}/autonomy/self-dev/patch/{patch_id}/approve")
                if resp.status_code == 200:
                    return resp.json()
                return {"error": f"Approve failed for {patch_id}"}
        except Exception as e:
            logger.debug(f"Approve patch failed: {e}")
        return {"error": "Failed to approve patch"}

    async def _reject_patch(self, ctx: AgentContext) -> dict:
        """Owner rejects a self-dev patch."""
        patch_id = ctx.metadata.get("params", {}).get("patch_id", "")
        if not patch_id:
            return {"error": "patch_id required"}
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(f"{self.autonomy_engine_url}/autonomy/self-dev/patch/{patch_id}/reject")
                if resp.status_code == 200:
                    return resp.json()
                return {"error": f"Reject failed for {patch_id}"}
        except Exception as e:
            logger.debug(f"Reject patch failed: {e}")
        return {"error": "Failed to reject patch"}

    async def _apply_patch(self, ctx: AgentContext) -> dict:
        """Safely apply an approved patch (backup → verify → apply)."""
        patch_id = ctx.metadata.get("params", {}).get("patch_id", "")
        if not patch_id:
            return {"error": "patch_id required"}
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(f"{self.autonomy_engine_url}/autonomy/self-dev/patch/{patch_id}/apply")
                if resp.status_code == 200:
                    return resp.json()
                return {"error": f"Apply failed for {patch_id}"}
        except Exception as e:
            logger.debug(f"Apply patch failed: {e}")
        return {"error": "Failed to apply patch"}

    async def _rollback_patch(self, ctx: AgentContext) -> dict:
        """Rollback a previously applied patch."""
        patch_id = ctx.metadata.get("params", {}).get("patch_id", "")
        if not patch_id:
            return {"error": "patch_id required"}
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(f"{self.autonomy_engine_url}/autonomy/self-dev/patch/{patch_id}/rollback")
                if resp.status_code == 200:
                    return resp.json()
                return {"error": f"Rollback failed for {patch_id}"}
        except Exception as e:
            logger.debug(f"Rollback patch failed: {e}")
        return {"error": "Failed to rollback patch"}

    async def _patch_outcome(self, ctx: AgentContext) -> dict:
        """Record whether an applied patch had positive/negative effect."""
        patch_id = ctx.metadata.get("params", {}).get("patch_id", "")
        outcome = ctx.metadata.get("params", {}).get("outcome", "positive")
        if not patch_id:
            return {"error": "patch_id required"}
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(
                    f"{self.autonomy_engine_url}/autonomy/self-dev/patch/{patch_id}/outcome",
                    params={"outcome": outcome},
                )
                if resp.status_code == 200:
                    return resp.json()
        except Exception as e:
            logger.debug(f"Patch outcome failed: {e}")
        return {"error": "Failed to record outcome"}

    async def _selfdev_history(self) -> dict:
        """Get self-development change history and stats."""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(f"{self.autonomy_engine_url}/autonomy/self-dev/history")
                if resp.status_code == 200:
                    return resp.json()
        except Exception as e:
            logger.debug(f"Self-dev history failed: {e}")
        return {"error": "Failed to get history"}

    # ── Governor v2 Methods ──────────────────────────────────

    async def _governor_dashboard(self):
        """Get governor dashboard data."""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(f"{self.autonomy_engine_url}/governor/dashboard")
                if resp.status_code == 200:
                    return resp.json()
        except Exception as e:
            logger.debug(f"Governor dashboard failed: {e}")
        return {"error": "Failed to get governor dashboard"}

    async def _governor_toggle_safe_mode(self, ctx: AgentContext):
        """Toggle governor safe mode."""
        msg_lower = ctx.message.lower()
        activate = "on" in msg_lower or "enable" in msg_lower or "activate" in msg_lower
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(
                    f"{self.autonomy_engine_url}/governor/safe-mode",
                    params={"active": activate},
                )
                if resp.status_code == 200:
                    return resp.json()
        except Exception as e:
            logger.debug(f"Governor safe mode toggle failed: {e}")
        return {"error": "Failed to toggle safe mode"}

    async def _governor_submit_feedback(self, ctx: AgentContext):
        """Submit owner feedback to governor."""
        try:
            score = 1.0 if any(w in ctx.message.lower() for w in ["ভালো", "good", "great", "correct"]) else -1.0
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(
                    f"{self.autonomy_engine_url}/governor/feedback",
                    json={"feedback": ctx.message, "score": score},
                )
                if resp.status_code == 200:
                    return resp.json()
        except Exception as e:
            logger.debug(f"Governor feedback failed: {e}")
        return {"error": "Failed to submit feedback"}
