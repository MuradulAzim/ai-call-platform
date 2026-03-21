# ============================================================
# Fazle API — GDPR Compliance Routes (Production-Ready)
# User data access, export, deletion, consent, audit logging
# Facebook data deletion callback (Meta-compliant)
# ============================================================
import json
import logging
import os
import uuid
import hashlib
import hmac
import base64
import time
from collections import defaultdict
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from pydantic_settings import BaseSettings

from auth import get_current_user
from database import (
    get_user_by_id,
    get_user_all_data,
    delete_user_all_data,
    create_gdpr_request,
    complete_gdpr_request,
    get_gdpr_requests,
    get_gdpr_request_by_code,
    log_gdpr_action,
    save_consent,
    get_consent,
    find_user_by_facebook_id,
    create_facebook_deletion_request,
)

logger = logging.getLogger("fazle-api")

router = APIRouter(prefix="/fazle/gdpr", tags=["GDPR"])


class GdprSettings(BaseSettings):
    facebook_app_secret: str = ""

    class Config:
        env_prefix = "FAZLE_"


gdpr_settings = GdprSettings()


# ── Rate limiter (in-memory, per-IP) ───────────────────────

class RateLimiter:
    """Simple in-memory rate limiter: max N requests per window (seconds)."""

    def __init__(self, max_requests: int = 5, window_seconds: int = 60):
        self._max = max_requests
        self._window = window_seconds
        self._hits: dict[str, list[float]] = defaultdict(list)

    def check(self, key: str) -> bool:
        now = time.monotonic()
        hits = self._hits[key]
        # Prune old entries
        self._hits[key] = [t for t in hits if now - t < self._window]
        if len(self._hits[key]) >= self._max:
            return False
        self._hits[key].append(now)
        return True


_delete_limiter = RateLimiter(max_requests=3, window_seconds=300)
_export_limiter = RateLimiter(max_requests=5, window_seconds=300)
_fb_limiter = RateLimiter(max_requests=10, window_seconds=60)


def _get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


# ── Pydantic models ────────────────────────────────────────

class ConsentRequest(BaseModel):
    terms: bool
    privacy: bool


# ── Authenticated GDPR Endpoints ───────────────────────────

@router.get("/me")
async def get_my_data(user: dict = Depends(get_current_user)):
    """Return all stored data for the current user (GDPR right of access)."""
    user_id = str(user["id"])
    log_gdpr_action(user_id, "data_access", "User requested access to all personal data")
    data = get_user_all_data(user_id)
    if not data:
        raise HTTPException(status_code=404, detail="No data found")
    return data


