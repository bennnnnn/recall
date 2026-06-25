"""Automatic model routing.

When a request uses the ``auto`` alias (or a user whose default model is
``auto``), pick a concrete model per message: cheap/fast for simple turns,
the stronger model for harder ones. Heuristic only — no extra LLM call — so
it stays snappy and free.
"""

_SMART_TRIGGERS = (
    "explain",
    "why",
    "prove",
    "analyze",
    "analyse",
    "debug",
    "optimize",
    "optimise",
    "algorithm",
    "complexity",
    "architecture",
    "refactor",
    "trade-off",
    "tradeoff",
    "step by step",
    "reason",
    "derive",
    "compare",
    "evaluate",
    "design a",
)

_LONG_MESSAGE_CHARS = 500


def route_chat_model(content: str) -> str:
    """Return a concrete chat alias for an auto-routed message."""
    text = content.lower()
    if len(content) >= _LONG_MESSAGE_CHARS:
        return "smart-chat"
    if "```" in content:
        return "smart-chat"
    if any(trigger in text for trigger in _SMART_TRIGGERS):
        return "smart-chat"
    return "free-chat"


def resolve_alias(alias: str, content: str) -> str:
    """Resolve ``auto`` to a concrete alias; pass everything else through."""
    if alias == "auto":
        return route_chat_model(content)
    return alias
