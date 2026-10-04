"""Shared entitlement checks and token accounting for paid job assistance."""

from __future__ import annotations

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.models.orm import User
from app.modules.billing import is_pro
from app.services import model_catalog, quota


async def check_spending(
    session: AsyncSession, user: User, redis: Redis, settings: Settings
) -> None:
    from app.modules.job_search.service import JobSearchError

    await session.refresh(user)
    if not is_pro(user):
        raise JobSearchError("My Job requires Recall Pro", status_code=403)
    if await quota.global_spend_exceeded(redis, settings):
        raise JobSearchError("Spending limit reached. Please try later.", status_code=429)


async def record_tokens(redis: Redis, model_alias: str, usage: dict[str, int]) -> None:
    amount = model_catalog.estimate_cost_usd(
        model_alias, input_tokens=usage.get("input", 0), output_tokens=usage.get("output", 0)
    )
    if amount:
        await quota.record_global_spend(redis, amount)
    import logging

    logging.getLogger(__name__).info(
        "my_job_assistance_usage",
        extra={
            "model": model_alias,
            "input_tokens": usage.get("input", 0),
            "output_tokens": usage.get("output", 0),
            "estimated_usd": amount,
        },
    )
