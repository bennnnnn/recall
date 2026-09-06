"""Reference-photo lookup MCP adapter — model-callable when the tool loop is on.

Distinct from ``ImageGenAdapter``: this returns a *real* photo (Tavily image
search, mirrored into Recall's storage), never AI-generated art. Persists
the attachment + assistant ``[Image: …]`` marker and signals a terminal turn
via ``ToolResult.data`` — same terminal-image contract ``tool_loop.py``
already understands, so the stream skips the visible LLM pass and the
mobile client renders it with zero new code (never trust the model to
invent attachment URLs).
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any
from uuid import UUID

from redis.asyncio import Redis

from app.core.config import Settings
from app.gateways.mcp.base import ToolResult
from app.models.orm import User
from app.models.tool_schemas import ImageSearchToolInput
from app.services import image_search as image_search_service

_search_user: ContextVar[User | None] = ContextVar("mcp_image_search_user", default=None)
_search_redis: ContextVar[Redis | None] = ContextVar("mcp_image_search_redis", default=None)
_search_chat_id: ContextVar[UUID | None] = ContextVar("mcp_image_search_chat_id", default=None)


@contextmanager
def bind_image_search_context(
    *,
    user: User | None = None,
    redis: Redis | None = None,
    chat_id: UUID | None = None,
) -> Iterator[None]:
    """Bind the calling turn's identity for quota + chat persistence."""
    token_user = _search_user.set(user)
    token_redis = _search_redis.set(redis)
    token_chat = _search_chat_id.set(chat_id)
    try:
        yield
    finally:
        _search_user.reset(token_user)
        _search_redis.reset(token_redis)
        _search_chat_id.reset(token_chat)


class ImageSearchAdapter:
    name = "search_image"
    input_schema = ImageSearchToolInput

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def describe(self) -> str:
        return (
            "Find and attach a REAL reference photo from the web — for "
            "'show me an ear', 'what does a golden retriever look like', "
            "'what does the Eiffel Tower look like'. Call this when the user "
            "wants to see what something actually looks like. "
            "Do NOT use for creative/artistic requests (draw, paint, create "
            "an image of) — use generate_image for those instead."
        )

    def to_openai_tool(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.describe(),
                "parameters": ImageSearchToolInput.model_json_schema(),
            },
        }

    async def invoke(self, args: dict[str, Any]) -> ToolResult:
        query = str(args.get("query") or "").strip()
        if not query:
            return ToolResult(name=self.name, content="Missing query.")

        user = _search_user.get()
        chat_id = _search_chat_id.get()
        if user is None or chat_id is None:
            return ToolResult(
                name=self.name,
                content="Reference-photo lookup is unavailable in this context.",
            )
        if not self.settings.image_search_enabled:
            return ToolResult(name=self.name, content="Reference-photo lookup is disabled.")

        try:
            # User row already exists from turn prep — only write the
            # assistant image marker, same as ImageGenAdapter.
            _user_msg, asst_msg = await image_search_service.search_and_attach_for_chat(
                self.settings,
                user=user,
                chat_id=chat_id,
                query=query,
                create_user_message=False,
            )
        except image_search_service.ImageSearchError as exc:
            return ToolResult(name=self.name, content=f"Photo lookup failed: {exc.detail}")
        except Exception:
            return ToolResult(name=self.name, content="Photo lookup failed unexpectedly.")

        marker = (asst_msg.content or "").strip()
        if not marker.startswith("[Image:"):
            return ToolResult(
                name=self.name,
                content="Photo lookup did not produce an attachment marker.",
            )

        return ToolResult(
            name=self.name,
            content=(
                "Reference photo found and attached. The app will show it — "
                "do not invent URLs or write another reply."
            ),
            data={
                "terminal": True,
                "image_marker": marker,
                "assistant_message_id": str(asst_msg.id),
                "resolved_model": asst_msg.model or "image-search-model",
            },
        )
