"""Exact scan-friendly replies for complete verified chemistry calculations."""

from __future__ import annotations

from app.modules.chemistry.block import VerifiedChemistry
from app.modules.chemistry.fence import assemble_chemistry_reply
from app.services.chat.presentation import present_assistant_markdown


def format_direct_chemistry_reply(verified: VerifiedChemistry) -> str:
    result = verified.result
    given = "\n".join(f"- {item}" for item in result.given)
    substitution = "\n".join(result.substitution)
    # The answer, scene, and structure are solver fences appended after
    # presentation. Calculation layout must not rewrite those bodies.
    body = (
        f"**Given**\n\n{given}\n\n"
        f"**Find**\n\n{result.find}\n\n"
        f"**Formula**\n\n{result.formula} — {result.formula_name}\n\n"
        f"**Substitution**\n\n{substitution}\n\n"
        f"**Answer**"
    )
    return assemble_chemistry_reply(present_assistant_markdown(body), verified)


def maybe_direct_chemistry_reply(
    verified: VerifiedChemistry | None,
    *,
    has_image_attachment: bool,
) -> str | None:
    """Use exact output only when extraction came from the user's typed text."""
    if verified is None or has_image_attachment:
        return None
    return format_direct_chemistry_reply(verified)
