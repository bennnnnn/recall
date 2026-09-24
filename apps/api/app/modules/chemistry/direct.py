"""Exact scan-friendly replies for complete verified chemistry calculations."""

from __future__ import annotations

from app.modules.chemistry.block import VerifiedChemistry


def format_direct_chemistry_reply(verified: VerifiedChemistry) -> str:
    result = verified.result
    given = "\n".join(f"- {item}" for item in result.given)
    substitution = "\n".join(result.substitution)
    return (
        f"**Given**\n\n{given}\n\n"
        f"**Find**\n\n{result.find}\n\n"
        f"**Formula**\n\n{result.formula} — {result.formula_name}\n\n"
        f"**Substitution**\n\n{substitution}\n\n"
        # Chemistry answers often contain formulas and slash-units (for example
        # ``ΔG = -10 kJ/mol``). The generic math answer fence interprets those
        # letters as algebra and can visibly rearrange a correct result. Keep
        # the exact verified chemistry text and its success mark as Markdown.
        f"**Answer**\n\n**{result.answer}** ✅\n"
    )


def maybe_direct_chemistry_reply(
    verified: VerifiedChemistry | None,
    *,
    has_image_attachment: bool,
) -> str | None:
    """Use exact output only when extraction came from the user's typed text."""
    if verified is None or has_image_attachment:
        return None
    return format_direct_chemistry_reply(verified)
