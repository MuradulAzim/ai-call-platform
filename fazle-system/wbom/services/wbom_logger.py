# ============================================================
# WBOM — Centralized Logger + Error Handling
# Phase 11: Consistent error handling & logging
# ============================================================
import json
import logging
import traceback
from datetime import datetime
from functools import wraps
from typing import Optional

from fastapi import HTTPException

logger = logging.getLogger("wbom")


# ── Log-level mapping per event type ─────────────────────────

LOG_LEVELS = {
    "message_received": logging.INFO,
    "message_classified": logging.INFO,
    "extraction_complete": logging.INFO,
    "template_generated": logging.INFO,
    "program_saved": logging.INFO,
    "payment_recorded": logging.INFO,
    "extraction_failed": logging.WARNING,
    "low_confidence": logging.WARNING,
    "validation_error": logging.ERROR,
    "database_error": logging.CRITICAL,
    "api_error": logging.ERROR,
}


class WBOMLogger:
    """Centralized structured logger for WBOM subagent."""

    def __init__(self, component: str = "wbom"):
        self._log = logging.getLogger(f"wbom.{component}")

    def log_event(
        self,
        event_type: str,
        details: dict,
        level: Optional[int] = None,
    ):
        """Log a structured event.

        Args:
            event_type: Key from LOG_LEVELS (or any string).
            details: Contextual key/value pairs.
            level: Override the default level for this event type.
        """
        lvl = level or LOG_LEVELS.get(event_type, logging.INFO)

        entry = {
            "ts": datetime.utcnow().isoformat(),
            "subagent": "WBOM",
            "event": event_type,
            "details": details,
        }

        self._log.log(lvl, json.dumps(entry, default=str))

        # Notify core module on critical events
        if lvl >= logging.ERROR:
            self._notify_core(event_type, entry)

    def _notify_core(self, event_type: str, entry: dict):
        """Fire-and-forget notification to brain on ERROR/CRITICAL."""
        try:
            from services.core_integration import CoreModuleIntegration

            CoreModuleIntegration().notify_event(event_type, entry)
        except Exception:
            # Never let notification failure break the caller
            self._log.debug("Core notification failed (non-critical)")


# ── Error-handling decorator ─────────────────────────────────

def handle_errors(func):
    """Decorator for consistent error handling on route handlers.

    Catches common exception types and returns a structured JSON
    error response instead of an unhandled 500.
    """

    @wraps(func)
    def wrapper(*args, **kwargs):
        wlog = WBOMLogger(func.__module__ or "route")
        try:
            return func(*args, **kwargs)
        except HTTPException:
            raise  # Let FastAPI handle HTTP exceptions natively
        except ValueError as exc:
            wlog.log_event(
                "validation_error",
                {"function": func.__name__, "error": str(exc)},
            )
            raise HTTPException(status_code=422, detail=str(exc))
        except Exception as exc:
            wlog.log_event(
                "unexpected_error",
                {
                    "function": func.__name__,
                    "error": str(exc),
                    "traceback": traceback.format_exc(),
                },
                level=logging.CRITICAL,
            )
            raise HTTPException(
                status_code=500,
                detail="An unexpected error occurred",
            )

    return wrapper
