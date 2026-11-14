"""Unicode superscripts and subscripts read as the scripts they write, for every reader.

"Integrate eˣ cos(2x)", "∫ x eˣ dx", "2ˣ⁺¹" and "∫₀¹ eˣ dx" are maths typed with a
phone's raised letters. The readers knew only the raised digits, so ˣ stayed a character
of its own, SymPy made it a symbol, and the turn was certified: ∫ eˣ cos(2x) dx came
back as ˣ·e·sin(2x)/2 and the derivative of 2ˣ as 0 (grade 12 textbook round,
2026-11-13). One reading of a run, for the maths and physics readers and the parser:

- Raised digits are the power they write, wherever they sit: ``x²`` is ``x^2``, ``s⁻²``
  ``s^-2``, ``10¹²`` ``10^12``, ``x²⁺¹`` ``x^(2+1)``.
- A run with a letter is a power only on a maths atom (a Latin letter, a digit, a closing
  bracket or π): ``eˣ``, ``e⁻ˣ``, ``e²ˣ``, ``xⁿ⁻¹``, ``2ˣ⁺¹``, ``(x+1)ⁿ``. Glued to a
  Latin letter after it, the power is bracketed so it ends where the raised letters do
  (``eˣsin x`` is ``e^(x)sin x``, never ``e^xsin``). Raised letters on a number are its
  ordinal ("the 21ˢᵗ century", "le 1ᵉʳ mai"); before a letter English does not write
  they are a sound's (IPA's "pʰæn"), and after a space there is nothing to raise. Those stay as
  written, and the parser refuses a modifier letter it is handed, so no reading
  certifies them.
- A sign that ends a run is a charge, not part of the power: ``Fe³⁺`` keeps its ⁺.
- A lowered run straight after a big operator is its lower limit: ``∫₀¹`` is ``∫_0^1``.
"""

from __future__ import annotations

from app.services.glyphs import SUBSCRIPT_GLYPHS, SUPERSCRIPT_GLYPHS

# A power's last character is never an operator or an opening bracket: those end a charge
# ("Fe³⁺", "SO₄²⁻") or begin nothing.
_DANGLING = "+-=("
# What a raised letter may stand on besides a Latin letter or a digit.
_CLOSED_ATOMS = frozenset(")]}π")
# Signs that open a number: ``s⁻²`` is ``s^-2``, a bound ``₋₁`` is ``-1``.
_SIGNS = "+-"
# Operators whose lowered script is a limit: ``∫₀¹``, ``∑ₖ₌₁¹⁰``.
_BIG_OPERATORS = frozenset("∫∬∭∮∑∏")


def _balanced(text: str) -> bool:
    depth = 0
    for char in text:
        depth += {"(": 1, ")": -1}.get(char, 0)
        if depth < 0:
            return False
    return depth == 0


def _wrapped(text: str) -> bool:
    """``(x+1)`` is one bracket round the whole; ``(x)(y)`` is two."""
    return len(text) > 1 and text[0] == "(" and text[-1] == ")" and _balanced(text[1:-1])


def _signed_digits(text: str) -> bool:
    digits = text[1:] if text[:1] in _SIGNS else text
    return digits.isdigit()


def _maths_atom(char: str) -> bool:
    return (char.isascii() and char.isalnum()) or char in _CLOSED_ATOMS


def _raised(body: str, before: str, after: str) -> str | None:
    """What a raised run writes as a power, or None when it raises nothing.

    ``before`` and ``after`` are the characters around the run.
    """
    if "=" in body or not _balanced(body) or not any(char.isalnum() for char in body):
        return None
    if not any(char.isalpha() for char in body):
        return body
    if not _maths_atom(before) or (after.isalpha() and not after.isascii()):
        return None
    if before.isdigit() and body.isalpha() and len(body) > 1:
        return None
    return body


def _written(script: str, mark: str, *, group_numbers: bool, glued: bool) -> str:
    """``x`` → ``^x``, ``-2`` → ``^-2``, ``n-1`` → ``^(n-1)``, ``x`` before ``sin`` → ``^(x)``.

    Plain readers keep a number bare (``^23``, ``^-2``), as they always read it; the parser
    groups it (``**(23)``) so ``**`` binds the whole number.
    """
    numeric = _signed_digits(script)
    if (len(script) == 1 and not (glued and not numeric)) or (numeric and not group_numbers):
        return f"{mark}{script}"
    inner = script[1:-1] if _wrapped(script) else script
    return f"{mark}({inner})"


def fold_superscript_runs(text: str, *, mark: str = "^", group_numbers: bool = False) -> str:
    """Every raised run that writes a power, as ``mark`` and the power: ``eˣ`` → ``e^x``."""
    if not any(char in SUPERSCRIPT_GLYPHS for char in text):
        return text
    out: list[str] = []
    index = 0
    while index < len(text):
        if text[index] not in SUPERSCRIPT_GLYPHS:
            out.append(text[index])
            index += 1
            continue
        end = index
        while end < len(text) and text[end] in SUPERSCRIPT_GLYPHS:
            end += 1
        run = "".join(SUPERSCRIPT_GLYPHS[char] for char in text[index:end])
        core = run.rstrip(_DANGLING)
        before = text[index - 1] if index else ""
        after = text[end] if end < len(text) else ""
        power = _raised(core, before, after) if core else None
        if power is None:
            out.append(text[index:end])
        else:
            glued = after.isascii() and after.isalpha()
            out.append(_written(power, mark, group_numbers=group_numbers, glued=glued))
            out.append(text[index + len(core) : end])
        index = end
    return "".join(out)


def _lowered_runs(text: str, *, after_operator_only: bool) -> str:
    out: list[str] = []
    index = 0
    while index < len(text):
        if text[index] not in SUBSCRIPT_GLYPHS:
            out.append(text[index])
            index += 1
            continue
        end = index
        while end < len(text) and text[end] in SUBSCRIPT_GLYPHS:
            end += 1
        run = "".join(SUBSCRIPT_GLYPHS[char] for char in text[index:end])
        before = text[index - 1] if index else ""
        out.append(
            _lowered(run, before, after_operator_only=after_operator_only) or text[index:end]
        )
        index = end
    return "".join(out)


def _lowered(run: str, before: str, *, after_operator_only: bool) -> str | None:
    if before in _BIG_OPERATORS:
        if not _balanced(run) or not any(char.isalnum() for char in run):
            return None
        return f"_{run}" if len(run) == 1 or _signed_digits(run) else f"_{{{run}}}"
    if after_operator_only:
        return None
    # A subscript names a quantity (``x₁``, ``aₙ``, ``H₂O``), its digits wherever they sit,
    # as the parser always read them. One with a sign in it (``aₙ₊₁``) is left whole, never
    # read as a name with a sum after it.
    if run.isdigit() or (run.isalnum() and _maths_atom(before)):
        return f"_{run}"
    return None


def fold_operator_subscripts(text: str) -> str:
    """A lowered run on a big operator, as its limit: ``∫₀¹ eˣ dx`` → ``∫_0¹ eˣ dx``."""
    if not any(char in SUBSCRIPT_GLYPHS for char in text):
        return text
    return _lowered_runs(text, after_operator_only=True)


def fold_subscript_runs(text: str) -> str:
    """Lowered names and limits: ``x₁`` → ``x_1``, ``aₙ`` → ``a_n``, ``∫₋₁`` → ``∫_-1``."""
    if not any(char in SUBSCRIPT_GLYPHS for char in text):
        return text
    return _lowered_runs(text, after_operator_only=False)
