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
        transport = httpx.AsyncHTTPTransport(local_address="0.0.0.0")
        async with httpx.AsyncClient(transport=transport, timeout=15.0) as client:
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
        transport = httpx.AsyncHTTPTransport(local_address="0.0.0.0")
        async with httpx.AsyncClient(transport=transport, timeout=15.0) as client:
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
    Returns a list of message dicts with sender, text, timestamp, media info, etc."""
    messages = []
    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            value = change.get("value", {})
            contacts = {c["wa_id"]: c.get("profile", {}).get("name", "")
                        for c in value.get("contacts", [])}
            for msg in value.get("messages", []):
                msg_type = msg.get("type", "text")
                text = ""
                media_id = ""
                caption = ""

                if msg_type == "text":
                    text = msg.get("text", {}).get("body", "")
                elif msg_type == "image":
                    media_id = msg.get("image", {}).get("id", "")
                    caption = msg.get("image", {}).get("caption", "")
                elif msg_type == "audio":
                    media_id = msg.get("audio", {}).get("id", "")
                elif msg_type == "voice":
                    media_id = msg.get("voice", {}).get("id", "")
                    msg_type = "audio"  # normalize voice → audio
                elif msg_type == "video":
                    media_id = msg.get("video", {}).get("id", "")
                    caption = msg.get("video", {}).get("caption", "")
                elif msg_type == "document":
                    media_id = msg.get("document", {}).get("id", "")
                    caption = msg.get("document", {}).get("filename", "")

                messages.append({
                    "sender_id": msg.get("from", ""),
                    "sender_name": contacts.get(msg.get("from", ""), ""),
                    "message_id": msg.get("id", ""),
                    "timestamp": msg.get("timestamp", ""),
                    "type": msg_type,
                    "text": text,
                    "media_id": media_id,
                    "caption": caption,
                    "raw": msg,
                })
    return messages


async def download_media(
    api_url: str,
    api_token: str,
    media_id: str,
) -> bytes | None:
    """Download media from WhatsApp Cloud API by media ID.
    Returns raw bytes or None on failure."""
    if not all([api_url, api_token, media_id]):
        return None
    try:
        transport = httpx.AsyncHTTPTransport(local_address="0.0.0.0")
        # Step 1: Get media URL
        async with httpx.AsyncClient(transport=transport, timeout=15.0) as client:
            resp = await client.get(
                f"{api_url}/{media_id}",
                headers={"Authorization": f"Bearer {api_token}"},
            )
            if resp.status_code != 200:
                logger.error(f"Media URL fetch failed: {resp.status_code}")
                return None
            media_url = resp.json().get("url", "")
            if not media_url:
                return None

        # Step 2: Download actual media bytes
        async with httpx.AsyncClient(transport=transport, timeout=30.0) as client:
            resp = await client.get(
                media_url,
                headers={"Authorization": f"Bearer {api_token}"},
            )
            if resp.status_code == 200:
                return resp.content
            logger.error(f"Media download failed: {resp.status_code}")
    except Exception as e:
        logger.error(f"Media download error: {e}")
    return None
