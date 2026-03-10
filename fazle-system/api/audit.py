# ============================================================
# Fazle API — Audit Logger
# Append-only audit log for admin and sensitive operations
# ============================================================
import logging
import uuid
from datetime import datetime
from typing import Optional

import psycopg2
import psycopg2.extras
from pydantic_settings import BaseSettings

logger = logging.getLogger("fazle-api")

psycopg2.extras.register_uuid()


class AuditDBSettings(BaseSettings):
    database_url: str = "postgresql://postgres:postgres@postgres:5432/postgres"

    class Config:
        env_prefix = "FAZLE_"


_audit_dsn = AuditDBSettings().database_url


def _get_conn():
    return psycopg2.connect(_audit_dsn)


def ensure_audit_table():
    """Create the audit_log table (append-only, no UPDATE/DELETE grants)."""
    with _get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS fazle_audit_log (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    actor_id VARCHAR(100) NOT NULL,
                    actor_email VARCHAR(255) NOT NULL DEFAULT '',
                    action VARCHAR(100) NOT NULL,
                    target_type VARCHAR(50) NOT NULL DEFAULT '',
                    target_id VARCHAR(100) DEFAULT '',
                    detail TEXT DEFAULT '',
                    ip_address VARCHAR(45) DEFAULT '',
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
                CREATE INDEX IF NOT EXISTS idx_audit_actor ON fazle_audit_log (actor_id);
                CREATE INDEX IF NOT EXISTS idx_audit_action ON fazle_audit_log (action);
                CREATE INDEX IF NOT EXISTS idx_audit_created ON fazle_audit_log (created_at);
            """)
        conn.commit()
    logger.info("fazle_audit_log table ensured")


def log_action(
    actor: dict,
    action: str,
    target_type: str = "",
    target_id: str = "",
    detail: str = "",
    ip_address: str = "",
):
    """Insert an immutable audit record."""
    try:
        with _get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO fazle_audit_log
                        (id, actor_id, actor_email, action, target_type, target_id, detail, ip_address)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        uuid.uuid4(),
                        str(actor.get("id", "unknown")),
                        actor.get("email", ""),
                        action,
                        target_type,
                        str(target_id),
                        detail[:2000],  # cap detail length
                        ip_address,
                    ),
                )
            conn.commit()
    except Exception as e:
        logger.error(f"Audit log write failed: {e}")


def get_audit_logs(
    limit: int = 100,
    action_filter: Optional[str] = None,
    actor_id: Optional[str] = None,
) -> list[dict]:
    """Read audit logs (admin only)."""
    with _get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            query = "SELECT * FROM fazle_audit_log WHERE 1=1"
            params: list = []
            if action_filter:
                query += " AND action = %s"
                params.append(action_filter)
            if actor_id:
                query += " AND actor_id = %s"
                params.append(actor_id)
            query += " ORDER BY created_at DESC LIMIT %s"
            params.append(limit)
            cur.execute(query, params)
            rows = cur.fetchall()
            return [
                {**dict(r), "id": str(r["id"]), "created_at": r["created_at"].isoformat()}
                for r in rows
            ]
