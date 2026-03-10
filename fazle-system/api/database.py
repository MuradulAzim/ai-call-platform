# ============================================================
# Fazle API — PostgreSQL Database Layer
# User management with async connection pool
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


class DBSettings(BaseSettings):
    database_url: str = "postgresql://postgres:postgres@postgres:5432/postgres"

    class Config:
        env_prefix = "FAZLE_"


db_settings = DBSettings()

_DSN = db_settings.database_url


def _get_conn():
    return psycopg2.connect(_DSN)


def ensure_users_table():
    """Create users table if it doesn't exist (idempotent)."""
    with _get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS fazle_users (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    email VARCHAR(255) UNIQUE NOT NULL,
                    hashed_password VARCHAR(255) NOT NULL,
                    name VARCHAR(100) NOT NULL,
                    relationship_to_azim VARCHAR(50) NOT NULL DEFAULT 'self',
                    role VARCHAR(20) NOT NULL DEFAULT 'member',
                    is_active BOOLEAN DEFAULT true,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
                CREATE INDEX IF NOT EXISTS idx_fazle_users_email ON fazle_users (email);
            """)
        conn.commit()
    logger.info("fazle_users table ensured")


def create_user(
    email: str,
    hashed_password: str,
    name: str,
    relationship_to_azim: str = "self",
    role: str = "member",
) -> dict:
    """Insert a new user, return the user dict (without password)."""
    user_id = uuid.uuid4()
    with _get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                INSERT INTO fazle_users (id, email, hashed_password, name, relationship_to_azim, role)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING id, email, name, relationship_to_azim, role, is_active, created_at
                """,
                (user_id, email, hashed_password, name, relationship_to_azim, role),
            )
            conn.commit()
            return dict(cur.fetchone())


def get_user_by_email(email: str) -> Optional[dict]:
    """Fetch user by email (includes hashed_password for verification)."""
    with _get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT id, email, hashed_password, name, relationship_to_azim, role, is_active, created_at FROM fazle_users WHERE email = %s",
                (email,),
            )
            row = cur.fetchone()
            return dict(row) if row else None


def get_user_by_id(user_id: str) -> Optional[dict]:
    """Fetch user by ID (without password)."""
    with _get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT id, email, name, relationship_to_azim, role, is_active, created_at FROM fazle_users WHERE id = %s",
                (user_id,),
            )
            row = cur.fetchone()
            return dict(row) if row else None


def list_family_members() -> list[dict]:
    """List all family members (without passwords)."""
    with _get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT id, email, name, relationship_to_azim, role, is_active, created_at FROM fazle_users ORDER BY created_at"
            )
            return [dict(row) for row in cur.fetchall()]


def update_user(user_id: str, **fields) -> Optional[dict]:
    """Update user fields. Returns updated user or None."""
    allowed = {"name", "relationship_to_azim", "role", "is_active"}
    updates = {k: v for k, v in fields.items() if k in allowed and v is not None}
    if not updates:
        return get_user_by_id(user_id)

    set_clause = ", ".join(f"{k} = %s" for k in updates)
    values = list(updates.values()) + [user_id]

    with _get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                f"UPDATE fazle_users SET {set_clause}, updated_at = NOW() WHERE id = %s "
                "RETURNING id, email, name, relationship_to_azim, role, is_active, created_at",
                values,
            )
            conn.commit()
            row = cur.fetchone()
            return dict(row) if row else None


def delete_user(user_id: str) -> bool:
    """Delete a user. Returns True if deleted."""
    with _get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM fazle_users WHERE id = %s", (user_id,))
            conn.commit()
            return cur.rowcount > 0


def count_users() -> int:
    """Count total users."""
    with _get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM fazle_users")
            return cur.fetchone()[0]
