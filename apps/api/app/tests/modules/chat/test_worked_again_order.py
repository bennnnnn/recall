"""``worked_again`` in the pipeline: before the answer label, on the last block, wired from
the stream (review of #2602)."""

from __future__ import annotations

from types import SimpleNamespace
from typing import cast
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from app.core.config import Settings
from app.modules.chat import stream_pipeline
from app.modules.chat.finalize_passes import FINALIZE_PASSES, FinalizeState
from app.modules.chat.stream_accum import StreamAccum
from app.modules.chat.turn_outcome import TurnOutcome
from app.modules.chat.turn_prep import StreamContext
from app.modules.chat.worked_again import drop_working_again_pass
from app.tests.modules.chat.test_worked_again import BLOCK, PHYSICS, QUESTION, RECAP, _streamed


def _passes_in_order(text: str, accum: StreamAccum, names: set[str]) -> str:
    """``text`` through the named finalize passes, in the order the pipeline runs them."""
    state = SimpleNamespace(
        text=text,
        server_text=False,
        ctx=SimpleNamespace(
            worked=PHYSICS, worked_layout=accum.worked_layout, user_message_content=QUESTION
        ),
    )
    for finalize_pass in FINALIZE_PASSES:
        if finalize_pass.name in names:
            state.text = cast(str, finalize_pass.run(cast(FinalizeState, state)))
    return state.text


def test_a_recaps_own_answer_label_never_takes_the_blocks_heading() -> None:
    # The recap ends on its own "**Answer:**": the label pass keeps only the last label, so
    # run first it dropped the block's heading and the card had none to land under.
    recap = (
        "Working it again:\n\n$$\\omega_0 = \\frac{2\\pi}{8}$$\n$$v = 4 \\times 0.785$$\n"
        "$$t = \\frac{0 - 0.785}{-0.1}$$\n\n**Answer:** $\\omega_0 = \\frac{2\\pi}{8} \\approx 0.785$"
    )
    text, accum = _streamed(f"{BLOCK}\n\n{recap}")
    kept = _passes_in_order(text, accum, {"worked_again", "answer_labels"})
    assert "**Answer**\n\n$0.79\\,\\mathrm{rad/s}$" in kept
    assert "**Answer:**" not in kept


def test_a_second_block_repeating_the_first_is_the_one_kept() -> None:
    # The second try is a second ```worked block: the layout kept is the last one, and the
    # first, above it, is the working written again.
    first = BLOCK.replace(
        "substitution: \\omega_0 = \\frac{2\\pi}{8}\n",
        "substitution: \\omega_0 = \\frac{2\\pi}{8}\nsubstitution: \\omega_0 = 6.2832 \\div 8\n"
        "substitution: \\omega_0 = 0.7854 \\times 1\n",
    )
    second = first.replace("0.785398", "0.785400")
    text, accum = _streamed(f"{first}\n\n{second}")
    kept = _passes_in_order(text, accum, {"worked_again", "answer_labels"})
    # The last block stands whole, its Answer heading kept for its card.
    assert accum.worked_layout.strip() in kept
    assert kept.rstrip().endswith("**Answer**\n\n$0.79\\,\\mathrm{rad/s}$")
    # The first, holding four sums, is the working written again above it.
    assert kept.count("**Given**") == 1


async def test_the_streamed_layout_reaches_the_finalize_pass() -> None:
    # Through _settle_reply the pass sees the stream's laid-out block and the recap goes:
    # dropping the wiring fails here, not silently in production.
    text, accum = _streamed(f"{BLOCK}\n\n{RECAP}")
    accum.parts = [text]
    ctx = StreamContext(
        user_id=uuid4(),
        chat_id=uuid4(),
        model="free-chat",
        prompt_messages=[{"role": "user", "content": QUESTION}],
        run_title=False,
        user_message_content=QUESTION,
        reserved_tokens=200,
        max_output_tokens=50,
        assistant_message_id=uuid4(),
    )
    ctx.worked = PHYSICS

    async def finalized(*_args: object, **kwargs: object) -> str:
        state = SimpleNamespace(text=kwargs["assistant_text"], server_text=False, ctx=ctx)
        return drop_working_again_pass(cast(FinalizeState, state))

    saved = AsyncMock()
    with (
        patch.object(stream_pipeline, "enrich_final_content", finalized),
        patch.object(stream_pipeline, "await_user_message_persist", AsyncMock()),
        patch.object(stream_pipeline, "register_and_enqueue_finalize", saved),
    ):
        await stream_pipeline._settle_reply(
            MagicMock(),
            MagicMock(),
            Settings(),
            ctx,
            usage={},
            accum=accum,
            should_cancel=None,
            outcome=TurnOutcome(),
            resources=None,
        )
    assert ctx.worked_layout == accum.worked_layout
    assert ctx.worked_layout
    assert saved.await_args is not None
    assert "step-by-step" not in saved.await_args.kwargs["assistant_text"]
