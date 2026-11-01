"""Physics as the subject registry asks it (``services/subjects/registry``).

The adapter calls what physics already has: the verified block through ``prompt`` and the
direct reply through ``direct``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from app.modules.physics.prompt import build_physics_augmentation
from app.services.solving import SubjectAugmentation, VerifiedPhysicsBlock

if TYPE_CHECKING:
    from app.core.config import Settings
    from app.services.solving import VerifiedSolveBlock
    from app.services.subjects.registry import SubjectRequest


def _physics_request_text(user_content: str) -> str:
    """The problem a physics turn verifies.

    A scanned photo's caption is a protocol line. When the student confirmed
    what the scanner read, that reading is the problem; without one, the
    caption alone gets the unverified physics note.
    """
    from app.services.subject_scan import confirmed_scan_reading, scanner_camera_subject

    if scanner_camera_subject(user_content) != "physics":
        return user_content
    return confirmed_scan_reading(user_content) or user_content


@dataclass(frozen=True)
class PhysicsSubject:
    name: Literal["physics"] = "physics"

    async def solve(self, request: SubjectRequest, settings: Settings) -> SubjectAugmentation:
        block, physics_verified, solve_failed = await build_physics_augmentation(
            _physics_request_text(request.text),
            settings,
            needs_subject=True,
        )
        return SubjectAugmentation(
            subject="physics",
            prompt_block=block,
            verified=physics_verified,
            # No matching template is not a failed check. The prompt note still
            # tells the model not to claim a check. The reply does not say it
            # could not be verified.
            unverified=solve_failed,
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
        if not isinstance(verified, VerifiedPhysicsBlock):
            return None
        from app.modules.physics.direct import maybe_direct_physics_reply

        return maybe_direct_physics_reply(
            verified,
            user_text,
            has_image_attachment=has_image_attachment,
        )


PHYSICS_SUBJECT = PhysicsSubject()
