"""Working written again outside the laid-out ```worked block goes (``chat.worked_again``).

Grade 11 physics round (2026-11-26): after the layout's last card a model wrote "Here are
the step-by-step solutions for each part of your problem:" and every part again in $$
lines, the whole derivation as prose above **Given**, or a visible re-check ("Let's
verify: …"). A sentence with one sum in it, the one-line summary and a picture stay.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import cast

import pytest

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
# The block's working said again: every number in it is the block's (a rounding of one).
RECAP = (
    "Here are the step-by-step solutions for each part of your problem:\n\n"
    "**a) Initial Angular Velocity**\nThe wheel turns once every 8 seconds.\n"
    "$$\\omega_0 = \\frac{2\\pi}{T}$$\n$$\\omega_0 = \\frac{2\\pi}{8}$$\n"
    "$$\\omega_0 = 2\\pi \\div 8 = 0.785$$\n$$\\omega_0 \\approx 0.79$$"
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
            worked=PHYSICS, worked_layouts=accum.worked_layouts, user_message_content=question
        ),
    )
    return drop_working_again_pass(cast(FinalizeState, state))


def test_the_layout_is_kept_for_the_pass() -> None:
    text, accum = _streamed(BLOCK)
    assert accum.worked_layouts[-1].startswith("**Given**")
    assert accum.worked_layouts[-1].strip() in text


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
        "$$\\omega_0 = 2\\pi \\div 8 = 0.785$$"
    )
    text = _finalized(f"{lead}\n\n{BLOCK}")
    # The derivation goes; the words before it, which work nothing, may stay.
    assert "$$" not in text
    assert "**Given**" in text


def test_sentences_with_a_sum_each_after_the_block_stay() -> None:
    # Each note works one sum: two of them are no working (three would be). Review of #2602:
    # with no sum in either, this held whatever the rule did.
    note = (
        "Note: the friction needed exceeds the most available, "
        "$f = 0.4 \\times 0.5 \\times 9.8 = 1.96\\,\\mathrm{N}$, so the cylinder would slip."
    )
    other = "The pull at the top adds torque: $\\tau = 10 \\times 0.1 = 1\\,\\mathrm{N\\,m}$."
    assert relations_in(note) == relations_in(other) == 1
    for reply in (f"{BLOCK}\n\n{note}", f"{BLOCK}\n\n{note}\n\n{other}"):
        text, _accum = _streamed(reply)
        assert _finalized(reply) == text
    # A third sum makes a working; the one saying the block again goes, the two notes with
    # numbers of their own stay.
    third = "Then $\\omega_0 = 2\\pi \\div 8 = 0.785$ again."
    kept = _finalized(f"{BLOCK}\n\n{note}\n\n{other}\n\n{third}")
    assert "again." not in kept
    assert note in kept and other in kept


def test_stated_values_with_units_and_powers_of_ten_are_no_sums() -> None:
    note = (
        "We took $g = 9.8\\,\\mathrm{m/s}^2$, $c = 3 \\times 10^8\\,\\mathrm{m/s}$ and "
        "$h = 6.63 \\times 10^{-34}$."
    )
    assert relations_in(note) == 0
    reply = f"{BLOCK}\n\n{note}"
    text, _accum = _streamed(reply)
    assert _finalized(reply) == text


def test_a_one_line_check_after_the_card_stays() -> None:
    # The unverified answer's **Check** line (SELF_CHECK_PROMPT_RULE) is no second try.
    check = "**Check**\n\n$0.785 \\times 8 = 6.28$"
    reply = f"{BLOCK}\n\n{check}"
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
        ctx=SimpleNamespace(worked=PHYSICS, worked_layouts=(), user_message_content=QUESTION),
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
            worked=PHYSICS, worked_layouts=accum.worked_layouts, user_message_content=QUESTION
        ),
    )
    kept = drop_working_again_pass(cast(FinalizeState, state))
    # The block ends at its own answer, not at the same line written again after the recap.
    assert "step-by-step" not in kept and "$$" not in kept
    assert "**Answer**\n\n$0.79\\,\\mathrm{rad/s}$" in kept


TWO_PARTS = (
    "```worked\ngiven: T | 8 | s | period\ngiven: r | 4 | m | radius\n"
    "required: \\omega_0 | angular velocity\nrequired: v | speed\n"
    "part: a | angular velocity\nformula: Angular velocity | \\omega_0 = \\frac{2\\pi}{T}\n"
    "substitution: \\omega_0 = \\frac{2\\pi}{8}\nsubstitution: \\omega_0 = 0.785398\n"
    "answer: \\omega_0 | 0.785398 | rad/s\n"
    "part: b | speed\nformula: Speed | v = r\\omega_0\nsubstitution: v = 4 \\times 0.785398\n"
    "substitution: v = 3.14159\nanswer: v | 3.14159 | m/s\n```"
)
PART_C = (
    "**(c) Time to stop**\n\nWith $\\alpha = -0.1\\,\\mathrm{rad/s^2}$:\n\n"
    "$$t = \\frac{0 - 0.7854}{-0.1}$$\n$$t = 7.854 \\div 1$$\n$$t = 7.854 - 0 = 7.854\\ \\text{s}$$"
)


def test_two_blocks_one_per_part_both_stay() -> None:
    # Review of #2602: one block per part; the first is a part, never a repeat of the last.
    first = BLOCK
    second = TWO_PARTS.replace("part: a |", "part: c |").replace("part: b |", "part: d |")
    for reply in (f"{first}\n\n{second}", f"{first}\n\nNow the speed.\n\n{second}"):
        text, accum = _streamed(reply)
        assert len(accum.worked_layouts) == 2
        assert _finalized(reply) == text


def test_a_part_the_block_left_out_stays() -> None:
    # Review of #2602: a block covering (a) and (b), then (c) worked in $$ lines.
    for part in (PART_C, PART_C.replace("**(c) Time to stop**", "**Part (c): Stopping**")):
        reply = f"{TWO_PARTS}\n\n{part}"
        text, _accum = _streamed(reply)
        assert _finalized(reply) == text


def test_new_working_with_numbers_of_its_own_stays() -> None:
    # No label, but numbers the block never holds: work it left out, never a repeat.
    extra = (
        "The time to stop follows from the deceleration:\n\n"
        "$$t = \\frac{0 - 0.7854}{-0.1}$$\n$$t = 7.854 \\div 1$$\n$$s = 4 \\times 3.0843 = 12.34$$"
    )
    reply = f"{TWO_PARTS}\n\n{extra}"
    text, _accum = _streamed(reply)
    assert _finalized(reply) == text


@pytest.mark.parametrize(
    "summary",
    [
        "So the wheel turns at about 0.79 rad/s.",
        "**The wheel's angular velocity is about 0.79 rad/s.**",
    ],
)
def test_the_summary_stays_and_not_the_closer_in_its_place(summary: str) -> None:
    # Review of #2602: a recap, the real summary, then a generic closer. The closer pass
    # strips the closer later; the summary must survive this one.
    closer = "Let me know if you have any other questions!"
    kept = _finalized(f"{BLOCK}\n\n{RECAP}\n\n{summary}\n\n{closer}")
    assert summary in kept
    assert "step-by-step" not in kept and "$$" not in kept


def test_stated_values_in_an_assumption_list_are_no_sums() -> None:
    # Review of #2602: degrees and bare units after a number state a value.
    assumptions = (
        "**Assumptions**\n\n- the launch angle is $\\theta = 30^\\circ$\n"
        "- the speed is $u = 20 m/s$\n- gravity is $g = 9.8 m/s^2$, "
        "or $g = 9.8\\,\\mathrm{m\\,s^{-2}}$"
    )
    assert relations_in(assumptions) == 0
    reply = f"{BLOCK}\n\n{assumptions}"
    text, _accum = _streamed(reply)
    assert _finalized(reply) == text


def test_words_before_the_working_starts_again_stay() -> None:
    described = (
        "**Part (a): Velocity-time graph**\n\nTo draw the graph, plot time across and "
        "velocity up, then join (0, 0), (20, 18) and (80, 18)."
    )
    text = _finalized(f"{BLOCK}\n\n{described}\n\n**Part (b): Again**\n\n{RECAP}")
    assert described in text
    assert "Part (b)" not in text and "step-by-step" not in text and "$$" not in text
