"""The held-out questions: their faithful English passes the translation check, and the
pattern readers give no wrong card on what it keeps (docs/MODEL_READER.md).

Written by a reviewer after the word tables were filled, so they measure the check on
questions it was not shaped by. No model call: the English is the reviewer's own.
"""

from __future__ import annotations

import pytest

from app.modules.chemistry.given_units import CHEMISTRY_UNITS
from app.modules.model_reader.translation import check_translation
from app.modules.physics import PHYSICS_UNITS
from app.tests.behavior.reader_eval import _with_prompt
from app.tests.behavior.reader_translate import heldout_entries
from app.tests.behavior.stem_sweep import SUBJECT_NAMES, run_entry

_TABLES = (PHYSICS_UNITS, CHEMISTRY_UNITS)
# Kept of 40 when the set was added: raise it when the check keeps more, never lower it.
_KEPT_FLOOR = 40


@pytest.mark.asyncio
async def test_held_out_translations_are_kept_and_never_answered_wrong(
    thread_sympy_executor: None,
) -> None:
    kept = 0
    wrong: list[str] = []
    for language, subject, entry, english in heldout_entries():
        if check_translation(entry.prompt, english, _TABLES, language) != "ok":
            continue
        kept += 1
        outcome = await run_entry(_with_prompt(entry, english), SUBJECT_NAMES[subject])
        wrong += [entry.id for problem in outcome.problems if problem.kind == "wrong"]
    assert wrong == []
    assert kept >= _KEPT_FLOOR
