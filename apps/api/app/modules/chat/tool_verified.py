"""The turn's verified block after the tool loop's own solve."""

from __future__ import annotations

from dataclasses import replace
from typing import Any

from app.core.config import Settings
from app.modules.chat.turn_trace import note_numbers_gate
from app.modules.chat.whole_question import answers_with
from app.services.solving import VerifiedMathBlock
from app.services.verified_numbers import gate_card


async def with_tool_verified(server: Any, tool: Any, question: str, settings: Settings) -> Any:
    """The turn's verified block after the tool loop.

    A block the server built from the user's own text is never replaced by one
    the model's tool call produced: the model may have mistyped the problem.
    A maths block may gain a diagram the server did not draw; its answer stays.
    The tool's block is held to the question as the server's is: a card the gate
    dropped from the server's solve never comes back through the model's call.
    """
    if server is None:
        if not answers_with(question, tool):
            return None
        gated = await gate_card(question, tool, settings)
        if not gated.stands:
            note_numbers_gate(settings.verified_numbers_gate, gated.missed)
            return None
        return tool
    if not isinstance(server, VerifiedMathBlock) or not isinstance(tool, VerifiedMathBlock):
        return server
    kinds = {
        fence.get("type") for fence in (server.canonical_fence, *server.canonical_fences) if fence
    }
    kinds.add("answer")
    extra: list[dict[str, Any]] = []
    for fence in (tool.canonical_fence, *tool.canonical_fences):
        if fence and fence.get("type") not in kinds:
            kinds.add(fence.get("type"))
            extra.append(fence)
    if not extra:
        return server
    return replace(server, canonical_fences=[*server.canonical_fences, *extra])
