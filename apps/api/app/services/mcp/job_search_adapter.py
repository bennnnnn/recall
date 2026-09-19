"""My Job MCP adapter — list matches or kick off a fresh search from chat.

The heavy search stays in the background runner; the tool only reads stored
matches and enqueues a run, so chat turns stay fast.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import UTC, datetime, timedelta
from typing import Any

from redis.asyncio import Redis
from sqlalchemy import select

from app.core.db import SessionLocal
from app.core.jobs import enqueue
from app.gateways.mcp.base import ToolResult
from app.models.orm import JobMatch, User
from app.models.schemas.tools import JobSearchToolInput
from app.services import plan as plan_service
from app.services.job_search import get_profile_for_user
from app.services.prompt_safety import wrap_untrusted

# Request-scoped identity, same pattern as the web search adapter.
_job_user: ContextVar[User | None] = ContextVar("mcp_job_search_user", default=None)
_job_redis: ContextVar[Redis | None] = ContextVar("mcp_job_search_redis", default=None)

_MANUAL_RUN_COOLDOWN = timedelta(minutes=10)
_LIST_LIMIT = 10


@contextmanager
def bind_job_search_context(
    *,
    user: User | None = None,
    redis: Redis | None = None,
) -> Iterator[None]:
    """Bind the calling turn's user/redis for invoke()."""
    token_user = _job_user.set(user)
    token_redis = _job_redis.set(redis)
    try:
        yield
    finally:
        _job_user.reset(token_user)
        _job_redis.reset(token_redis)


def _match_line(match: JobMatch) -> str:
    fit = f", {match.match_score}% fit" if match.match_score is not None else ""
    return f"- {match.title} at {match.company}{fit} — {match.url}"


class JobSearchAdapter:
    name = "job_search"
    input_schema = JobSearchToolInput

    def describe(self) -> str:
        return (
            "List the user's job matches from My Job, or start a fresh job "
            "search with their My Job profile. Use when the user asks to find "
            "jobs, see their job matches, or check for new openings."
        )

    def to_openai_tool(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.describe(),
                "parameters": JobSearchToolInput.model_json_schema(),
            },
        }

    async def invoke(self, args: dict[str, Any]) -> ToolResult:
        user = _job_user.get()
        if user is None:
            return ToolResult(name=self.name, content="Job search is unavailable right now.")
        action = str(args.get("action") or "list")

        async with SessionLocal() as session:
            profile = await get_profile_for_user(session, user.id)
            if profile is None:
                return ToolResult(
                    name=self.name,
                    content=(
                        "The user has not set up My Job yet. Suggest opening the "
                        "My Job screen to choose roles, location, and resume first."
                    ),
                )
            matches = list(
                (
                    await session.scalars(
                        select(JobMatch)
                        .where(
                            JobMatch.profile_id == profile.id,
                            JobMatch.status != "hidden",
                        )
                        .order_by(JobMatch.found_at.desc())
                        .limit(_LIST_LIMIT)
                    )
                ).all()
            )
            profile_id = profile.id
            last_run_at = profile.last_run_at

        listing = "\n".join(_match_line(match) for match in matches) or "No matches yet."
        listing = wrap_untrusted("job matches", listing)

        if action != "search_now":
            return ToolResult(name=self.name, content=listing)

        redis = _job_redis.get()
        now = datetime.now(UTC)
        if not plan_service.is_pro(user):
            note = (
                "On-demand searches need Recall Pro; the matches below are from "
                "the scheduled weekly search."
            )
        elif redis is None:
            note = "A fresh search cannot start right now; the matches below are the latest."
        elif last_run_at is not None and now - last_run_at < _MANUAL_RUN_COOLDOWN:
            note = "A search ran a few minutes ago; the matches below are the latest."
        else:
            await enqueue(
                redis,
                "job_search_run",
                {"profile_id": str(profile_id), "manual": True},
                dedupe_key=(
                    f"job_search_manual:{profile_id}:"
                    f"{last_run_at.isoformat() if last_run_at else 'never'}"
                ),
            )
            note = "A fresh job search just started; new matches will appear shortly."
        return ToolResult(name=self.name, content=f"{note}\n\n{listing}")
