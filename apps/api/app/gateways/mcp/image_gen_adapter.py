"""Image generation MCP adapter — model-callable when the tool loop is on.

Persists the attachment + assistant ``[Image: …]`` marker and signals a
terminal turn via ``ToolResult.data`` so the stream skips the visible LLM
pass (never trust the model to invent attachment URLs).
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
from app.models.tool_schemas import GenerateImageToolInput
from app.services import image_generation as image_generation_service
from app.services import plan as plan_service

_image_user: ContextVar[User | None] = ContextVar("mcp_image_gen_user", default=None)
_image_redis: ContextVar[Redis | None] = ContextVar("mcp_image_gen_redis", default=None)
_image_chat_id: ContextVar[UUID | None] = ContextVar("mcp_image_gen_chat_id", default=None)


@contextmanager
def bind_image_gen_context(
    *,
    user: User | None = None,
    redis: Redis | None = None,
    chat_id: UUID | None = None,
) -> Iterator[None]:
    """Bind the calling turn's identity for Pro/quota + chat persistence."""
    token_user = _image_user.set(user)
    token_redis = _image_redis.set(redis)
    token_chat = _image_chat_id.set(chat_id)
    try:
        yield
    finally:
        _image_user.reset(token_user)
        _image_redis.reset(token_redis)
        _image_chat_id.reset(token_chat)


class ImageGenAdapter:
    name = "generate_image"
    input_schema = GenerateImageToolInput

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def describe(self) -> str:
        return (
            "Generate a new picture for the user and attach it to this chat. "
            "Call ONLY when they clearly want a visual image/illustration/photo "
            "(e.g. draw a cat, create a sunset pic). "
            "Do NOT use for math examples, equations, quizzes, code, todos, "
            "diagrams/charts (use sympy), or ordinary chat follow-ups."
        )

    def to_openai_tool(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.describe(),
                "parameters": GenerateImageToolInput.model_json_schema(),
            },
        }

    async def invoke(self, args: dict[str, Any]) -> ToolResult:
        prompt = str(args.get("prompt") or "").strip()
        if not prompt:
            return ToolResult(name=self.name, content="Missing prompt.")

        user = _image_user.get()
        chat_id = _image_chat_id.get()
        if user is None or chat_id is None:
            return ToolResult(
                name=self.name,
                content="Image generation is unavailable in this context.",
            )
        if not self.settings.image_generation_enabled:
            return ToolResult(name=self.name, content="Image generation is disabled.")
        if not plan_service.is_pro(user):
            return ToolResult(
                name=self.name,
                content="Image generation requires Pro.",
            )

        aspect = args.get("aspect_ratio")
        aspect_ratio = aspect if isinstance(aspect, str) else None

        try:
            # User row already exists from turn prep — only write the assistant
            # image marker. Keyword / HTTP paths may still create both.
            _user_msg, asst_msg = await image_generation_service.generate_for_chat(
                self.settings,
                user=user,
                chat_id=chat_id,
                prompt=prompt,
                aspect_ratio=aspect_ratio,
                create_user_message=False,
            )
        except image_generation_service.ImageGenerationError as exc:
            return ToolResult(
                name=self.name,
                content=f"Image generation failed: {exc.detail}",
            )
        except Exception:
            return ToolResult(
                name=self.name,
                content="Image generation failed unexpectedly.",
            )

        marker = (asst_msg.content or "").strip()
        if not marker.startswith("[Image:"):
            return ToolResult(
                name=self.name,
                content="Image generation did not produce an attachment marker.",
            )

        return ToolResult(
            name=self.name,
            content=(
                "Image generated. The app will show it — do not invent URLs or write another reply."
            ),
            data={
                "terminal": True,
                "image_marker": marker,
                "assistant_message_id": str(asst_msg.id),
                "resolved_model": asst_msg.model or "image-gen-model",
            },
        )
