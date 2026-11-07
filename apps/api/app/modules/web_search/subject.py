"""The user's earlier lines in the prompt, the current one left out."""

from __future__ import annotations


def collect_prior_user_messages(
    prompt_messages: list[dict[str, str]],
    current: str,
) -> list[str]:
    user_msgs = [str(m.get("content") or "") for m in prompt_messages if m.get("role") == "user"]
    if user_msgs and user_msgs[-1].strip() == current.strip():
        user_msgs = user_msgs[:-1]
    return [msg for msg in user_msgs if msg.strip()]
