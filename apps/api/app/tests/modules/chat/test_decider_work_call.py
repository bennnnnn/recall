"""The Decider's work question is a call of its own beside the turn's (``decider_read``).

Asked among the turn's questions it moved their measured answers (the think corpus's recall
from 96% to 92%), so it goes in a second call begun with the first, and the turn's read never
waits on it longer than a moment.
"""

from __future__ import annotations

from typing import Any

import pytest

from app.modules.chat import decider_read
from app.tests.fakes import isolated_settings


def _decider_answers(**work: Any) -> dict[str, Any]:
    return {
        "subject": {"type": "choice", "choice": "maths"},
        "think": {"type": "noul", "noul": 0.1},
        "hard": {"type": "noul", "noul": 0.1},
        "picture": {"type": "choice", "choice": "none"},
        "follow": {"type": "choice", "choice": "none"},
        "live": {"type": "noul", "noul": 0.0},
        "asked": {"type": "noul", "noul": 0.0},
        **work,
    }


@pytest.mark.parametrize(("work_fails", "work"), [(False, False), (True, None)])
@pytest.mark.asyncio
async def test_the_work_question_is_its_own_call_and_never_costs_the_read(
    monkeypatch: pytest.MonkeyPatch, work_fails: bool, work: bool | None
) -> None:
    """Asked among the turn's questions it moved their measured answers, so it is a call of
    its own; when that call fails the turn's read stands and the rules lay the turn out."""
    from app.gateways import decider_gateway
    from app.gateways.decider_gateway import DeciderReply

    asked: list[set[str]] = []

    async def fake_decide(_settings: Any, *, questions: dict[str, Any], **_: Any) -> DeciderReply:
        asked.append(set(questions))
        if "work" in questions:
            if work_fails:
                raise RuntimeError("refused")
            return DeciderReply.model_validate({"answers": {"work": {"type": "noul", "noul": 0.1}}})
        return DeciderReply.model_validate({"answers": _decider_answers()})

    monkeypatch.setattr(decider_gateway, "decide", fake_decide)
    fields = await decider_read.decide_turn(
        isolated_settings(), "Translate 7x into words", has_earlier=False, seconds=1.0
    )
    assert fields is not None and fields["subject"] == "maths"
    assert fields["work"] is work
    assert {"work"} in asked and set(decider_read.QUESTIONS) in asked
    assert "work" not in decider_read.QUESTIONS
