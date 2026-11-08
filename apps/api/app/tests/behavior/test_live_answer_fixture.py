"""The composer's live answer and the chat turn read a keyboard draft to one value.

While the math keyboard is open the phone works out a draft that is a calculation and shows
its value under it as each key lands (``apps/mobile/lib/math/live/answer.ts``). Send still asks
the server, so the two must agree: ``docs/fixtures/live_answer_cases.json`` holds drafts, the
calculation in SymPy's words and SymPy's value, and the phone's jest test
(``lib/math/live/__tests__/liveAnswerFixture.test.ts``) holds its answer to the same file.

Here SymPy works out each ``sympy`` text and must give the stored ``value``
(``UPDATE_LIVE_ANSWER_FIXTURE=1`` writes it), and the chat turn, when it verifies a draft on
Send, must verify that value too. A case with a ``server_gap`` is one the turn still misreads:
a strict expected failure until the fix deletes the line. A null ``value`` is a draft that
shows no live answer (``why`` says why); the phone's test holds those.

    UPDATE_LIVE_ANSWER_FIXTURE=1 uv run pytest app/tests/behavior/test_live_answer_fixture.py
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

import pytest
from sympy import N, Rational, simplify
from sympy.parsing.sympy_parser import parse_expr, rationalize, standard_transformations

from app.modules.math.solve.latex_normalize import normalize_latex_to_sympy
from app.modules.math.solve.parse import parse_expression
from app.tests.behavior.cases import Case, Expect
from app.tests.behavior.harness import route_case

FIXTURE = Path(__file__).resolve().parents[5] / "docs" / "fixtures" / "live_answer_cases.json"
_TRANSFORMATIONS = (*standard_transformations, rationalize)
_LOG_BASE = re.compile(r"\\log_\{([^{}]+)\}\s*(\S+)")
_SIZING = re.compile(r"\\(?:left|right)")
# SymPy's own LaTeX braces a function's argument: ``\sinh{\left(1 \right)}``.
_BRACED_CALL = re.compile(r"(\\[A-Za-z]+)\{(\([^{}]*\))\}")
_RELATIVE = 1e-9


def _load() -> dict[str, Any]:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def _sympy_value(text: str) -> str | None:
    """SymPy's value: an exact fraction, else 15 significant digits; ``None`` if not real."""
    value = simplify(parse_expr(text, transformations=_TRANSFORMATIONS))
    if value.is_Rational:
        return str(value)
    if not (value.is_real and value.is_finite):
        return None
    return str(N(value, 15))


def _number(value: str) -> float:
    return float(Rational(value))


def _close(a: float, b: float) -> bool:
    return abs(a - b) <= _RELATIVE * max(1.0, abs(b))


def _turn_value(answer: str) -> complex | None:
    """The number the turn verified: the last side of ``3 + 1 * 2 = 5``, read by SymPy."""
    tail = answer.rsplit("=", 1)[-1].strip()
    if "undefined" in tail:
        return None
    tail = _BRACED_CALL.sub(r"\1\2", _SIZING.sub("", tail))
    tail = _LOG_BASE.sub(r"\\log(\2, \1)", tail)
    return complex(N(parse_expression(normalize_latex_to_sympy(f"${tail}$"))))


def _cases() -> list[dict[str, Any]]:
    return _load()["cases"]


def _turn_param(case: dict[str, Any]) -> object:
    gap = case.get("server_gap")
    marks = [pytest.mark.xfail(reason=gap, strict=True)] if gap else []
    return pytest.param(case, id=case["id"], marks=marks)


def test_live_answer_fixture_is_sympys_value() -> None:
    data = _load()
    if os.environ.get("UPDATE_LIVE_ANSWER_FIXTURE"):
        for case in data["cases"]:
            case["value"] = _sympy_value(case["sympy"]) if case["sympy"] else None
        FIXTURE.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    ids = [case["id"] for case in data["cases"]]
    assert len(ids) == len(set(ids)), "case ids repeat"
    for case in data["cases"]:
        if case["sympy"] is None:
            assert case["value"] is None and case.get("why"), f"{case['id']}: say why no answer"
            continue
        assert _sympy_value(case["sympy"]) == case["value"], (
            f"{case['id']}: SymPy gives {_sympy_value(case['sympy'])}, the fixture holds "
            f"{case['value']} (UPDATE_LIVE_ANSWER_FIXTURE=1 rewrites it)"
        )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "case", [_turn_param(case) for case in _cases() if case["value"] is not None]
)
async def test_the_turn_verifies_the_live_answer(
    case: dict[str, Any], thread_sympy_executor: None
) -> None:
    route = await route_case(Case("live-answer", "math", case["draft"], Expect(), ""))
    if not route.solved:
        # The model answers it: no checked number to differ from the phone's.
        assert not case.get("server_gap"), f"{case['id']}: the turn no longer verifies it"
        return
    verified = _turn_value(route.verified_answer)
    want = _number(case["value"])
    assert verified is not None and abs(verified.imag) < 1e-12 and _close(verified.real, want), (
        f"{case['draft']}: the phone shows {case['value']}, the turn verifies "
        f"{route.verified_answer!r}"
    )
