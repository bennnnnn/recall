"""A sentence that tells the user about the prompt's own parts comes off a reply."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.modules.chat.finalize_passes import FINALIZE_PASSES, STOPPED_REPLY_PASSES
from app.modules.chat.prompt_leaks import drop_prompt_leaks, drop_prompt_leaks_pass

ANSWER = "For a first investment, a low-cost index fund is a sound start."
# The live reply (2026-10-25), on an investing question.
LIVE_LEAK = (
    "The memory block contains details that don't match this conversation. It names a "
    "different person and preferences that conflict with what you've told me, so I'm "
    "setting it aside and answering from what you've shared, Dev."
)


@pytest.mark.parametrize(
    ("reply", "expected"),
    [
        (f"{LIVE_LEAK}\n\n{ANSWER}", ANSWER),
        (f"{LIVE_LEAK} {ANSWER}", ANSWER),
        (
            f"Sure thing, Dev! Your saved memory block lists a nursing exam. {ANSWER}",
            f"Sure thing, Dev! {ANSWER}",
        ),
        (f"My system prompt says your name on file is Dev. {ANSWER}", ANSWER),
        (f"Per the [Chemistry note], no IUPAC name came back. {ANSWER}", ANSWER),
        (f"[BEGIN UNTRUSTED CONTENT — saved memory] was empty.\n\n{ANSWER}", ANSWER),
        (
            f"Hi Dev!\n\n- The profile block about you says Chicago.\n- {ANSWER}",
            f"Hi Dev!\n\n- {ANSWER}",
        ),
        # The sentence that points back at the leak goes with it; the next one stays.
        (
            f"The memory block names a different person. That is set aside. {ANSWER}",
            f"That is set aside. {ANSWER}",
        ),
        (
            f"The memory block names a different person. It conflicts with what you've told "
            f"me. {ANSWER}",
            ANSWER,
        ),
    ],
)
def test_a_sentence_about_the_prompt_comes_off(reply: str, expected: str) -> None:
    assert drop_prompt_leaks(reply, "how should I start investing?") == expected


@pytest.mark.parametrize(
    "reply",
    [
        # Everyday meanings of the same words.
        "When you call `free()`, the memory block goes back to the heap.",
        "malloc returns a pointer to a memory block of at least the requested size.",
        "A system prompt sets the model's role before the first user message.",
        "Your profile block in the CMS template holds the avatar and bio.",
        # Words about the user without a prompt part.
        "Earlier I called you Sam; sorry, Dev. Here is the plan for this conversation.",
        f"From what you've told me, a low-risk start fits. {ANSWER}",
        # Inside code, a table or a heading nothing changes.
        "```python\n# the memory block on file for this conversation\nx = 1\n```",
        "Use `system prompt on file` as the key.",
        "| term | meaning |\n| --- | --- |\n| memory block about you | a note |",
        "## The memory block in this conversation",
        ANSWER,
    ],
)
def test_other_replies_are_left_alone(reply: str) -> None:
    assert drop_prompt_leaks(reply, "why does free crash?") == reply


@pytest.mark.parametrize(
    "query",
    [
        "What does your system prompt say about me?",
        "write a system prompt for my support bot",
        "what's in the memory block?",
    ],
)
def test_a_turn_that_asks_about_prompts_keeps_its_reply(query: str) -> None:
    reply = f"My system prompt says your name on file is Dev. {ANSWER}"
    assert drop_prompt_leaks(reply, query) == reply


def test_a_reply_that_is_only_a_leak_is_kept() -> None:
    assert drop_prompt_leaks(LIVE_LEAK, "hi") == LIVE_LEAK


def _state(text: str, *, server_text: bool = False) -> SimpleNamespace:
    ctx = SimpleNamespace(user_message_content="how do I start investing?")
    return SimpleNamespace(text=text, ctx=ctx, server_text=server_text)


def test_the_pass_cleans_a_model_reply_and_never_server_text() -> None:
    reply = f"{LIVE_LEAK}\n\n{ANSWER}"
    assert drop_prompt_leaks_pass(_state(reply)) == ANSWER  # type: ignore[arg-type]
    assert drop_prompt_leaks_pass(_state(reply, server_text=True)) == reply  # type: ignore[arg-type]


def test_the_pass_runs_on_every_reply_and_a_stopped_one() -> None:
    names = [finalize_pass.name for finalize_pass in FINALIZE_PASSES]
    assert names.index("prompt_leaks") == names.index("meta_notes") + 1
    assert "prompt_leaks" in STOPPED_REPLY_PASSES
