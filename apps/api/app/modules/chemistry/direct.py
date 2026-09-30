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
) -> str | None:
    """Use exact output only when extraction came from the user's typed text."""
    if verified is None or has_image_attachment:
        return None
    return format_direct_chemistry_reply(verified)
