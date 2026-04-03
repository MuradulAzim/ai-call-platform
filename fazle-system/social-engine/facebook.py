# ============================================================
# Fazle Social Engine — Facebook Graph API Integration
# Handles posts, comments, reactions via Facebook Graph API
# ============================================================
import httpx
import logging

logger = logging.getLogger("fazle-social-engine")

GRAPH_API_BASE = "https://graph.facebook.com/v19.0"


async def create_post(
    page_id: str,
    page_access_token: str,
    message: str,
    image_url: str | None = None,
) -> dict:
    """Create a post on a Facebook page."""
    if not page_id or not page_access_token:
        return {"posted": False, "error": "Facebook credentials not configured"}

    try:
        transport = httpx.AsyncHTTPTransport(local_address="0.0.0.0")
        async with httpx.AsyncClient(transport=transport, timeout=15.0) as client:
            payload = {"message": message, "access_token": page_access_token}
            if image_url:
                payload["url"] = image_url
                endpoint = f"{GRAPH_API_BASE}/{page_id}/photos"
            else:
                endpoint = f"{GRAPH_API_BASE}/{page_id}/feed"

            resp = await client.post(endpoint, data=payload)
            if resp.status_code == 200:
                return {"posted": True, "post_id": resp.json().get("id")}
            return {"posted": False, "error": f"API returned {resp.status_code}: {resp.text[:200]}"}
    except Exception as e:
        logger.error(f"Facebook post failed: {e}")
        return {"posted": False, "error": str(e)}


async def reply_to_comment(
    target_id: str,
    page_access_token: str,
    message: str,
) -> dict:
    """Reply to a comment on Facebook."""
    if not page_access_token:
        return {"sent": False, "error": "Facebook token not configured"}

    try:
        transport = httpx.AsyncHTTPTransport(local_address="0.0.0.0")
        async with httpx.AsyncClient(transport=transport, timeout=15.0) as client:
            resp = await client.post(
                f"{GRAPH_API_BASE}/{target_id}/comments",
                data={"message": message, "access_token": page_access_token},
            )
            if resp.status_code == 200:
                return {"sent": True, "comment_id": resp.json().get("id")}
            return {"sent": False, "error": f"API returned {resp.status_code}"}
    except Exception as e:
        logger.error(f"Facebook comment reply failed: {e}")
        return {"sent": False, "error": str(e)}


async def react_to_post(
    target_id: str,
    page_access_token: str,
    reaction_type: str = "LIKE",
) -> dict:
    """React to a Facebook post or comment."""
    valid = {"LIKE", "LOVE", "HAHA", "WOW", "SAD", "ANGRY"}
    if reaction_type.upper() not in valid:
        return {"sent": False, "error": f"Invalid reaction. Must be one of: {', '.join(valid)}"}

    if not page_access_token:
        return {"sent": False, "error": "Facebook token not configured"}

    try:
        transport = httpx.AsyncHTTPTransport(local_address="0.0.0.0")
        async with httpx.AsyncClient(transport=transport, timeout=10.0) as client:
            resp = await client.post(
                f"{GRAPH_API_BASE}/{target_id}/reactions",
                data={"type": reaction_type.upper(), "access_token": page_access_token},
            )
            return {"sent": resp.status_code == 200}
    except Exception as e:
        logger.error(f"Facebook react failed: {e}")
        return {"sent": False, "error": str(e)}


async def get_page_posts(
    page_id: str,
    page_access_token: str,
    limit: int = 25,
) -> list[dict]:
    """Fetch recent posts from a Facebook page via Graph API."""
    if not page_id or not page_access_token:
        return []
    try:
        transport = httpx.AsyncHTTPTransport(local_address="0.0.0.0")
        async with httpx.AsyncClient(transport=transport, timeout=15.0) as client:
            resp = await client.get(
                f"{GRAPH_API_BASE}/{page_id}/feed",
                params={"access_token": page_access_token, "limit": limit,
                        "fields": "id,message,created_time,type"},
            )
            if resp.status_code == 200:
                return resp.json().get("data", [])
    except Exception as e:
        logger.error(f"Facebook get posts failed: {e}")
    return []


async def get_post_comments(
    post_id: str,
    page_access_token: str,
    limit: int = 50,
) -> list[dict]:
    """Fetch comments on a Facebook post."""
    if not page_access_token:
        return []
    try:
        transport = httpx.AsyncHTTPTransport(local_address="0.0.0.0")
        async with httpx.AsyncClient(transport=transport, timeout=15.0) as client:
            resp = await client.get(
                f"{GRAPH_API_BASE}/{post_id}/comments",
                params={"access_token": page_access_token, "limit": limit,
                        "fields": "id,from,message,created_time"},
            )
            if resp.status_code == 200:
                return resp.json().get("data", [])
    except Exception as e:
        logger.error(f"Facebook get comments failed: {e}")
    return []


def parse_webhook_entry(payload: dict) -> list[dict]:
    """Parse incoming Facebook webhook events (comment/message notifications)."""
    events = []
    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            field = change.get("field", "")
            value = change.get("value", {})
            events.append({
                "page_id": entry.get("id", ""),
                "field": field,
                "item": value.get("item", ""),
                "verb": value.get("verb", ""),
                "sender_id": value.get("from", {}).get("id", ""),
                "sender_name": value.get("from", {}).get("name", ""),
                "message": value.get("message", ""),
                "post_id": value.get("post_id", ""),
                "comment_id": value.get("comment_id", ""),
                "raw": value,
            })
    return events
