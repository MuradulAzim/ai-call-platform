# ============================================================
# WBOM — Configuration & Environment
# Phase 10: Centralized settings via environment variables
# ============================================================
from pydantic_settings import BaseSettings


class WBOMSettings(BaseSettings):
    """All WBOM configuration loaded from environment variables.

    Every field can be overridden via WBOM_<FIELD_NAME> env var.
    """

    # ── Database ──────────────────────────────────────────────
    database_url: str = "postgresql://postgres:postgres@postgres:5432/postgres"

    # ── WhatsApp API ──────────────────────────────────────────
    whatsapp_api_url: str = "https://graph.facebook.com/v18.0"
    whatsapp_phone_number_id: str = ""
    whatsapp_access_token: str = ""
    whatsapp_webhook_verify_token: str = ""

    # ── Core module integration ───────────────────────────────
    core_api_url: str = "http://fazle-brain:8100/api"
    core_api_key: str = ""
    subagent_id: str = "WBOM"
    event_webhook: str = "/api/subagent/wbom/events"

    # ── AI Processing ─────────────────────────────────────────
    confidence_threshold: float = 0.7
    auto_process_threshold: float = 0.9
    max_extraction_attempts: int = 3

    # ── Internal service auth (zero-trust) ────────────────────
    internal_key: str = ""  # WBOM_INTERNAL_KEY — shared secret for service-to-service calls

    # ── Business Rules ────────────────────────────────────────
    default_service_charge: int = 2000
    per_program_allowance: int = 500
    max_advance_percentage: float = 0.5
    shift_day_start: int = 6    # 6 AM
    shift_night_start: int = 18  # 6 PM

    # ── Validation ────────────────────────────────────────────
    mobile_format: str = "BD"
    date_format: str = "%d.%m.%Y"
    require_admin_approval: bool = True
    allow_validation_override: bool = True

    class Config:
        env_prefix = "WBOM_"

    # ── Helpers ───────────────────────────────────────────────

    def get_shift(self, hour: int) -> str:
        """Return 'D' or 'N' based on hour of day."""
        return "D" if self.shift_day_start <= hour < self.shift_night_start else "N"


# Singleton — import this from anywhere
settings = WBOMSettings()
