"""Review probes: finalize passes that undo, duplicate or contradict each other (2026-11-19).

Each test runs a model reply through the real finalize (``enrich_final_content``) on the real
turn context its prompt builds (``route_case``), and asserts the defect, so it passes while the
defect exists. They document ``docs/review/2026-11-19-finalize-pipeline.md`` and are skipped in
CI. A fix turns one red: then delete it, or invert it into the fix's own test.

    RECALL_REVIEW_PROBES=1 uv run pytest app/tests/review/test_finalize_conflicts.py -q
"""

from __future__ import annotations

import asyncio
import os
from dataclasses import replace
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

import pytest

from app.modules.chat.finalize_passes import enrich_final_content
from app.modules.chat.turn_deps import default_deps
from app.modules.chat.turn_outcome import TurnOutcome
from app.services.answer_fence import VERIFIED_ANSWER_MARKER
from app.tests.behavior.cases import Case, Expect
from app.tests.behavior.harness import (
    _no_reminders,
    _no_session,
    battery_settings,
    offline_pubchem,
    route_case,
)

pytestmark = [
    pytest.mark.skipif(
        os.environ.get("RECALL_REVIEW_PROBES") != "1",
        reason="review probe: documents a finalize conflict; run with RECALL_REVIEW_PROBES=1",
    ),
    pytest.mark.usefixtures("thread_sympy_executor"),
]


def _done(value: Any) -> asyncio.Future[Any]:
    future: asyncio.Future[Any] = asyncio.get_running_loop().create_future()
    future.set_result(value)
    return future


async def _finalize(
    prompt: str,
    reply: str,
    *,
    history: tuple[tuple[str, str], ...] = (),
    formal: tuple[float, str, tuple[float, ...]] | None = None,
) -> tuple[Any, str]:
    """``reply`` as the model wrote it on ``prompt``'s turn, saved through every pass.

    ``formal``: the formal reader's answer (value, unit), as the physics read's task gives it
    (it needs a model, so it is stubbed here, with the live read saying physics).
    """
    route = await route_case(Case("probe", "probe", prompt, Expect(), "", history=history))
    ctx = route.context
    ctx.instant_reply = None  # the model wrote this reply
    if formal is not None:
        ctx.live_read = _done(SimpleNamespace(subject="physics"))
        ctx.formal = _done(_formal_answer(*formal))
    deps = replace(
        default_deps(),
        session_factory=_no_session,
        users=SimpleNamespace(get_by_id=AsyncMock(return_value=None)),
        todos=SimpleNamespace(materialize_reminder_fences=AsyncMock(side_effect=_no_reminders)),
    )
    with offline_pubchem():
        saved = await enrich_final_content(
            deps,
            AsyncMock(),
            battery_settings(),
            ctx,
            assistant_text=reply,
            usage={},
            outcome=TurnOutcome(),
            was_cancelled=False,
            should_cancel=None,
        )
    return route, saved


def _formal_answer(value: float, unit: str, uses: tuple[float, ...] = ()) -> Any:
    """The formal reader's answer in the shape this checkout's ``FormalAnswer`` takes: main's
    (value, unit), or #2501's per-part values with the range the standard constants allow
    and the stated numbers the value is worked from."""
    from app.services.formal import answer as formal_answer

    value_type = getattr(formal_answer, "FormalValue", None)
    if value_type is None:
        return formal_answer.FormalAnswer(value, unit)
    part = value_type(
        part="",
        symbol="",
        value=value,
        unit=unit,
        low=value * 0.997,
        high=value * 1.003,
        uses=uses,
    )
    # #2501's FormalAnswer takes per-part values; main's type checker knows only (value, unit).
    newer: Any = formal_answer.FormalAnswer
    return newer(values=(part,))


def _cards(text: str) -> list[str]:
    from app.services.answer_fence import ANSWER_FENCE_LANGS
    from app.services.md_fence_scan import iter_fences

    return [
        text[fence.body_start : fence.body_end]
        for fence in iter_fences(text)
        if fence.closed and fence.lang in ANSWER_FENCE_LANGS
    ]


# --- 1. formal_answer overrules the reply's own right card -----------------------------------

_BLOCK = (
    "A rectangular block of mass 50 kg lies with a side 2m by 1m on a table. "
    "What is the pressure exerted by its weight on the table? (g = 10 m/s2)"
)
_BLOCK_REPLY = (
    "**Given**\n$m = 50\\,\\mathrm{kg}$, $A = 2\\,\\mathrm{m^2}$, $g = 10\\,\\mathrm{m/s^2}$\n\n"
    "**Required**\nP\n\n**Substitution**\n$W = 50 \\times 10 = 500\\,\\mathrm{N}$\n"
    "$P = \\frac{500}{2} = 250\\,\\mathrm{Pa}$\n\n**Answer**\n\n```answer\n250 Pa\n```"
)