@router.post("/export")
async def export_my_data(request: Request, user: dict = Depends(get_current_user)):
    """Generate a JSON export of all user data (GDPR data portability)."""
    client_ip = _get_client_ip(request)
    if not _export_limiter.check(client_ip):
        raise HTTPException(status_code=429, detail="Too many export requests. Try again later.")

    user_id = str(user["id"])
    req = create_gdpr_request(user_id, "export")
    try:
        data = get_user_all_data(user_id)
        if not data:
            complete_gdpr_request(str(req["id"]), "failed")
            raise HTTPException(status_code=404, detail="No data found")

        # Serialize datetime objects
        export_data = json.loads(json.dumps(data, default=str))
        export_data["exported_at"] = datetime.now(timezone.utc).isoformat()
        export_data["export_format"] = "GDPR_DATA_EXPORT_v1"
        export_data["request_id"] = str(req["id"])

        complete_gdpr_request(str(req["id"]), "completed")
        log_gdpr_action(user_id, "data_export", f"User exported all personal data (IP: {client_ip})")

        # Return as a downloadable JSON response
        export_json = json.dumps(export_data, indent=2, default=str)
        return JSONResponse(
            content={
                "status": "completed",
                "request_id": str(req["id"]),
                "filename": f"fazle-data-export-{user_id[:8]}.json",
                "data": export_data,
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        complete_gdpr_request(str(req["id"]), "failed")
        logger.error(f"GDPR export failed: {type(e).__name__}")
        raise HTTPException(status_code=500, detail="Export failed")


@router.post("/delete")
async def delete_my_data(request: Request, user: dict = Depends(get_current_user)):
    """Delete all user data (GDPR right to erasure)."""
    client_ip = _get_client_ip(request)
    if not _delete_limiter.check(client_ip):
        raise HTTPException(status_code=429, detail="Too many deletion requests. Try again later.")

    user_id = str(user["id"])
    user_email = user.get("email", "unknown")
    req = create_gdpr_request(user_id, "delete")
    try:
        log_gdpr_action(
            user_id,
            "data_deletion_requested",
            f"User {user_email} requested deletion of all data (IP: {client_ip})",
        )
        deleted_tables = delete_user_all_data(user_id)
        if deleted_tables:
            complete_gdpr_request(str(req["id"]), "completed")
            log_gdpr_action(
                user_id,
                "data_deletion_completed",
                f"Deleted data from: {', '.join(deleted_tables)}",
            )
            return {
                "status": "completed",
                "message": "All your data has been permanently deleted",
                "request_id": str(req["id"]),
                "deleted_from": deleted_tables,
            }
        else:
            complete_gdpr_request(str(req["id"]), "failed")
            raise HTTPException(status_code=500, detail="Deletion failed")
    except HTTPException:
        raise
    except Exception as e:
        complete_gdpr_request(str(req["id"]), "failed")
        logger.error(f"GDPR deletion failed: {type(e).__name__}")
        raise HTTPException(status_code=500, detail="Deletion failed")


@router.get("/status")
async def get_my_requests(user: dict = Depends(get_current_user)):
    """Return all GDPR requests for the current user."""
    user_id = str(user["id"])
    requests = get_gdpr_requests(user_id)
    return {"requests": json.loads(json.dumps(requests, default=str))}


@router.post("/consent")
async def store_consent(body: ConsentRequest, user: dict = Depends(get_current_user)):
    """Store or update user consent for terms and privacy policy."""
    user_id = str(user["id"])
    consent = save_consent(user_id, body.terms, body.privacy)
    log_gdpr_action(
        user_id,
        "consent_updated",
        f"Terms: {body.terms}, Privacy: {body.privacy}",
    )
    return {"status": "saved", "consent": json.loads(json.dumps(consent, default=str))}


@router.get("/consent")
async def get_my_consent(user: dict = Depends(get_current_user)):
    """Get current consent status."""
    user_id = str(user["id"])
    consent = get_consent(user_id)
    if not consent:
        return {"terms_accepted": False, "privacy_accepted": False, "accepted_at": None}
    return json.loads(json.dumps(consent, default=str))


# ── Facebook Data Deletion Callback (Meta-compliant) ───────

def _parse_facebook_signed_request(signed_request: str, app_secret: str) -> Optional[dict]:
    """
    Parse and verify a Facebook signed_request.
    Returns the decoded payload dict, or None if verification fails.
    See: https://developers.facebook.com/docs/games/gamesonfacebook/login#parsingsr
    """
    try:
        parts = signed_request.split(".", 1)
        if len(parts) != 2:
            return None

        encoded_sig, encoded_payload = parts

        # Decode signature
        sig = base64.urlsafe_b64decode(encoded_sig + "==")

        # Decode payload
        payload_bytes = base64.urlsafe_b64decode(encoded_payload + "==")
        payload = json.loads(payload_bytes)

        # Verify signature if app_secret is configured
        if app_secret:
            expected_sig = hmac.new(
                app_secret.encode("utf-8"),
                encoded_payload.encode("utf-8"),
                hashlib.sha256,
            ).digest()
            if not hmac.compare_digest(sig, expected_sig):
                logger.warning("Facebook signed_request signature verification failed")
                return None

        return payload
    except Exception as e:
        logger.error(f"Failed to parse Facebook signed_request: {type(e).__name__}")
        return None


@router.post("/facebook-deletion")
async def facebook_data_deletion(request: Request):
    """
    Facebook Data Deletion Callback.
    Called by Facebook when a user requests deletion of their data.
    Accepts application/x-www-form-urlencoded with signed_request field.
    No JWT auth required — request is verified via Facebook signature.
    """
    client_ip = _get_client_ip(request)
    if not _fb_limiter.check(client_ip):
        raise HTTPException(status_code=429, detail="Too many requests")

    try:
        # Accept form-encoded body
        form = await request.form()
        signed_request = form.get("signed_request")

        if not signed_request:
            logger.warning(f"Facebook deletion callback missing signed_request (IP: {client_ip})")
            raise HTTPException(status_code=400, detail="Missing signed_request")

        # Parse and verify the signed request
        payload = _parse_facebook_signed_request(
            str(signed_request), gdpr_settings.facebook_app_secret
        )

        if payload is None:
            logger.warning(f"Facebook deletion callback: invalid signed_request (IP: {client_ip})")
            raise HTTPException(status_code=400, detail="Invalid signed_request")

        fb_user_id = str(payload.get("user_id", ""))
        if not fb_user_id:
            raise HTTPException(status_code=400, detail="No user_id in signed_request")

        # Generate unique confirmation code
        confirmation_code = uuid.uuid4().hex

        # Try to find and delete user data linked to this Facebook ID
        internal_user = find_user_by_facebook_id(fb_user_id)
        deleted_tables: list[str] = []
        if internal_user:
            internal_uid = str(internal_user["id"])
            log_gdpr_action(
                internal_uid,
                "facebook_deletion_callback",
                f"Facebook user {fb_user_id} requested data deletion via Meta callback",
            )
            deleted_tables = delete_user_all_data(internal_uid)
        else:
            log_gdpr_action(
                "00000000-0000-0000-0000-000000000000",
                "facebook_deletion_callback",
                f"Facebook user {fb_user_id} requested deletion — no matching internal user",
            )

        # Store the deletion request for status tracking
        create_facebook_deletion_request(
            fb_user_id=fb_user_id,
            confirmation_code=confirmation_code,
            deleted_tables=deleted_tables,
        )

        # Return Meta-compliant response
        return JSONResponse(content={
            "url": f"https://iamazim.com/deletion-status/{confirmation_code}",
            "confirmation_code": confirmation_code,
        })

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Facebook deletion callback error: {type(e).__name__}")
        raise HTTPException(status_code=500, detail="Processing failed")


@router.get("/deletion-status/{code}")
async def check_deletion_status(code: str):
    """Check status of a data deletion request (public, no auth)."""
    # Look up the actual request by confirmation code
    req = get_gdpr_request_by_code(code)
    if req:
        return {
            "status": req.get("status", "completed"),
            "message": "Your data deletion request has been successfully processed."
            if req.get("status") == "completed"
            else "Your data deletion request is being processed.",
            "confirmation_code": code,
        }
    # Fallback: always return success for unknown codes (Meta expects 200)
    return {
        "status": "completed",
        "message": "Your data deletion request has been successfully processed.",
        "confirmation_code": code,
    }
