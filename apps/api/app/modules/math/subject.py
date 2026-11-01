"""Maths as the subject registry asks it (``services/subjects/registry``).

The adapter calls what maths already has: the verified block through ``tools.prompt``, the
direct reply through ``tools.direct``, and its prompt copy from ``reply_policy`` and
``followup``.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Literal

from app.modules.math.followup import (
    MATH_FOLLOWUP_HINT,
    answer_claim_problem,
    is_math_followup,
    math_working_followup_problem,
    offered_equation_problem,
    pronoun_math_problem,
    readable_standalone_answer,
    restated_math_problem,
)
from app.modules.math.reply_policy import MATH_REPLY_POLICY, math_prompt_hints
from app.modules.math.tools.prompt import (
    NOTHING_TO_GRAPH,
    build_math_augmentation,
    needs_symbolic_math,
)
from app.services.solving import SubjectAugmentation, VerifiedMathBlock
from app.services.subject_hints import SubjectHints

if TYPE_CHECKING:
    from app.core.config import Settings
    from app.services.solving import VerifiedSolveBlock
    from app.services.subjects.registry import SubjectRequest


_HINTS = SubjectHints(
    math_prompt_hints,
    (MATH_REPLY_POLICY,),
    shared_math_ink=False,
    followup=(MATH_REPLY_POLICY, MATH_FOLLOWUP_HINT),
)


@dataclass(frozen=True)
class MathFollowups:
    def problem(
        self,
        query: str | None,
        recent: Sequence[Any],
        *,
        blocked: Callable[[str], bool] | None = None,
    ) -> str | None:
        # Its verified working first. "Do it" after the assistant wrote a new equation is
        # not a request to re-solve the user's earlier line: the offered equation is solved
        # instead. "check my answer: x = 6" is checked against the open problem, and
        # "simplify it" works on the user's last expression. Alone, each one used to be
        # solved as typed: ``x = 6`` verified itself and "it" was ``i t``.
        found = math_working_followup_problem(query, recent, blocked=blocked)
        if found is None:
            found = offered_equation_problem(query, recent)
        if found is None:
            found = (
                answer_claim_problem(query, recent, blocked=blocked)
                or pronoun_math_problem(query, recent, blocked=blocked)
                or restated_math_problem(query, recent, blocked=blocked)
            )
        return found

    def continues(
        self,
        query: str | None,
        recent: Sequence[Any],
        *,
        blocked: Callable[[str], bool] | None = None,
    ) -> bool:
        return is_math_followup(query, recent, blocked=blocked)

    def previous_result(self, reply: str) -> str | None:
        return readable_standalone_answer(reply)

    def asks_to_see(self, line: str, recent: Sequence[Any] | None = None) -> bool:
        return False

    def shown_problem(self, line: str, recent: Sequence[Any]) -> str | None:
        return None


@dataclass(frozen=True)
class MathSubject:
    name: Literal["math"] = "math"
    hints: SubjectHints = _HINTS
    followups: MathFollowups = MathFollowups()

    def asks(self, text: str, *, has_image_attachment: bool = False) -> bool:
        return needs_symbolic_math(text, has_image_attachment=has_image_attachment)

    async def solve(self, request: SubjectRequest, settings: Settings) -> SubjectAugmentation:
        block, math_verified = await build_math_augmentation(
            request.math_text,
            settings,
            has_image_attachment=request.has_image_attachment,
            image_math_extract=request.image_math_extract,
            needs_math=True,
            prior_user_messages=request.prior_user_messages,
            response_intent_text=request.response_intent_text,
        )
        return SubjectAugmentation(
            subject="math",
            prompt_block=block,
            verified=math_verified,
            # Asking which function to graph is not an unverified answer.
            unverified=(
                block is not None and math_verified is None and block is not NOTHING_TO_GRAPH
            ),
        )

    def direct_reply(
        self,
        verified: VerifiedSolveBlock,
        user_text: str,
        *,
        has_image_attachment: bool,
        verified_request_text: str | None,
    ) -> str | None:
        if not isinstance(verified, VerifiedMathBlock):
            return None
        from app.modules.math.tools.direct import maybe_direct_math_reply

        return maybe_direct_math_reply(
            verified,
            user_text,
            has_image_attachment=has_image_attachment,
            verified_request_text=verified_request_text,
        )


MATH_SUBJECT = MathSubject()