async def test_conflict_1_formal_answer_replaces_a_right_card() -> None:
    """The question states g = 10; the reply works with it to 250 Pa. The formal reader's
    setup took 9.81 (245.25 Pa): ``formal_answer`` lands its card in the reply's place and
    the working above still ends at 250 Pa. The turn is also dispatched as maths (the maths
    fence pass demoted the reply's card first) while the live read says physics."""
    route, saved = await _finalize(_BLOCK, _BLOCK_REPLY, formal=(245.25, "Pa", (50.0, 2.0)))
    assert route.subject == "math"
    assert _cards(saved) and "245" in _cards(saved)[0]
    assert "250\\,\\mathrm{Pa}" in saved  # the working's own value, now contradicted


# --- 2. formal_answer's card contradicts the working it sits under ---------------------------

_PARALLEL = (
    "A 75Ω lamp and 150Ω heater are connected in parallel across a 150V potential difference. "
    "What current flows through the entire circuit?"
)
_PARALLEL_REPLY = (
    "**Given**\n$R_1 = 75\\,\\Omega$, $R_2 = 150\\,\\Omega$, $V = 150\\,\\mathrm{V}$\n\n"
    "**Required**\n$I$\n\n**Substitution**\n"
    "$R = \\frac{75 \\times 150}{75 + 150} = 50\\,\\Omega$\n"
    "$I = \\frac{150}{50} = 3\\,\\mathrm{A}$\n\n**Answer**\n\n$I = 3\\,\\mathrm{A}$"
)


async def test_conflict_2_formal_card_under_working_that_says_otherwise() -> None:
    """Whichever value is right, the saved reply says both: the working ends I = 3 A, and
    the card under it, from another reading, says 2 A. Nothing re-reads the working."""
    _route, saved = await _finalize(
        _PARALLEL, _PARALLEL_REPLY, formal=(2.0, "A", (75.0, 150.0, 150.0))
    )
    assert "I = 3\\,\\mathrm{A}" in saved
    assert len(_cards(saved)) == 1 and "2\\" in _cards(saved)[0]


async def test_conflict_2b_working_check_lands_the_card_formal_agrees() -> None:
    """Control: when the formal answer agrees, working_check lands the reply's own card."""
    _route, saved = await _finalize(
        _PARALLEL, _PARALLEL_REPLY, formal=(3.0, "A", (75.0, 150.0, 150.0))
    )
    assert len(_cards(saved)) == 1 and "3" in _cards(saved)[0]


# --- 3. the maths fence pass demotes a card that working_check does not re-land -------------

_TRIP = "A car travels 100 m in 8 s, then 60 m in 4 s. What is its average speed?"


async def test_conflict_3_demoted_card_left_as_a_bare_line() -> None:
    """On an unsolved physics turn the maths fence pass (``rewrite_answer_fences``,
    ``math/fence_conflict.py``) unwraps the model's ```answer card; ``working_check`` re-lands
    a card only from working it recognises, so the value is left as a bare line under the
    Answer heading: the orphan-line shape of the 2026-11-18 round."""
    reply = (
        "**Given**\n$d_1 = 100\\,\\mathrm{m}$\n\n**Required**\nAverage speed\n\n"
        "**Substitution**\n$v = \\frac{160}{12} = 13.33\\,\\mathrm{m/s}$\n\n"
        "**Answer**\n\n```answer\n13.3 m/s\n```"
    )
    _route, saved = await _finalize(_TRIP, reply)
    assert _cards(saved) == []
    assert saved.rstrip().endswith("**Answer**\n\n13.3 m/s")


async def test_conflict_3b_answer_heading_in_another_language() -> None:
    """The same with an Amharic heading: the card is demoted and nothing re-lands it."""
    reply = "$I = \\frac{150}{50} = 3\\,\\mathrm{A}$\n\n**መልስ**\n\n```answer\n3 A\n```"
    _route, saved = await _finalize(_PARALLEL, reply)
    assert _cards(saved) == []
    assert saved.rstrip().endswith("3 A")


# --- 4. a stripped picture leaves its claim -------------------------------------------------


async def test_conflict_4_stripped_graph_leaves_its_lead() -> None:
    """The maths fence pass strips a ```graph no solver wrote, on a physics turn too; the
    sentence presenting it stays. The saved reply (and the running summary that reads it)
    says a graph is shown that is not."""
    reply = (
        "Here is the v–t graph of the car's motion:\n\n"
        '```graph\n{"type": "function", "functions": [{"expression": "t", "label": "v(t)"}], '
        '"x_min": 0, "x_max": 10}\n```\n\nThe slope is the acceleration, 1 m/s².'
    )
    route, saved = await _finalize(
        "A car starts from rest and reaches a velocity of 10 m/s in 10 s. "
        "Draw the v against t graph for the motion of the car.",
        reply,
    )
    assert route.subject == "physics"
    assert "```graph" not in saved and "```simulation" not in saved
    assert "Here is the v–t graph" in saved


