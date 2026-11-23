"""Where a provider may cache a chat prompt, for the models that cache only a marked prefix.

A chat prompt opens with two system messages (``modules/chat/prompt_builder``): the
stable one, the same text on every turn for this user (who Recall is, the tone and
unclear-message rules, their own instructions and language), then the rules this kind
of turn needs; the history and what changes on every turn follow. Most providers reuse
the longest prefix they have seen by themselves. A model flagged ``cache_breakpoints``
(Anthropic's) caches only up to a ``cache_control`` mark, so its stable message goes as
one text part carrying the mark: OpenRouter's format, which LiteLLM forwards for Claude.
Only that message is marked: the rules differ between a slim and a rich turn, and a
mark that is not read again pays the cache write (1.25x) for nothing.
"""

from __future__ import annotations

from typing import Any

from app.models.model_catalog import ChatModel

# The cache lifetime every caching provider offers; it renews on each hit.
EPHEMERAL = {"type": "ephemeral"}


def with_cache_breakpoint(
    messages: list[dict[str, Any]],
    route: ChatModel,
    *,
    enabled: bool = True,
    history: bool = False,
) -> list[dict[str, Any]]:
    """``messages`` with the stable system message marked, when ``route`` needs the mark.

    ``enabled`` is the ``prompt_cache_breakpoints_enabled`` setting. Only a stable
    message followed by the turn's own system message is marked: a lone system prompt
    holds that turn's text too, and a mark on it would pay a cache write on every turn
    and never be read. ``history`` (``prompt_cache_history_breakpoint_enabled``) also
    marks the last reply before the turn's line: the next turn's prompt repeats every
    message up to it until the chat's next fold (``context_window.FoldRule``), and the
    provider finds that mark looking back from its own. The messages are not changed in
    place.
    """
    if not enabled or not route.cache_breakpoints or len(messages) < 2:
        return messages
    stable, turn = messages[0], messages[1]
    if stable.get("role") != "system" or turn.get("role") != "system":
        return messages
    marked = _marked(stable)
    if marked is None:
        return messages
    out = [marked, *messages[1:]]
    last_reply = _last_reply_index(out) if history else None
    if last_reply is not None:
        reply = _marked(out[last_reply])
        if reply is not None:
            out[last_reply] = reply
    return out


def _marked(message: dict[str, Any]) -> dict[str, Any] | None:
    """The message as one text part carrying the mark; None when its content is not text."""
    text = message.get("content")
    if not isinstance(text, str) or not text:
        return None
    return {
        **message,
        "content": [{"type": "text", "text": text, "cache_control": dict(EPHEMERAL)}],
    }


def _last_reply_index(messages: list[dict[str, Any]]) -> int | None:
    """The last assistant message before the turn's own user line, if the prompt ends so.

    A tool round's second call ends with the round (the reply's tool-call message, the
    tool results, the notes they bring); the turn's line is the one before them, so the
    mark stays where the first call wrote it and that call's cache is read.
    """
    line = _turn_line_index(messages)
    if line is None:
        return None
    for index in range(line - 1, 1, -1):
        role = messages[index].get("role")
        if role == "assistant":
            return index
        if role == "user":
            return None
    return None


def _turn_line_index(messages: list[dict[str, Any]]) -> int | None:
    """The turn's user line: the last message, or the last one before a tool round."""
    index = len(messages) - 1
    while index >= 0 and _in_tool_round(messages[index]):
        index -= 1
    if index < 0 or messages[index].get("role") != "user":
        return None
    return index


def _in_tool_round(message: dict[str, Any]) -> bool:
    role = message.get("role")
    return role in ("tool", "system") or (role == "assistant" and bool(message.get("tool_calls")))
