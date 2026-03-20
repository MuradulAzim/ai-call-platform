# ============================================================
# Fazle Social Engine — Workflow Automation Tasks
# Integrates with Fazle Workflow Engine for automation rules
# ============================================================
import httpx
import logging
from datetime import datetime, timezone

logger = logging.getLogger("fazle-social-engine")


async def trigger_workflow(workflow_engine_url: str, event_type: str, payload: dict) -> dict:
    """Notify the Workflow Engine of a social event to trigger automation rules.

    Event types:
      - whatsapp.message.received
      - facebook.comment.received
      - facebook.post.created
      - social.campaign.started
    """
    if not workflow_engine_url:
        return {"triggered": False, "reason": "Workflow engine URL not configured"}

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{workflow_engine_url}/trigger",
                json={
                    "event": event_type,
                    "source": "social-engine",
                    "payload": payload,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
            )
            if resp.status_code == 200:
                return {"triggered": True, "workflow_id": resp.json().get("id")}
            return {"triggered": False, "reason": f"Workflow engine returned {resp.status_code}"}
    except Exception as e:
        logger.error(f"Workflow trigger failed: {e}")
        return {"triggered": False, "reason": str(e)}


async def check_keyword_rules(db_conn_fn, platform: str, message: str) -> list[dict]:
    """Check if incoming message matches any keyword automation rules."""
    matched = []
    with db_conn_fn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT id, name, config FROM fazle_social_campaigns
                   WHERE platform = %s AND campaign_type = 'keyword_trigger'
                   AND status = 'running'""",
                (platform,),
            )
            for row in cur.fetchall():
                config = row[2] if row[2] else {}
                keywords = config.get("keywords", [])
                msg_lower = message.lower()
                for kw in keywords:
                    if kw.lower() in msg_lower:
                        matched.append({
                            "campaign_id": str(row[0]),
                            "campaign_name": row[1],
                            "keyword": kw,
                            "response_template": config.get("response_template", ""),
                        })
                        break
    return matched


async def process_scheduled_items(db_conn_fn, send_whatsapp_fn, send_facebook_fn):
    """Process pending scheduled items whose time has arrived.
    Called periodically by the main service or a background task."""
    now = datetime.now(timezone.utc)
    with db_conn_fn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT id, platform, action_type, payload
                   FROM fazle_social_scheduled
                   WHERE status = 'pending' AND scheduled_at <= %s
                   LIMIT 20""",
                (now,),
            )
            rows = cur.fetchall()

        for row in rows:
            item_id, platform, action_type, payload = row
            try:
                if platform == "whatsapp" and action_type == "send":
                    await send_whatsapp_fn(payload)
                elif platform == "facebook" and action_type == "post":
                    await send_facebook_fn(payload)

                with conn.cursor() as cur:
                    cur.execute(
                        "UPDATE fazle_social_scheduled SET status = 'completed' WHERE id = %s",
                        (item_id,),
                    )
                conn.commit()
            except Exception as e:
                logger.error(f"Scheduled item {item_id} failed: {e}")
                with conn.cursor() as cur:
                    cur.execute(
                        "UPDATE fazle_social_scheduled SET status = 'failed' WHERE id = %s",
                        (item_id,),
                    )
                conn.commit()

    return {"processed": len(rows)}
