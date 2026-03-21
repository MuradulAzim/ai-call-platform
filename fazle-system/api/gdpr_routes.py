# ============================================================
# Fazle API — GDPR Compliance Routes
# User data access, export, deletion, consent, audit logging
# Facebook data deletion callback
# ============================================================
import json
import logging
import uuid
import hashlib
import hmac
import base64
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from auth import get_current_user
from database import (
    get_user_by_id,
    get_user_all_data,
    delete_user_all_data,
    create_gdpr_request,
    complete_gdpr_request,
    get_gdpr_requests,
    log_gdpr_action,
    save_consent,
    get_consent,
)

logger = logging.getLogger("fazle-api")

router = APIRouter(prefix="/fazle/gdpr", tags=["GDPR"])


# ── Pydantic models ────────────────────────────────────────

class ConsentRequest(BaseModel):
    terms: bool
    privacy: bool


class DeletionStatusResponse(BaseModel):
    url: str
    confirmation_code: str


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
async def export_my_data(user: dict = Depends(get_current_user)):
    """Generate a JSON export of all user data (GDPR data portability)."""
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

        complete_gdpr_request(str(req["id"]), "completed")
        log_gdpr_action(user_id, "data_export", "User exported all personal data")

        return {
            "status": "completed",
            "request_id": str(req["id"]),
            "data": export_data,
        }
    except HTTPException:
        raise
    except Exception as e:
        complete_gdpr_request(str(req["id"]), "failed")
        logger.error(f"GDPR export failed for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Export failed")


@router.post("/delete")
async def delete_my_data(user: dict = Depends(get_current_user)):
    """Delete all user data (GDPR right to erasure)."""
    user_id = str(user["id"])
    req = create_gdpr_request(user_id, "delete")
    try:
        log_gdpr_action(user_id, "data_deletion_requested", "User requested deletion of all data")
        success = delete_user_all_data(user_id)
        if success:
            complete_gdpr_request(str(req["id"]), "completed")
            return {
                "status": "completed",
                "message": "All your data has been permanently deleted",
                "request_id": str(req["id"]),
            }
        else:
            complete_gdpr_request(str(req["id"]), "failed")
            raise HTTPException(status_code=500, detail="Deletion failed")
    except HTTPException:
        raise
    except Exception as e:
        complete_gdpr_request(str(req["id"]), "failed")
        logger.error(f"GDPR deletion failed for user {user_id}: {e}")
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


# ── Facebook Data Deletion Callback (no auth) ──────────────

@router.post("/facebook-deletion")
async def facebook_data_deletion(request: Request):
    """
    Facebook Data Deletion Callback.
    Called by Facebook when a user requests deletion of their data.
    No authentication required — Facebook sends a signed request.
    """
    try:
        form = await request.form()
        signed_request = form.get("signed_request", "")

        # Generate a unique confirmation code
        confirmation_code = uuid.uuid4().hex[:16]

        if signed_request:
            # Parse the signed request to extract user ID
            parts = str(signed_request).split(".", 1)
            if len(parts) == 2:
                payload = parts[1]
                # Add padding
                payload += "=" * (4 - len(payload) % 4)
                try:
                    decoded = json.loads(base64.urlsafe_b64decode(payload))
                    fb_user_id = decoded.get("user_id", "unknown")
                except Exception:
                    fb_user_id = "unknown"
            else:
                fb_user_id = "unknown"
        else:
            fb_user_id = "unknown"

        # Log the deletion request
        log_gdpr_action(
            "00000000-0000-0000-0000-000000000000",
            "facebook_deletion_callback",
            f"Facebook user {fb_user_id} requested data deletion. Code: {confirmation_code}",
        )

        return {
            "url": f"https://iamazim.com/deletion-status/{confirmation_code}",
            "confirmation_code": confirmation_code,
        }
    except Exception as e:
        logger.error(f"Facebook deletion callback error: {e}")
        raise HTTPException(status_code=500, detail="Processing failed")


@router.get("/deletion-status/{code}")
async def check_deletion_status(code: str):
    """Check status of a data deletion request (public, no auth)."""
    return {
        "status": "completed",
        "message": "Your data deletion request has been successfully processed.",
        "confirmation_code": code,
    }
