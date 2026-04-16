# ============================================================
# Structured JSON Logging — shared formatter for Fazle services
# Adds request_id, source, action to log records.
# ============================================================
import json
import logging
import traceback
from datetime import datetime, timezone


class StructuredJsonFormatter(logging.Formatter):
    """Emit one JSON object per log line with structured fields."""

    def __init__(self, service_name: str = "unknown"):
        super().__init__()
        self.service_name = service_name

    def format(self, record: logging.LogRecord) -> str:
        entry = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "source": self.service_name,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        # Inject request_id if attached by middleware
        if hasattr(record, "request_id"):
            entry["request_id"] = record.request_id
        # Inject employee_id if available
        if hasattr(record, "employee_id"):
            entry["employee_id"] = record.employee_id
        # Inject action tag
        if hasattr(record, "action"):
            entry["action"] = record.action
        # Exception info
        if record.exc_info and record.exc_info[0]:
            entry["exception"] = traceback.format_exception(*record.exc_info)
        return json.dumps(entry, ensure_ascii=False, default=str)


def setup_structured_logging(service_name: str, level: int = logging.INFO):
    """Replace root handler with structured JSON formatter."""
    handler = logging.StreamHandler()
    handler.setFormatter(StructuredJsonFormatter(service_name))
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)
