"""Chemistry prompt hints: how a chemistry answer is presented."""

CHEMISTRY_PRESENTATION_HINT = (
    "This is a chemistry answer. Keep species, amounts, and units easy to scan. "
    "Write species with Unicode sub- and superscripts (H₂O, Fe³⁺, SO₄²⁻), reactions with → "
    "or ⇌, and never put a bare species or unit in LaTeX. "
    "When you calculate, follow the calculation layout: one reasoning state per row."
)


def chemistry_prompt_hints(short: bool) -> tuple[str, ...]:
    """The chemistry pack. Short style and a compact turn get the same one."""
    return (CHEMISTRY_PRESENTATION_HINT,)
