"""Exact scan-friendly replies for complete verified chemistry calculations."""

from __future__ import annotations

import json

from app.modules.chemistry.block import VerifiedChemistry
from app.services.chat.presentation import present_assistant_markdown


def format_direct_chemistry_reply(verified: VerifiedChemistry) -> str:
    result = verified.result
    given = "\n".join(f"- {item}" for item in result.given)
    substitution = "\n".join(result.substitution)
    # Chemistry answers often contain formulas and slash-units (for example
    # ``ΔG = -10 kJ/mol``). The generic math answer fence interprets those
    # letters as algebra and can visibly rearrange a correct result. Keep
    # the exact verified chemistry text and its success mark as Markdown.
    body = (
        f"**Given**\n\n{given}\n\n"
        f"**Find**\n\n{result.find}\n\n"
        f"**Formula**\n\n{result.formula} — {result.formula_name}\n\n"
        f"**Substitution**\n\n{substitution}\n\n"
        f"**Answer**\n\n**{result.answer}** ✅\n"
    )
    # Present the prose only. Scene and structure fences stay byte-for-byte.
    presented = present_assistant_markdown(body)
    extras: list[str] = []
    if result.scene is not None:
        payload = json.dumps(result.scene, ensure_ascii=False)
        extras.append(f"```chem_scene\n{payload}\n```")
    if result.structure_smiles:
        extras.append(f"```smiles\n{result.structure_smiles}\n```")
    if not extras:
        return presented
    return presented + "\n" + "\n".join(extras) + "\n"


def maybe_direct_chemistry_reply(
    verified: VerifiedChemistry | None,
    *,
    has_image_attachment: bool,
) -> str | None:
    """Use exact output only when extraction came from the user's typed text."""
    if verified is None or has_image_attachment:
        return None
    return format_direct_chemistry_reply(verified)
