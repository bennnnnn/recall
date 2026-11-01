"""A turn's decisions have one owner each; other code reads them (structure ticket ST-05).

Small talk is decided once per turn, in its place, by ``turn_prep.mode.classify_turn_mode``
(``_TurnMode.lightweight`` and its reason, carried as ``ctx.lightweight_turn``): a short
reply to an offer or a clarify card is an answer, not a greeting. Calling the reader on
the turn's message again elsewhere decides it a second time, without that place. The
other callers below read some other text, or compose the reader into a reader of their
own; each function is listed with how many times it calls and why, and the list only
shrinks.
"""

from __future__ import annotations

import ast
from collections import Counter

from .boundary_support import APP_ROOT

# "path::function" -> (calls, why).
_LIGHTWEIGHT_CALLERS: dict[str, tuple[int, str]] = {
    # The owner: the turn's small-talk decision, read alone and then in its place.
    "modules/chat/turn_prep/mode.py::_light_reason": (2, "owner"),
    # Precedence questions (docs/STRUCTURE_TICKETS.md, ST-05): these ask about the turn's
    # own message without its place, so "no" after an offer reads as small talk here and
    # as an answer to the turn's mode. Choosing is a behaviour change of its own.
    "modules/chat/model_routing/route.py::_looks_like_smart_continuation": (
        1,
        "routing runs in the pool, before the window",
    ),
    "modules/chat/answer_photo_offer.py::offers_answer_photo": (1, "the bare query"),
    # Readers of other text, or readers built from this reader.
    "modules/chat/continuation_subject.py::is_pure_continuation": (1, "any line"),
    "modules/chat/follow_up_thread.py::_continues_thread": (1, "any line"),
    "modules/chat/prompt_constants/writing.py::is_bare_writing_line": (1, "a pasted fragment"),
    "modules/chat/related_questions.py::general_question": (1, "a suggested question"),
    "modules/chat/related_questions.py::_asks": (1, "a suggested question"),
    "modules/math/followup.py::open_math_problem": (1, "a fragment against its equation"),
    "modules/speech/live_talk_tools.py::execute_tool": (1, "live talk's spoken query"),
    "modules/turn_reading/personal.py::needs_rich_context": (1, "a reader built on it"),
    "modules/turn_reading/writing.py::_answers_draft_question": (1, "a reader built on it"),
    "modules/web_search/detection.py::web_search_skip": (1, "a reader with its own offer check"),
}


def callers(name: str, tree: ast.AST, path: str) -> Counter[str]:
    """Each call of ``name`` (bare or ``module.name``), counted by its enclosing function."""
    found: Counter[str] = Counter()

    def visit(node: ast.AST, scope: str) -> None:
        for child in ast.iter_child_nodes(node):
            inner = scope
            if isinstance(child, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
                inner = f"{scope}.{child.name}" if scope else child.name
            if isinstance(child, ast.Call):
                func = child.func
                named = func.id if isinstance(func, ast.Name) else None
                if isinstance(func, ast.Attribute):
                    named = func.attr
                if named == name:
                    found[f"{path}::{scope or '<module>'}"] += 1
            visit(child, inner)

    visit(tree, "")
    return found


def _production_callers(name: str) -> Counter[str]:
    found: Counter[str] = Counter()
    for path in sorted(APP_ROOT.rglob("*.py")):
        relative = path.relative_to(APP_ROOT).as_posix()
        if not relative.startswith("tests/"):
            found += callers(name, ast.parse(path.read_text(encoding="utf-8")), relative)
    return found


def test_callers_sees_bare_and_module_qualified_calls_by_function() -> None:
    tree = ast.parse(
        "from x import routing, is_lightweight_chat_turn\n"
        "def a(t):\n    return is_lightweight_chat_turn(t)\n"
        "class B:\n    def c(self, t):\n        return routing.is_lightweight_chat_turn(t)\n"
        "def d(t):\n    return is_lightweight_chat_turn(t) or is_lightweight_chat_turn(t + 'x')\n"
    )
    assert callers("is_lightweight_chat_turn", tree, "f.py") == {
        "f.py::a": 1,
        "f.py::B.c": 1,
        "f.py::d": 2,
    }


def test_small_talk_is_decided_once_per_turn() -> None:
    found = _production_callers("is_lightweight_chat_turn")
    recorded = {caller: calls for caller, (calls, _why) in _LIGHTWEIGHT_CALLERS.items()}
    more = sorted(
        f"{caller}: {calls}" for caller, calls in found.items() if calls > recorded.get(caller, 0)
    )
    assert not more, (
        f"{more} decide small talk again: read the turn's mode (ctx.lightweight_turn), "
        "or, for another text, list the function here with why"
    )
    fewer = sorted(caller for caller, calls in recorded.items() if found.get(caller, 0) < calls)
    assert not fewer, f"{fewer} call it less now: lower or remove them in the list"
