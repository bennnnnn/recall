"""Every STEM sweep question is answered right or left to the model, never wrong.

The STEM sweep (``stem_sweep.py``) runs homework questions through the real
chat path and reads the verified answer card. A wrong number, a misread turn, a
reply out of shape or a broken picture fails its own test. Questions the solver
declines, and pictures it does not draw, are coverage: held by floors that only
go up. Raise a floor when a change answers more.
"""

from __future__ import annotations

import pytest

from app.tests.behavior.stem_sweep import (
    SUBJECT_NAMES,
    Entry,
    answered,
    drawn,
    load,
    run,
    run_entry,
)

# subject -> (answered, drawn) on the current corpus
FLOORS = {"physics": (265, 47)}
EXPECTS = {"answer", "explain", "decline", "not_subject"}

ENTRIES = [(subject, entry) for subject in FLOORS for entry in load(subject)]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("subject", "entry"),
    [pytest.param(subject, entry, id=f"{subject}:{entry.id}") for subject, entry in ENTRIES],
)
async def test_stem_turn_is_never_wrong(
    subject: str, entry: Entry, thread_sympy_executor: None
) -> None:
    outcome = await run_entry(entry, SUBJECT_NAMES[subject])
    assert not outcome.critical, f"{entry.prompt!r}: " + "; ".join(
        f"{problem.kind}: {problem.text}" for problem in outcome.critical
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("subject", sorted(FLOORS))
async def test_stem_coverage_holds_its_floor(subject: str, thread_sympy_executor: None) -> None:
    outcomes = await run(load(subject), SUBJECT_NAMES[subject])
    floor_answered, floor_drawn = FLOORS[subject]
    assert len(answered(outcomes)) >= floor_answered
    assert len(drawn(outcomes)) >= floor_drawn


@pytest.mark.parametrize("subject", sorted(FLOORS))
def test_stem_corpus_is_well_formed(subject: str) -> None:
    entries = load(subject)
    ids = [entry.id for entry in entries]
    assert len(ids) == len(set(ids)), "entry ids repeat"
    for entry in entries:
        assert entry.expect in EXPECTS, entry.id
        assert entry.prompt.strip(), entry.id
        assert (entry.answer is not None) == (entry.expect == "answer"), entry.id
