"""RevenueCat REST API — subscriber entitlement lookup."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

import httpx

logger = logging.getLogger(__name__)

REVENUECAT_API = "https://api.revenuecat.com/v1/subscribers"


async def fetch_subscriber(secret_key: str, app_user_id: str) -> dict[str, Any] | None:
    if not secret_key.strip():
        return None
    url = f"{REVENUECAT_API}/{app_user_id}"
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(
                url,
                headers={
                    "Authorization": f"Bearer {secret_key.strip()}",
                    "Accept": "application/json",
                },
            )
            if response.status_code == 404:
                return None
            response.raise_for_status()
            payload = response.json()
            return payload if isinstance(payload, dict) else None
    except Exception:
        logger.exception("RevenueCat subscriber fetch failed user=%s", app_user_id)
        try:
            import sentry_sdk

            sentry_sdk.add_breadcrumb(
                category="billing.revenuecat",
                message="subscriber fetch failed",
                level="error",
                data={"app_user_id": app_user_id},
            )
            sentry_sdk.capture_message(
                "RevenueCat subscriber fetch failed",
                level="warning",
            )
        except Exception:
            logger.debug("RevenueCat fetch metric report failed", exc_info=True)
        return None


def entitlement_active(payload: dict[str, Any], entitlement_id: str) -> bool:
    subscriber = payload.get("subscriber")
    if not isinstance(subscriber, dict):
        return False
    entitlements = subscriber.get("entitlements")
    if not isinstance(entitlements, dict):
        return False
    ent = entitlements.get(entitlement_id)
    if not isinstance(ent, dict):
        return False
    expires_raw = ent.get("expires_date")
    if expires_raw is None:
        return True
    if not isinstance(expires_raw, str) or not expires_raw.strip():
        return True
    try:
        normalized = expires_raw.replace("Z", "+00:00")
        expires = datetime.fromisoformat(normalized)
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=UTC)
        return expires > datetime.now(UTC)
    except ValueError:
        logger.warning("Invalid RevenueCat expires_date: %s", expires_raw)
        return False
