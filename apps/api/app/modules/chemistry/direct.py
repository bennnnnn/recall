"""Exact scan-friendly replies for complete verified chemistry calculations."""

from __future__ import annotations

from app.modules.chemistry.block import VerifiedChemistry
from app.modules.chemistry.fence import assemble_chemistry_reply
from app.modules.chemistry.notation import typeset


def format_direct_chemistry_reply(verified: VerifiedChemistry) -> str:
    result = verified.result
    # The solver text is ASCII (H2SO4, Fe2+, ->); the reader gets H₂SO₄, Fe²⁺, →. A result
    # that carries SMILES or atom labels is left exactly as the solver wrote it.
    show = (lambda text: text) if result.verbatim else typeset
    given = "\n".join(f"- {show(item)}" for item in result.given)
    substitution = "\n".join(show(line) for line in result.substitution)
    # The body is laid out here, so the shared calculation layout is not run over it: it
    # would wrap any row with two "=" in LaTeX math, and a row like "n = 10 / 2.02 = 4.95 mol"
    # is chemistry text, not a formula the client can typeset.
    body = (
        f"**Given**\n\n{given}\n\n"
        f"**Find**\n\n{show(result.find)}\n\n"
        f"**Formula**\n\n{show(result.formula)} — {result.formula_name}\n\n"
        f"**Substitution**\n\n{substitution}\n\n"
        f"**Answer**"
    )
    return assemble_chemistry_reply(body, verified)


def maybe_direct_chemistry_reply(
    verified: VerifiedChemistry | None,
    *,
    has_image_attachment: bool,
    user_text: str = "",
) -> str | None:
    """Use exact output for typed text, and for a photo whose reading was confirmed."""
    if verified is None:
        return None
    if has_image_attachment:
        from app.modules.chemistry.reading import confirmed_chemistry_reading

        if confirmed_chemistry_reading(user_text) is None:
            return None
    return format_direct_chemistry_reply(verified)
