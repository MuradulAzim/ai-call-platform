# ============================================================
# Fazle Brain — Content Safety Module
# Filters harmful content using OpenAI Moderation API with
# relationship-aware thresholds (stricter for children)
# ============================================================
import httpx
import logging
from typing import Optional

logger = logging.getLogger("fazle-brain")

# Category thresholds — lower = stricter
# For child accounts (daughter/son), use CHILD_THRESHOLDS
DEFAULT_THRESHOLDS = {
    "sexual": 0.5,
    "hate": 0.7,
    "harassment": 0.7,
    "self-harm": 0.3,
    "sexual/minors": 0.01,
    "hate/threatening": 0.5,
    "violence/graphic": 0.5,
    "violence": 0.7,
    "harassment/threatening": 0.5,
    "self-harm/intent": 0.2,
    "self-harm/instructions": 0.2,
}

CHILD_THRESHOLDS = {
    "sexual": 0.05,
    "hate": 0.3,
    "harassment": 0.4,
    "self-harm": 0.05,
    "sexual/minors": 0.001,
    "hate/threatening": 0.2,
    "violence/graphic": 0.1,
    "violence": 0.3,
    "harassment/threatening": 0.2,
    "self-harm/intent": 0.05,
    "self-harm/instructions": 0.05,
}

BLOCKED_RESPONSE = (
    "I'd rather not go there. Let's talk about something else!"
)

CHILD_BLOCKED_RESPONSE = (
    "Hmm, let's talk about something more fun instead! 😊"
)


def _get_thresholds(relationship: Optional[str]) -> dict:
    if relationship in ("daughter", "son"):
        return CHILD_THRESHOLDS
    return DEFAULT_THRESHOLDS


async def check_content(
    text: str,
    openai_api_key: str,
    relationship: Optional[str] = None,
) -> dict:
    """Check text against OpenAI Moderation API.

    Returns:
        {"safe": True} or {"safe": False, "reason": str, "blocked_reply": str}
    """
    if not openai_api_key or not text.strip():
        return {"safe": True}

    thresholds = _get_thresholds(relationship)

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                "https://api.openai.com/v1/moderations",
                headers={
                    "Authorization": f"Bearer {openai_api_key}",
                    "Content-Type": "application/json",
                },
                json={"input": text},
            )
            resp.raise_for_status()
            data = resp.json()
    except Exception as e:
        logger.warning(f"Moderation API call failed: {e}")
        # CRITICAL: Fail closed for child accounts
        if relationship in ("daughter", "son", "child"):
            return {
                "safe": False,
                "reason": "moderation_unavailable",
                "blocked_reply": CHILD_BLOCKED_RESPONSE,
            }
        # Adults: fail open — don't block if the API is down
        return {"safe": True, "reason": "moderation_unavailable"}

    result = data.get("results", [{}])[0]
    scores = result.get("category_scores", {})

    for category, threshold in thresholds.items():
        score = scores.get(category, 0)
        if score >= threshold:
            logger.info(
                f"Content blocked: category={category} score={score:.3f} "
                f"threshold={threshold} relationship={relationship}"
            )
            blocked_reply = (
                CHILD_BLOCKED_RESPONSE
                if relationship in ("daughter", "son")
                else BLOCKED_RESPONSE
            )
            return {
                "safe": False,
                "reason": category,
                "blocked_reply": blocked_reply,
            }

    return {"safe": True}
