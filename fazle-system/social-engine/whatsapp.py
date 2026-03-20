# ============================================================
# Fazle Social Engine — WhatsApp Business API Integration
# Handles messaging, scheduling, broadcasts via Meta WhatsApp
# ============================================================
import httpx
import logging
import uuid
from datetime import datetime, timezone

logger = logging.getLogger("fazle-social-engine")


async def send_message(
    api_url: str,
    api_token: str,
    phone_number_id: str,
    to: str,
    message: str,
) -> dict:
    """Send a WhatsApp text message via Meta Business API."""
    if not all([api_url, api_token, phone_number_id]):
        return {"sent": False, "error": "WhatsApp API not configured"}

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                f"{api_url}/{phone_number_id}/messages",
                headers={"Authorization": f"Bearer {api_token}"},
                json={
                    "messaging_product": "whatsapp",
                    "to": to,
                    "type": "text",
                    "text": {"body": message},
                },
            )
            if resp.status_code == 200:
                data = resp.json()
                return {"sent": True, "message_id": data.get("messages", [{}])[0].get("id")}
            return {"sent": False, "error": f"API returned {resp.status_code}: {resp.text[:200]}"}
    except Exception as e:
        logger.error(f"WhatsApp send failed: {e}")
        return {"sent": False, "error": str(e)}


async def send_template(
    api_url: str,
    api_token: str,
    phone_number_id: str,
    to: str,
    template_name: str,
    language_code: str = "en_US",
    components: list | None = None,
) -> dict:
    """Send a WhatsApp template message."""
    if not all([api_url, api_token, phone_number_id]):
        return {"sent": False, "error": "WhatsApp API not configured"}

    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "template",
        "template": {
            "name": template_name,
            "language": {"code": language_code},
        },
    }
    if components:
        payload["template"]["components"] = components

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                f"{api_url}/{phone_number_id}/messages",
                headers={"Authorization": f"Bearer {api_token}"},
                json=payload,
            )
            if resp.status_code == 200:
                return {"sent": True, "message_id": resp.json().get("messages", [{}])[0].get("id")}
            return {"sent": False, "error": f"API returned {resp.status_code}"}
    except Exception as e:
        logger.error(f"WhatsApp template send failed: {e}")
        return {"sent": False, "error": str(e)}


def parse_incoming_message(payload: dict) -> list[dict]:
    """Parse incoming webhook payload from Meta WhatsApp Cloud API.
    Returns a list of message dicts with sender, text, timestamp, etc."""
    messages = []
    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            value = change.get("value", {})
            contacts = {c["wa_id"]: c.get("profile", {}).get("name", "")
                        for c in value.get("contacts", [])}
            for msg in value.get("messages", []):
                messages.append({
                    "sender_id": msg.get("from", ""),
                    "sender_name": contacts.get(msg.get("from", ""), ""),
                    "message_id": msg.get("id", ""),
                    "timestamp": msg.get("timestamp", ""),
                    "type": msg.get("type", "text"),
                    "text": msg.get("text", {}).get("body", "") if msg.get("type") == "text" else "",
                    "raw": msg,
                })
    return messages
