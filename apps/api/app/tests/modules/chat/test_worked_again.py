"""Working written again outside the laid-out ```worked block goes (``chat.worked_again``).

Grade 11 physics round (2026-11-26): after the layout's last card a model wrote "Here are
the step-by-step solutions for each part of your problem:" and every part again in $$
lines, the whole derivation as prose above **Given**, or a visible re-check ("Let's
verify: …"). A sentence with one sum in it, the one-line summary and a picture stay.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import cast

from app.modules.chat.finalize_passes import FinalizeState
from app.modules.chat.stream_accum import StreamAccum
from app.modules.chat.worked_again import drop_working_again_pass, relations_in
from app.modules.chat.worked_render import WorkedLayout
from app.modules.chat.worked_stream import ReplyFilter

PHYSICS = WorkedLayout(law_heading=True)
BLOCK = (
    "```worked\n"
    "given: T | 8 | s | period\n"
    "required: \\omega_0 | initial angular velocity\n"
    "formula: Angular velocity | \\omega_0 = \\frac{2\\pi}{T}\n"
    "substitution: \\omega_0 = \\frac{2\\pi}{8}\n"
    "substitution: \\omega_0 = 0.785398\\,\\mathrm{rad/s}\n"
    "answer: \\omega_0 | 0.785398 | rad/s\n"
    "```"
)
QUESTION = "A wheel turns once every 8 s. Find its initial angular velocity."
RECAP = (
    "Here are the step-by-step solutions for each part of your problem:\n\n"
    "**a) Initial Angular Velocity**\nThe wheel turns once every 8 seconds.\n"
    "$$\\omega_0 = \\frac{2\\pi}{8}$$\n$$\\omega_0 = 0.785$$\n\n**b) Linear Velocity**\n"
    "$$v = 4 \\times 0.785$$\n$$v \\approx 3.14$$\n\n**c) Time to Stop**\n"
    "$$t = \\frac{0 - 0.785}{-0.1}$$"
)
GRAPH = "```graph\n{}\n```"


def _streamed(reply: str) -> tuple[str, StreamAccum]:
    accum = StreamAccum()
    reply_filter = ReplyFilter(accum, PHYSICS)
    for start in range(0, len(reply), 7):
        if sent := reply_filter.feed(reply[start : start + 7]):
            accum.shown.append(sent)
    if tail := reply_filter.flush():
        accum.shown.append(tail)
    return "".join(accum.shown), accum


def _finalized(reply: str, question: str = QUESTION) -> str:
    text, accum = _streamed(reply)
    state = SimpleNamespace(
        text=text,
        server_text=False,
        ctx=SimpleNamespace(
            worked=PHYSICS, worked_layout=accum.worked_layout, user_message_content=question
        ),
    )
    return drop_working_again_pass(cast(FinalizeState, state))


def test_the_layout_is_kept_for_the_pass() -> None:
    text, accum = _streamed(BLOCK)
    assert accum.worked_layout.startswith("**Given**")
    assert accum.worked_layout.strip() in text


def test_the_working_said_again_after_the_block_goes() -> None:
    text = _finalized(f"{BLOCK}\n\n{RECAP}")
    assert "step-by-step" not in text
    assert "$$" not in text
    assert text.rstrip().endswith("**Answer**\n\n$0.79\\,\\mathrm{rad/s}$")


def test_the_summary_and_a_picture_stay_when_the_recap_goes() -> None:
    summary = "The wheel's initial angular velocity is about 0.79 rad/s."
    text = _finalized(f"{BLOCK}\n\n{summary}\n\n{RECAP}\n\n{GRAPH}")
    assert summary in text
    assert GRAPH in text
    assert "step-by-step" not in text


def test_a_derivation_above_the_block_goes() -> None:
    lead = (
        "To find it we use the angular velocity.\n\n"
        "$$\\omega_0 = \\frac{2\\pi}{T}$$\n$$\\omega_0 = \\frac{2\\pi}{8}$$\n"
        "$$\\omega_0 = 6.2832 \\div 8 = 0.785$$"
    )
    text = _finalized(f"{lead}\n\n{BLOCK}")
    assert text.startswith("**Given**")


def test_a_sentence_with_one_sum_after_the_block_stays() -> None:
    note = (
        "Note: with $\\mu_s = 0.4$ the friction needed exceeds the most available, "
        "$f = 1.96\\,\\mathrm{N}$, so the cylinder would slip."
    )
    reply = f"{BLOCK}\n\n{note}"
    text, _accum = _streamed(reply)
    assert _finalized(reply) == text


def test_a_question_asking_for_reasoning_keeps_what_follows() -> None:
    question = "Explain why the wheel turns at 2π/8 rad/s and show your reasoning."
    reply = f"{BLOCK}\n\n{RECAP}"
    text, _accum = _streamed(reply)
    assert _finalized(reply, question) == text


def test_a_reply_with_no_block_is_left_alone() -> None:
    reply = f"Wait, let me check.\n\n{RECAP}"
    state = SimpleNamespace(
        text=reply,
        server_text=False,
        ctx=SimpleNamespace(worked=PHYSICS, worked_layout="", user_message_content=QUESTION),
    )
    assert drop_working_again_pass(cast(FinalizeState, state)) == reply


def test_only_maths_that_works_a_sum_counts() -> None:
    assert relations_in("$v = 4 \\times 3$ and $$t \\approx \\frac{7}{2}$$ then $x \\le 2$") == 2
    # A value stated alone: an assumption, a unit, a negative number.
    assert relations_in("$u = 0$, $a = -1.2\\,\\mathrm{m/s^2}$ and $g = 9.8$") == 0
    assert relations_in("costs $5 and $6") == 0


def test_an_assumption_list_with_one_sum_stays() -> None:
    assumptions = (
        "### Assumptions\n\n1. The stone starts at rest ($u = 0$).\n"
        "2. Gravity is $g = 9.8\\,\\mathrm{m/s^2}$.\n\n"
        "Ignoring sound, $d = \\frac{1}{2}(9.8)(2^2) = 19.6\\,\\mathrm{m}$."
    )
    reply = f"{BLOCK}\n\n{assumptions}"
    text, _accum = _streamed(reply)
    assert _finalized(reply) == text


def test_the_block_is_found_when_a_pass_changed_a_line_of_it() -> None:
    text, accum = _streamed(f"{BLOCK}\n\n{RECAP}\n\n$0.79\\,\\mathrm{{rad/s}}$")
    changed = text.replace("**Required**", "**Required** ")
    state = SimpleNamespace(
        text=changed,
        server_text=False,
        ctx=SimpleNamespace(
            worked=PHYSICS, worked_layout=accum.worked_layout, user_message_content=QUESTION
        ),
    )
    kept = drop_working_again_pass(cast(FinalizeState, state))
    # The block ends at its own answer, not at the same line written again after the recap.
    assert "step-by-step" not in kept and "$$" not in kept
    assert "**Answer**\n\n$0.79\\,\\mathrm{rad/s}$" in kept


def test_words_before_the_working_starts_again_stay() -> None:
    described = (
        "**Part (a): Velocity-time graph**\n\nTo draw the graph, plot time across and "
        "velocity up, then join (0, 0), (20, 18) and (80, 18)."
    )
    text = _finalized(f"{BLOCK}\n\n{described}\n\n**Part (b): Again**\n\n{RECAP}")
    assert described in text
    assert "Part (b)" not in text and "step-by-step" not in text and "$$" not in text
