"""Maths glyphs as ASCII, one table for every reader: operators and scripts.

The solver, the arithmetic gate, the work reader, the tool check, the check of a
reply's own arithmetic and the number scanners each kept a table of their own (eleven
of them): an en dash was a minus to the solver and not to the reply check, and "⋅"
folded in three of them (code-health audit DUP-07). A reader's own rewrites (π, ∞,
roots, vulgar fractions, ≤) stay with it, on top of these.
"""

from __future__ import annotations

# Escapes, not literals: RUF001 flags lookalike punctuation.
OPERATOR_GLYPHS: dict[str, str] = {
    "\u00d7": "*",  # multiplication sign
    "\u22c5": "*",  # dot operator
    "\u00b7": "*",  # middle dot
    "\u2217": "*",  # asterisk operator
    "\u00f7": "/",  # division sign
    "\u2215": "/",  # division slash
    "\u2044": "/",  # fraction slash
    "\u2212": "-",  # minus sign
    "\u2013": "-",  # en dash (phones, OCR)
    "\u2014": "-",  # em dash
}
_OPERATORS = str.maketrans(OPERATOR_GLYPHS)

# A derivative's primes as typed: iOS smart punctuation curls them ("\u2019"), a book sets
# prime, double and triple prime glyphs. Every reader of derivative notation folds these.
_PRIMES = str.maketrans(
    {
        "\u2019": "'",  # right single quotation mark
        "\u2032": "'",  # prime
        "\u2035": "'",  # reversed prime
        "\u2033": "''",  # double prime
        "\u2034": "'''",  # triple prime
    }
)

SUPERSCRIPT_DIGIT_GLYPHS = "⁰¹²³⁴⁵⁶⁷⁸⁹"
SUBSCRIPT_DIGIT_GLYPHS = "₀₁₂₃₄₅₆₇₈₉"
# Superscript digits and the signs an exponent carries ("10⁻⁹"), for number readers.
SUPERSCRIPT_SIGNED = str.maketrans(SUPERSCRIPT_DIGIT_GLYPHS + "⁻⁺", "0123456789-+")
SUBSCRIPT_DIGITS = str.maketrans(SUBSCRIPT_DIGIT_GLYPHS, "0123456789")
# An exponent written raised: "x²", "m⁻¹" (a worked block's units, a graph's labels).
TO_SUPERSCRIPT = str.maketrans("0123456789-", SUPERSCRIPT_DIGIT_GLYPHS + "⁻")

# Every raised and lowered form Unicode has of a digit, a Latin letter, a plus, minus or
# equals sign and a round bracket (its <super> and <sub> forms), as the character it
# raises or lowers. Readers that knew only the digits read "eˣ" as e times a symbol ˣ and
# certified the result (∫ x eˣ dx came back as e·x²·ˣ/2, 2026-11-13). The two ordinal
# indicators are left out: "1ª" and "nº" are ordinals, and "30º" is a degree typed in the
# degree sign's place, never a script. ``docs/fixtures/script_glyphs.json`` holds the
# phone's table (``lib/unicodeSupSub.ts``) to this one.
SUPERSCRIPT_GLYPHS: dict[str, str] = dict(
    zip(
        "⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻⁼⁽⁾ᵃᵇᶜᵈᵉᶠᵍʰⁱʲᵏˡᵐⁿᵒᵖ\U000107a5ʳˢᵗᵘᵛʷˣʸᶻᴬᴮꟲᴰᴱꟳᴳᴴᴵᴶᴷᴸᴹᴺᴼᴾꟴᴿᵀᵁⱽᵂ",
        "0123456789+-=()abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRTUVW",
        strict=True,
    )
)
SUBSCRIPT_GLYPHS: dict[str, str] = dict(
    zip(
        "₀₁₂₃₄₅₆₇₈₉₊₋₌₍₎ₐₑₕᵢⱼₖₗₘₙₒₚᵣₛₜᵤᵥₓ",
        "0123456789+-=()aehijklmnoprstuvx",
        strict=True,
    )
)


def fold_operator_glyphs(text: str) -> str:
    """Every operator glyph a reader meets, as ASCII: times, divide and minus signs."""
    return text.translate(_OPERATORS)


def fold_primes(text: str) -> str:
    """Every prime glyph as ASCII apostrophes: y″ is y''."""
    return text.translate(_PRIMES)
