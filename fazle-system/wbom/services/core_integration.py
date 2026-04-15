# ============================================================
# WBOM — Core Module Integration
# Phase 7 §7.2: Communication with main AI-App core module
# ============================================================
import logging
import os
from datetime import datetime
from typing import Optional

import httpx

logger = logging.getLogger("wbom.core_integration")

CORE_API_URL = os.getenv("WBOM_BRAIN_URL", "http://fazle-brain:8200")
API_KEY = os.getenv("WBOM_API_KEY", "")


class CoreModuleIntegration:
    """Handle communication with the Fazle brain / core module."""

    def __init__(
        self,
        core_api_url: str = CORE_API_URL,
        api_key: str = API_KEY,
        timeout: float = 10.0,
    ):
        self.core_url = core_api_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout

    # ── outbound events ──────────────────────────────────────

    def notify_event(self, event_type: str, payload: dict) -> bool:
        """Send event notification to core module.

        Returns True on success, False on failure (non-blocking).
        """
        body = {
            "subagent": "WBOM",
            "event_type": event_type,
            "timestamp": datetime.utcnow().isoformat(),
            "payload": payload,
        }
        return self._post("/api/events", body)

    def log_activity(self, activity_type: str, details: dict) -> bool:
        """Send activity log to core module."""
        body = {
            "subagent": "WBOM",
            "activity_type": activity_type,
            "timestamp": datetime.utcnow().isoformat(),
            "details": details,
        }
        return self._post("/api/activity-log", body)

    # ── inbound context ──────────────────────────────────────

    def request_user_context(self, user_id: str) -> Optional[dict]:
        """Get user context from core module."""
        return self._get(f"/api/users/{user_id}/context")

    # ── convenience shortcuts ────────────────────────────────

    def notify_message_processed(
        self, message_id: int, classification: str, confidence: float
    ) -> bool:
        return self.notify_event("message_processed", {
            "message_id": message_id,
            "classification": classification,
            "confidence": confidence,
        })

    def notify_program_created(self, program_id: int, details: dict) -> bool:
        return self.notify_event("program_created", {
            "program_id": program_id,
            **details,
        })

    def notify_payment_recorded(self, transaction_id: int, details: dict) -> bool:
        return self.notify_event("payment_recorded", {
            "transaction_id": transaction_id,
            **details,
        })

    # ── HTTP helpers (non-blocking, fire-and-forget) ─────────

    def _post(self, path: str, body: dict) -> bool:
        try:
            headers = {}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"
            resp = httpx.post(
                f"{self.core_url}{path}",
                json=body,
                headers=headers,
                timeout=self.timeout,
            )
            if resp.status_code >= 400:
                logger.warning(
                    "Core module POST %s returned %s", path, resp.status_code
                )
                return False
            return True
        except Exception as e:
            logger.debug("Core module POST %s failed: %s", path, e)
            return False

    def _get(self, path: str) -> Optional[dict]:
        try:
            headers = {}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"
            resp = httpx.get(
                f"{self.core_url}{path}",
                headers=headers,
                timeout=self.timeout,
            )
            if resp.status_code >= 400:
                logger.warning(
                    "Core module GET %s returned %s", path, resp.status_code
                )
                return None
            return resp.json()
        except Exception as e:
            logger.debug("Core module GET %s failed: %s", path, e)
            return None
