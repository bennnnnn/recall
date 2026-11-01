"""Chemistry as the subject registry asks it (``services/subjects/registry``).

The adapter calls what chemistry already has: the reading of a line through ``reading``, the
verified block through ``context`` (with its fence hint from ``reply_policy``) and the direct
reply through ``direct``, each imported when it runs.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from app.services.solving import SubjectAugmentation

if TYPE_CHECKING:
    from app.core.config import Settings
    from app.services.solving import VerifiedSolveBlock
    from app.services.subjects.registry import SubjectRequest


@dataclass(frozen=True)
class ChemistrySubject:
    name: Literal["chemistry"] = "chemistry"

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
