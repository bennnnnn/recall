"""The ``recall_chats`` tool: the reply's model searches the user's earlier chats.

Whether a turn read past chats was a phrase list (``recalls_shared_past``): "remind me
what you told me about lenses" matched, "what did i ask you earlier about a lens" did
not, and the reply said there was no earlier conversation (2026-11-05). Reading past
chats on every turn sat on the first token, so the model writing the reply is offered
this tool instead: it answers at once, or searches and answers in a second call. A turn
that needs no recall costs nothing more.
"""

from __future__ import annotations

from typing import Any

from app.core.config import Settings
from app.gateways.mcp.base import ToolContext, ToolResult
from app.models.schemas.tools import RecallChatsToolInput
from app.modules.conversation import history_rag
from app.modules.memory.switch import memory_switch_on

RECALL_TOOL = "recall_chats"

# The tool results the model reads when there is nothing to show.
_NOTHING_FOUND = (
    "No earlier chat matches this. Say you couldn't find it in your past chats; do not "
    "fill in what was said from memory."
)
_MEMORY_OFF = "Memory is off, so earlier chats are not searched. Say so; do not guess."


class RecallChatsAdapter:
    name = RECALL_TOOL
    input_schema = RecallChatsToolInput

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def describe(self) -> str:
        return (
            "Search the user's earlier chats with you. Call it before you answer when the "
            "user refers to something said, asked, decided or shared in a past conversation "
            'you cannot see here ("what did I ask you earlier", "the plan we made", '
            '"what was my question before"). Do not call it for general knowledge or for '
            "what is already in this chat. The query names the topic in the user's words "
            "(\"lens question\", \"trip to Rome budget\"), never 'it' or 'that'."
        )

    def to_openai_tool(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.describe(),
                "parameters": RecallChatsToolInput.model_json_schema(),
            },
        }

    async def invoke(self, args: dict[str, Any], ctx: ToolContext) -> ToolResult:
        # One search per turn: a repeat call gets the first call's result.
        first = ctx.first_results.get(self.name)
        if first is not None:
            return first
        if ctx.user is None or not memory_switch_on(ctx.user):
            return ToolResult(name=self.name, content=_MEMORY_OFF)
        query = str(args.get("query") or "").strip() or ctx.user_query
        # Earlier chats only: this chat is already in the prompt (its window and its
        # summary), and its own lines came back as "earlier chats" and crowded out the rest.
        block = await history_rag.retrieve_for_prompt(
            self.settings, user_id=ctx.user.id, query=query, exclude_chat_id=ctx.chat_id
        )
        result = ToolResult(name=self.name, content=block or _NOTHING_FOUND)
        ctx.first_results[self.name] = result
        return result
