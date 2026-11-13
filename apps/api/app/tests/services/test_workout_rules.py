"""The worked-solution rules a prompt carries read as sentences: none runs into the next.

"…never the symbol written twice.Carry **Substitution**…" went to every physics prompt
(review of PR #2420).
"""

from __future__ import annotations

import re

import pytest

from app.services import workout

# A sentence's full stop with the next sentence (or its bold heading) straight after it.
_RUN_ON = re.compile(r"[a-z][.!?;:](?:\*\*)?[A-Z]")

_RULES = sorted(
    name
    for name in dir(workout)
    if name.isupper() and isinstance(getattr(workout, name), str) and " " in getattr(workout, name)
)


def test_the_prompt_rules_are_found() -> None:
    assert "PHYSICS_WORKOUT_PROMPT_RULE" in _RULES and "MATH_WORKOUT_PROMPT_RULE" in _RULES


@pytest.mark.parametrize("name", _RULES)
def test_no_rule_runs_one_sentence_into_the_next(name: str) -> None:
    text = getattr(workout, name)
    assert [text[max(0, m.start() - 20) : m.end() + 10] for m in _RUN_ON.finditer(text)] == []
