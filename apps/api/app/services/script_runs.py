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
  ordinal ("le 1ᵉʳ mai"); before a letter English does not write they are a sound's (IPA's
  "pʰæn"), and after a space there is nothing to raise. Those stay as written, and the
  parser refuses a raised or lowered character it is handed, so no reading certifies them.
- A sign that ends a run is a charge, not part of the power: ``Fe³⁺`` keeps its ⁺.
- An English ordinal's raised suffix is the ordinal typed plain: ``2ⁿᵈ`` is ``2nd``, ``nᵗʰ``
  ``nth``, "the 21ˢᵗ century" "the 21st century". Read as a power, "the nᵗʰ derivative"
  was n^(th) and "the 2ⁿᵈ derivative" no order at all: a checked first derivative
  (2026-11-14).
- Raised digits before a root sign are its index: ``2 ³√27`` and ``2³√27`` are ``2 ∛27``,
  never 2³·√27 (24√3 for 6), as ``³√`` is how a phone types a cube root. A square root
  writes no index, so on a letter or a number a raised 2 stays its power (``x²√x``), and
  so does a longer run (``x²³√x``).
- Raised digits straight after a caret's number or letter go on with its power, as a
  tower groups to the right: ``e^x²`` is e^(x²), ``2^3²`` 2⁹. Any other run there raises
  nothing: ``e^(2x)ˣ`` is e^((2x)^x) or (e^(2x))^x, and nothing says which.
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
# The suffixes an English ordinal raises: "1ˢᵗ", "2ⁿᵈ", "3ʳᵈ", "4ᵗʰ", "nᵗʰ".
_ORDINAL_SUFFIXES = frozenset({"st", "nd", "rd", "th"})
_ROOT = "√"
# A root's raised index as the sign that writes it; another index stays for the parser.
_ROOT_SIGNS = {"2": _ROOT, "3": "∛", "4": "∜"}
# The longest bracketed power read back to its caret.
_POWER_SPAN = 200


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
    if _signed_digits(script) and (len(script) == 1 or not group_numbers):
        return f"{mark}{script}"
    if len(script) == 1 and not glued:
        return f"{mark}{script}"
    inner = script[1:-1] if _wrapped(script) else script
    return f"{mark}({inner})"


def root_index_at(text: str, index: int) -> tuple[str, int] | None:
    """The index raised before a root sign at ``index``, and where the sign ends:
    ``³√27`` → ``("3", 2)``. A run is read from its first digit. After a letter or a
    number only one digit from 3 is an index (``2³√27`` is 2∛27); a 2 or a longer run
    there is its power (``x²√x`` is x² times √x), since a square root writes no index.

    Read as the power, "Evaluate 2³√27" was a checked 24√3 (2026-11-14)."""
    if index and text[index - 1] in SUPERSCRIPT_GLYPHS:
        return None
    end = index
    while (
        end < len(text)
        and text[end] in SUPERSCRIPT_GLYPHS
        and SUPERSCRIPT_GLYPHS[text[end]].isdigit()
    ):
        end += 1
    if end == index or text[end : end + 1] != _ROOT:
        return None
    digits = "".join(SUPERSCRIPT_GLYPHS[char] for char in text[index:end])
    if index and _maths_atom(text[index - 1]) and not (len(digits) == 1 and digits >= "3"):
        return None
    return digits, end + 1


def _opening(text: str, close: int) -> int:
    """Where the bracket closing at ``close`` opens, or -1 past ``_POWER_SPAN`` characters
    (no power is that long, and a long paste of brackets is not read back once per run)."""
    depth = 0
    for at in range(close, max(close - _POWER_SPAN, -1), -1):
        depth += {")": 1, "]": 1, "}": 1, "(": -1, "[": -1, "{": -1}.get(text[at], 0)
        if depth == 0:
            return at
    return -1


def _after_caret_power(text: str, index: int) -> bool:
    """The run at ``index`` comes straight after a power typed with a caret: ``e^x²``,
    ``e^(2x)ˣ``, ``e^2ˣ``, ``4^(1/2)⁻¹``. A caret's operand is a bracket, a number or one
    letter."""
    before = text[index - 1] if index else ""
    start = index - 1
    if before in ")]}":
        start = _opening(text, start)
    elif before.isascii() and before.isdigit():
        while (
            start
            and text[start - 1].isascii()
            and (text[start - 1].isdigit() or text[start - 1] == ".")
        ):
            start -= 1
    elif not (before.isascii() and before.isalpha()):
        return False
    return start > 0 and text[:start].endswith(("^", "**"))


def _raises_here(text: str, index: int, core: str) -> bool:
    """Whether the run at ``index`` may raise what it stands on. After a caret's number or
    letter, only digits do, going on with that power: read as nothing, "Differentiate e^x²"
    and "Evaluate 2^3²" were declined, which they never were before (2026-11-14)."""
    if not _after_caret_power(text, index):
        return True
    return core.isdigit() and text[index - 1] not in _CLOSED_ATOMS


def _ordinal(body: str, before: str) -> bool:
    """``21ˢᵗ``, ``2ⁿᵈ``, ``nᵗʰ``, ``(n+1)ᵗʰ``: a number's or a letter's ordinal suffix."""
    if before.isascii() and before.isdigit():
        return body in _ORDINAL_SUFFIXES
    return body == "th" and ((before.isascii() and before.isalpha()) or before == ")")


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
        root = root_index_at(text, index)
        if root is not None and root[0] in _ROOT_SIGNS:
            out.append(_ROOT_SIGNS[root[0]])
            index = root[1]
            continue
        end = index
        while end < len(text) and text[end] in SUPERSCRIPT_GLYPHS:
            end += 1
        run = "".join(SUPERSCRIPT_GLYPHS[char] for char in text[index:end])
        core = run.rstrip(_DANGLING)
        before = text[index - 1] if index else ""
        after = text[end] if end < len(text) else ""
        if run == core and _ordinal(core, before):
            out.append(core)
            index = end
            continue
        power = None
        if core and root is None and _raises_here(text, index, core):
            power = _raised(core, before, after)
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
