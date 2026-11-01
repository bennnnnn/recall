"""A turn's decisions have one owner each; other code reads them (structure ticket ST-05).

Small talk is decided once per turn, in its place, by ``turn_prep.mode.classify_turn_mode``
(``_TurnMode.lightweight`` and its reason, carried as ``ctx.lightweight_turn``): a short
reply to an offer or a clarify card is an answer, not a greeting. Calling the reader on
the turn's message again elsewhere decides it a second time, without that place. The
other callers below read some other text, or compose the reader into a reader of their
own; each is listed with why, and the list only shrinks.
"""

from __future__ import annotations

import ast

from .boundary_support import APP_ROOT

_LIGHTWEIGHT_CALLERS: dict[str, str] = {
    # The owner: the turn's small-talk decision, read against the window.
    "modules/chat/turn_prep/mode.py": "owner",
    # Precedence questions (docs/STRUCTURE_TICKETS.md, ST-05): these ask about the turn's
    # own message without its place, so "no" after an offer reads as small talk here and
    # as an answer to the turn's mode. Choosing is a behaviour change of its own.
    "modules/chat/model_routing/route.py": "routing runs in the pool, before the window",
    "modules/chat/answer_photo_offer.py": "the photo offer reads the bare query",
    # Readers of other text, or readers built from this reader.
    "modules/chat/continuation_subject.py": "any line: is it only 'continue'",
    "modules/chat/follow_up_thread.py": "any line: does it continue the thread",
    "modules/chat/prompt_constants/writing.py": "any line: a pasted fragment",
    "modules/chat/related_questions.py": "the suggested follow-up questions",
    "modules/math/followup.py": "a fragment against earlier lines",
    "modules/speech/live_talk_tools.py": "live talk's spoken search query",
    "modules/turn_reading/personal.py": "a reader built on it",
    "modules/turn_reading/writing.py": "a reader built on it",
    "modules/web_search/detection.py": "a reader built on it, with its own offer check",
}


def _callers(name: str) -> set[str]:
    found: set[str] = set()
    for path in sorted(APP_ROOT.rglob("*.py")):
        relative = path.relative_to(APP_ROOT).as_posix()
        if relative.startswith("tests/"):
            continue
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Call) and getattr(node.func, "id", None) == name:
                found.add(relative)
    return found


def test_small_talk_is_decided_once_per_turn() -> None:
    callers = _callers("is_lightweight_chat_turn")
    new = sorted(callers - set(_LIGHTWEIGHT_CALLERS))
    assert not new, (
        f"{new} decide small talk again: read the turn's mode (ctx.lightweight_turn), "
        "or, for another text, list the file here with why"
    )
    gone = sorted(set(_LIGHTWEIGHT_CALLERS) - callers)
    assert not gone, f"{gone} no longer call it: remove them from the list"
