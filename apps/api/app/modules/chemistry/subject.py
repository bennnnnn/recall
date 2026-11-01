"""Chemistry as the subject registry asks it (``services/subjects/registry``).

The adapter calls what chemistry already has: the reading of a line through ``reading``, the
verified block through ``context`` (with its fence hint from ``reply_policy``) and the direct
reply through ``direct``, each imported when it runs; and its prompt copy from
``reply_policy`` and ``followup``.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Literal

from app.modules.chemistry.followup import CHEMISTRY_FOLLOWUP_HINT, chemistry_followup_problem
from app.modules.chemistry.reply_policy import (
    CHEMISTRY_FENCE_HINT,
    CHEMISTRY_PRESENTATION_HINT,
    chemistry_prompt_hints,
)
from app.modules.chemistry.request import is_chemistry_question
from app.modules.chemistry.shape_followup import (
    could_ask_a_shape,
    is_show_line,
    last_question_line,
    shape_followup_problem,
)
from app.services.solving import SubjectAugmentation
from app.services.subject_hints import SubjectHints

if TYPE_CHECKING:
    from app.core.config import Settings
    from app.services.solving import VerifiedSolveBlock
    from app.services.subjects.registry import SubjectRequest


_HINTS = SubjectHints(
    chemistry_prompt_hints,
    followup=(CHEMISTRY_FOLLOWUP_HINT,),
    beside_visuals=(CHEMISTRY_PRESENTATION_HINT, CHEMISTRY_FENCE_HINT),
)


@dataclass(frozen=True)
class ChemistryFollowups:
    def problem(
        self,
        query: str | None,
        recent: Sequence[Any],
        *,
        blocked: Callable[[str], bool] | None = None,
    ) -> str | None:
        return chemistry_followup_problem(query, recent)

    def continues(
        self,
        query: str | None,
        recent: Sequence[Any],
        *,
        blocked: Callable[[str], bool] | None = None,
    ) -> bool:
        return chemistry_followup_problem(query, recent) is not None

    def previous_result(self, reply: str) -> str | None:
        return None

    def asks_to_see(self, line: str, recent: Sequence[Any] | None = None) -> bool:
        # "can u show me both" right after a shape answer asks for its molecules.
        if not is_show_line(line):
            return False
        return recent is None or could_ask_a_shape(last_question_line(recent))

    def shown_problem(self, line: str, recent: Sequence[Any]) -> str | None:
        return shape_followup_problem(line, recent)


@dataclass(frozen=True)
class ChemistrySubject:
    name: Literal["chemistry"] = "chemistry"
    hints: SubjectHints = _HINTS
    followups: ChemistryFollowups = ChemistryFollowups()

    def asks(self, text: str, *, has_image_attachment: bool = False) -> bool:
        return is_chemistry_question(text)

    async def solve(self, request: SubjectRequest, settings: Settings) -> SubjectAugmentation:
        if not settings.chemistry_enabled:
            return SubjectAugmentation(None, None, None)
        from app.modules.chemistry.context import build_chemistry_augmentation
        from app.modules.chemistry.reading import chemistry_text_for_solve
        from app.modules.chemistry.reply_policy import attach_chemistry_fence_hint

        block, verified, declined = await build_chemistry_augmentation(
            chemistry_text_for_solve(request.text), settings, redis=request.redis
        )
        if block:
            block = attach_chemistry_fence_hint(block)
        return SubjectAugmentation(
            subject="chemistry" if block or verified else None,
            prompt_block=block,
            verified=verified,
            unverified=declined,
        )

    def direct_reply(
        self,
        verified: VerifiedSolveBlock,
        user_text: str,
        *,
        has_image_attachment: bool,
        verified_request_text: str | None,
    ) -> str | None:
        del verified_request_text
        from app.modules.chemistry.block import VerifiedChemistry
        from app.modules.chemistry.direct import maybe_direct_chemistry_reply

        if not isinstance(verified, VerifiedChemistry):
            return None
        return maybe_direct_chemistry_reply(
            verified,
            has_image_attachment=has_image_attachment,
            user_text=user_text,
        )


CHEMISTRY_SUBJECT = ChemistrySubject()
