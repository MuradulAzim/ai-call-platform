# ============================================================
# WBOM Retry Queue — Reliable delivery for WhatsApp→WBOM
# Uses Redis list as a retry queue with max 5 attempts.
# ============================================================
import asyncio
import json
import logging
import time
from typing import Optional

import httpx
import redis

logger = logging.getLogger("fazle-social-engine.wbom-retry")

_QUEUE_KEY = "wbom_retry_queue"
_MAX_RETRIES = 5
_RETRY_INTERVAL = 15  # seconds between retry sweeps

_redis_client: Optional[redis.Redis] = None
_wbom_url: str = ""
_wbom_internal_key: str = ""
_worker_task: Optional[asyncio.Task] = None


def init_retry_worker(redis_url: str, wbom_url: str, wbom_internal_key: str = ""):
    """Initialise Redis connection and start the background retry worker."""
    global _redis_client, _wbom_url, _wbom_internal_key
    if not redis_url or not wbom_url:
        return
    try:
        _redis_client = redis.Redis.from_url(redis_url, decode_responses=True)
        _redis_client.ping()
        _wbom_url = wbom_url.rstrip("/")
        _wbom_internal_key = wbom_internal_key
        logger.info("WBOM retry queue connected (redis=%s)", redis_url)
    except Exception as e:
        logger.warning("WBOM retry queue Redis init failed: %s", e)
        _redis_client = None


def start_retry_loop():
    """Start the async retry loop (call after event-loop is running)."""
    global _worker_task
    if _redis_client and _worker_task is None:
        _worker_task = asyncio.create_task(_retry_loop())
        logger.info("WBOM retry worker started (interval=%ds, max_retries=%d)", _RETRY_INTERVAL, _MAX_RETRIES)


def enqueue_failed_message(payload: dict):
    """Push a failed WBOM message onto the retry queue."""
    if not _redis_client:
        logger.warning("Retry queue unavailable — dropping WBOM message")
        return
    item = {
        "payload": payload,
        "retry_count": 0,
        "enqueued_at": time.time(),
    }
    _redis_client.lpush(_QUEUE_KEY, json.dumps(item))
    logger.info("Enqueued WBOM message for retry (sender=%s)", payload.get("sender_number", "?"))


async def _retry_loop():
    """Background worker: pop items from queue, retry HTTP call, re-queue on failure."""
    while True:
        try:
            await asyncio.sleep(_RETRY_INTERVAL)
            if not _redis_client:
                continue

            queue_len = _redis_client.llen(_QUEUE_KEY)
            if queue_len == 0:
                continue

            # Process up to 20 items per sweep
            for _ in range(min(queue_len, 20)):
                raw = _redis_client.rpop(_QUEUE_KEY)
                if not raw:
                    break
                item = json.loads(raw)
                payload = item["payload"]
                retry_count = item.get("retry_count", 0)

                success = await _try_send(payload)
                if success:
                    logger.info("WBOM retry succeeded (attempt=%d, sender=%s)",
                                retry_count + 1, payload.get("sender_number", "?"))
                else:
                    retry_count += 1
                    if retry_count >= _MAX_RETRIES:
                        logger.error(
                            "WBOM message PERMANENTLY FAILED after %d retries: sender=%s body=%.80s",
                            retry_count, payload.get("sender_number", "?"),
                            payload.get("message_body", ""),
                        )
                    else:
                        item["retry_count"] = retry_count
                        _redis_client.lpush(_QUEUE_KEY, json.dumps(item))
                        logger.warning("WBOM retry %d/%d failed, re-queued (sender=%s)",
                                       retry_count, _MAX_RETRIES, payload.get("sender_number", "?"))
        except Exception as e:
            logger.error("WBOM retry loop error: %s", e)


async def _try_send(payload: dict) -> bool:
    """Attempt to POST to WBOM process-message endpoint."""
    headers = {}
    if _wbom_internal_key:
        headers["X-INTERNAL-KEY"] = _wbom_internal_key
    try:
        async with httpx.AsyncClient(timeout=10.0, headers=headers) as client:
            resp = await client.post(
                f"{_wbom_url}/api/subagent/wbom/process-message",
                json=payload,
            )
            return resp.status_code < 500
    except Exception:
        return False