# --- 5. a money card on a physics question --------------------------------------------------


async def test_conflict_5_loan_card_under_a_physics_answer() -> None:
    """The money reader and the subject dispatch both claim the turn; ``money_card`` attaches
    whenever money owns its read, whatever the subject: a car-loan calculator under a
    physics answer."""
    reply = (
        "**Given**\n$a = 0.06 \\times 9.81 = 0.5886\\,\\mathrm{m/s^2}$, $t = 5\\,\\mathrm{s}$\n\n"
        "**Required**\n$v$\n\n**Substitution**\n$v = 0.5886 \\times 5 = 2.943\\,\\mathrm{m/s}$\n\n"
        "**Answer**\n\n$v = 2.94\\,\\mathrm{m/s}$"
    )
    route, saved = await _finalize(
        "A car accelerates at 6% of g for 5 s from rest. What is its final speed?", reply
    )
    assert route.subject == "physics"
    assert "```calculator" in saved and '"product":"loan"' in saved


# --- 6. an unclosed card skips every check, then close_fences closes it ----------------------


async def test_conflict_6_open_card_ships_unchecked_on_a_solved_turn() -> None:
    """A reply cut off inside its card: the subject passes read closed fences only, so the
    model's wrong 18 J is neither replaced nor demoted; ``close_fences`` (after every fence
    reader) then closes it. The solved turn's verified 9 J never appears."""
    route, saved = await _finalize(
        "A 2 kg ball moves at 3 m/s. What is its kinetic energy?",
        "KE = ½ × 2 × 3² = 9 J\n\n**Answer**\n\n```answer\n18 J",
    )
    assert route.solved
    assert _cards(saved) == ["18 J\n"] or [card.strip() for card in _cards(saved)] == ["18 J"]
    assert VERIFIED_ANSWER_MARKER not in saved


async def test_conflict_6b_open_card_kept_where_a_closed_one_is_demoted() -> None:
    """Unsolved turn: closed, the card is demoted (conflict 3); left open, it ships as a card."""
    _route, saved = await _finalize(
        _TRIP, "v = 160 / 12 = 13.33 m/s\n\n**Answer**\n\n```answer\n12 m/s"
    )
    assert [card.strip() for card in _cards(saved)] == ["12 m/s"]


# --- 7. the closing line ------------------------------------------------------------------


async def test_conflict_7_closing_summary_dropped_by_two_owners() -> None:
    """A one-line closing summary is wanted (owner). On a solved turn the subject's fence
    pass drops it; on an unsolved one ``working_check`` drops it (``drop_restated_tail``)."""
    solved_reply = (
        "**Substitution**\n$KE = \\tfrac12 \\times 2 \\times 3^2 = 9\\,\\mathrm{J}$\n\n"
        "**Answer**\n\n```answer\n9 J\n```\n\nThe kinetic energy is 9 J."
    )
    _route, solved = await _finalize(
        "A 2 kg ball moves at 3 m/s. What is its kinetic energy?", solved_reply
    )
    assert "The kinetic energy is" not in solved
    unsolved_reply = (
        "**Substitution**\n$v = \\frac{160}{12} = 13.33\\,\\mathrm{m/s}$\n\n"
        "**Answer**\n\n$v = 13.33\\,\\mathrm{m/s}$\n\n"
        "The car's average speed is $13.33\\,\\mathrm{m/s}$."
    )
    _route, unsolved = await _finalize(_TRIP, unsolved_reply)
    assert "The car's average speed is" not in unsolved


# --- 8. a flowchart stands in for a drawing -------------------------------------------------

_FLOWCHART = (
    "Here is a diagram:\n\n```mermaid\nflowchart LR\n  A[Object] --> B[Lens]\n  B --> C[Image]\n```"
    "\n\nThe image is real and inverted."
)


async def test_conflict_8_flowchart_kept_for_a_ray_diagram() -> None:
    """A ray diagram asked for, nothing drawn by the server: the model's flowchart is the
    only picture (``mermaid_and_places`` sanitizes it; nothing asks whether it answers)."""
    route, saved = await _finalize(
        "Draw a ray diagram for an object placed between F and 2F of a convex lens.", _FLOWCHART
    )
    assert route.subject == "physics"
    assert "```mermaid" in saved and "```simulation" not in saved


async def test_conflict_8b_flowchart_beside_the_server_figure() -> None:
    """A triangle asked for: the server's ```geometry and the model's flowchart, both shown."""
    _route, saved = await _finalize("Draw a right triangle with legs 3 cm and 4 cm.", _FLOWCHART)
    assert "```mermaid" in saved and "```geometry" in saved
