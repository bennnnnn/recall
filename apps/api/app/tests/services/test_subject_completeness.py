"""Every registered subject has what chat asks of it, and chat's subject lists are the registry's.

A subject plugs in through its adapter (``services/subjects/registry``): its name in
``SubjectName``, its entry in ``SUBJECTS`` and its step in the subject order. Chat then asks
the adapter for its switch, its status line, its prompt hints and which replies its fence
finishes. A subject missing any of them, or a list of subjects kept by hand that leaves one
out, fails here rather than in a turn that is read and never solved (physics review
2026-11-12, §3.1).
"""

from __future__ import annotations

from typing import get_args

import pytest

from app.core.config import Settings
from app.services.solving import SubjectName, VerifiedSolveBlock
from app.services.subjects.registry import (
    FENCE_FALLBACK,
    SUBJECTS,
    SubjectAdapter,
    fence_owner,
    subject_adapter,
)

NAMES: tuple[str, ...] = get_args(SubjectName)


def _blocks_of(name: str) -> list[VerifiedSolveBlock]:
    """A verified block a subject's solve could hand the turn: the shared transport naming
    it, and each block class whose subject defaults to it."""

    def subclasses(cls: type[VerifiedSolveBlock]) -> list[type[VerifiedSolveBlock]]:
        return [sub for child in cls.__subclasses__() for sub in (child, *subclasses(child))]

    blocks = [VerifiedSolveBlock(text="block", subject=name)]  # type: ignore[arg-type]
    for cls in subclasses(VerifiedSolveBlock):
        default = cls.__dataclass_fields__["subject"].default
        if default == name:
            try:
                blocks.append(cls(text="block", subject=default))
            except TypeError:
                continue  # a block whose own fields are required (chemistry's result)
    return blocks


def test_the_registry_and_subject_name_agree() -> None:
    names = [adapter.name for adapter in SUBJECTS]
    assert sorted(names) == sorted(NAMES)
    assert len(set(names)) == len(names)
    assert FENCE_FALLBACK in NAMES


@pytest.mark.parametrize("adapter", SUBJECTS, ids=lambda adapter: adapter.name)
def test_every_subject_has_what_chat_asks_of_it(adapter: SubjectAdapter) -> None:
    from app.modules.chat.finalize_contracts import CARD_PASSES, fences_pass
    from app.modules.chat.finalize_passes import FINALIZE_PASSES
    from app.modules.chat.prompt_sections import CONTEXT_SECTIONS
    from app.modules.chat.prompt_subjects import SUBJECT_HINTS
    from app.modules.chat.stream_status import STREAM_STATUS_PHASES

    name = adapter.name
    # A switch, read from settings.
    assert isinstance(adapter.enabled(Settings()), bool)
    # A status line the phone has a label for.
    assert adapter.status_phase in STREAM_STATUS_PHASES
    # Prompt hints, stated by chat, and a follow-up section that states its follow-up copy.
    assert SUBJECT_HINTS[name] is adapter.hints
    for short in (False, True):
        assert all(isinstance(hint, str) and hint for hint in adapter.hints.presentation(short))
    assert f"{name}_followup" in {section.name for section in CONTEXT_SECTIONS}
    # A finalize pass that checks its fences, and its own verified blocks to finish.
    assert fences_pass(name) in {finalize_pass.name for finalize_pass in FINALIZE_PASSES}
    assert fences_pass(name) in CARD_PASSES
    assert any(fence_owner(block) is adapter for block in _blocks_of(name)), name
    # Never another subject's block: the one owner of a reply is the subject that verified it.
    for other in NAMES:
        if other != name:
            assert not any(adapter.fence.owns(block) for block in _blocks_of(other)), other


def test_a_reply_no_subject_verified_is_finished_by_the_fallback() -> None:
    assert fence_owner(None) is subject_adapter(FENCE_FALLBACK)


def test_the_subject_lists_chat_keeps_are_the_registrys() -> None:
    from app.models.routing_lanes import ROUTING
    from app.modules.chat import turn_decision
    from app.modules.chat.answer_photo_offer import NO_PHOTO_SUBJECTS
    from app.modules.chat.decider_read import QUESTIONS, READ_SUBJECTS
    from app.modules.chat.worked_turn import _STEM_SUBJECTS

    # The read names every registered subject, in its own words (its measured prompt), and
    # Auto has a lane for each.
    assert sorted(READ_SUBJECTS.values()) == sorted(NAMES)
    assert set(READ_SUBJECTS) <= set(QUESTIONS["subject"]["criteria"])
    assert set(READ_SUBJECTS) <= set(get_args(turn_decision.Subject))
    assert set(READ_SUBJECTS) <= set(ROUTING.decided)
    # A registered subject's turn is a calculation's, and never one photo to look at.
    assert set(NAMES) <= _STEM_SUBJECTS
    assert set(NAMES) <= NO_PHOTO_SUBJECTS
