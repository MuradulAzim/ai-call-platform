# ============================================================
# Fazle Social Engine — Webhook Handlers
# Processes incoming WhatsApp & Facebook webhook events
# ============================================================
import logging
import uuid
from datetime import datetime, timezone

import httpx
import psycopg2.extras

from whatsapp import parse_incoming_message
from facebook import parse_webhook_entry

logger = logging.getLogger("fazle-social-engine")


async def handle_whatsapp_webhook(payload: dict, db_conn_fn, brain_url: str, get_creds_fn) -> dict:
    """Process an incoming WhatsApp webhook event.
    Flow: parse message → store → call Brain → send AI reply."""
    messages = parse_incoming_message(payload)
    processed = 0

    for msg in messages:
        if not msg["text"]:
            continue

        # Store incoming message
        with db_conn_fn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """INSERT INTO fazle_social_messages
                       (platform, direction, contact_identifier, content, metadata, status)
                       VALUES ('whatsapp', 'incoming', %s, %s, %s, 'received')""",
                    (msg["sender_id"], msg["text"], psycopg2.extras.Json({"sender_name": msg["sender_name"]})),
                )
                # Upsert contact
                cur.execute(
                    """INSERT INTO fazle_social_contacts (name, platform, identifier, metadata)
                       VALUES (%s, 'whatsapp', %s, '{}')
                       ON CONFLICT (platform, identifier) DO UPDATE SET name = EXCLUDED.name""",
                    (msg["sender_name"] or msg["sender_id"], msg["sender_id"]),
                )
            conn.commit()

        # Generate AI reply via Brain
        ai_reply = await _call_brain(brain_url, msg["text"], "whatsapp", msg["sender_name"])
        if ai_reply:
            # Send reply back via WhatsApp API
            creds = get_creds_fn("whatsapp")
            if creds:
                from whatsapp import send_message
                result = await send_message(
                    creds.get("whatsapp_api_url", ""),
                    creds.get("access_token", ""),
                    creds.get("phone_number_id", ""),
                    msg["sender_id"],
                    ai_reply,
                )
                # Store outgoing reply
                with db_conn_fn() as conn:
                    with conn.cursor() as cur:
                        cur.execute(
                            """INSERT INTO fazle_social_messages
                               (platform, direction, contact_identifier, content, status)
                               VALUES ('whatsapp', 'outgoing', %s, %s, %s)""",
                            (msg["sender_id"], ai_reply, "sent" if result.get("sent") else "failed"),
                        )
                    conn.commit()
        processed += 1

    return {"processed": processed, "total_messages": len(messages)}


async def handle_facebook_webhook(payload: dict, db_conn_fn, brain_url: str, get_creds_fn) -> dict:
    """Process an incoming Facebook webhook event.
    Flow: parse event → if comment → sentiment analysis → auto-reply."""
    events = parse_webhook_entry(payload)
    processed = 0

    for event in events:
        if event["field"] == "feed" and event["verb"] in ("add", "edited") and event["message"]:
            # Store incoming message/comment
            with db_conn_fn() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """INSERT INTO fazle_social_messages
                           (platform, direction, contact_identifier, content, metadata, status)
                           VALUES ('facebook', 'incoming', %s, %s, %s, 'received')""",
                        (event["sender_id"], event["message"],
                         psycopg2.extras.Json({"sender_name": event["sender_name"], "post_id": event["post_id"]})),
                    )
                conn.commit()

            # Auto-reply with AI if it's a comment
            if event["item"] == "comment" and event["comment_id"]:
                ai_reply = await _call_brain(
                    brain_url, event["message"], "facebook",
                    event["sender_name"],
                    context="Facebook comment reply. Be brief, friendly, and engaging."
                )
                if ai_reply:
                    creds = get_creds_fn("facebook")
                    if creds:
                        from facebook import reply_to_comment
                        result = await reply_to_comment(
                            event["comment_id"],
                            creds.get("page_access_token", ""),
                            ai_reply,
                        )
                        with db_conn_fn() as conn:
                            with conn.cursor() as cur:
                                cur.execute(
                                    """INSERT INTO fazle_social_messages
                                       (platform, direction, contact_identifier, content, status)
                                       VALUES ('facebook', 'outgoing', %s, %s, %s)""",
                                    (event["sender_id"], ai_reply, "sent" if result.get("sent") else "failed"),
                                )
                            conn.commit()
            processed += 1

    return {"processed": processed, "total_events": len(events)}


async def _call_brain(brain_url: str, message: str, platform: str,
                      sender: str, context: str = "") -> str:
    """Call Fazle Brain API to generate a persona-aware response."""
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{brain_url}/chat",
                json={
                    "message": message,
                    "user": sender or "Social Bot",
                    "conversation_id": f"social-{platform}-{uuid.uuid4().hex[:8]}",
                    "context": context or f"Reply to a {platform} message. Be natural and engaging.",
                },
            )
            if resp.status_code == 200:
                return resp.json().get("reply", "")
    except Exception as e:
        logger.error(f"Brain API call failed: {e}")
    return ""
