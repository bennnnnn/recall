"""Whether a maths message asks for something besides its result: a leftover-words count.

``Solve x+1=2 and tell me a joke`` must not become an instant ``x = 1``. Pure text, so
the verified blocks may ask it as well as the direct-reply guard.
"""

from __future__ import annotations

# Polite glue around a closed compute; two more English words ("tell joke") keep the LLM.
_MATH_REQUEST_GLUE = frozenset(
    {
        "solve",
        "isolate",
        "factor",
        "expand",
        "simplify",
        "calculate",
        "compute",
        "evaluate",
        "determine",
        "find",
        "please",
        "thanks",
        "thank",
        "now",
        "quickly",
        "briefly",
        "here",
        "what",
        "whats",
        "the",
        "value",
        "of",
        "over",
        "for",
        "and",
        "then",
        "is",
        "equals",
        "equal",
        "plus",
        "minus",
        "times",
        "can",
        "you",
        "could",
        "this",
        "that",
        "real",
        "numbers",
    }
)


def _looks_math_token(tok: str, after: str = "") -> bool:
    tok = tok.lstrip("(")  # "(x - sin x)/x^3"
    names = ("sqrt", "sin", "cos", "tan", "sec", "csc", "cot", "log", "ln", "exp", "lim")
    # A bare name is maths before "(" or a variable ("sin x", "lim x->0"), not "wait a sec".
    variable = after[:1].isalpha() and not after[1:2].isalpha()
    bare = tok in names and (after[:1] == "(" or variable)
    if not tok or bare or any(tok.startswith(f"{name}(") for name in names):
        return True
    return any(ch.isdigit() or ch in "=^*/+-%" for ch in tok)


def leftover_non_math_request(text: str) -> bool:
    """True when the message asks for something besides the verified value.

    ``Solve x+1=2 and tell me a joke`` must not become an instant ``x = 1``.
    Linear token walk — no regex on user text.
    """
    english = 0
    for at, raw in enumerate(tokens := text.replace("'", "").lower().split()):
        tok, after = raw.strip(".,?!:;"), tokens[at + 1] if at + 1 < len(tokens) else ""
        if _looks_math_token(tok, after) or len(tok) < 3 or tok in _MATH_REQUEST_GLUE:
            continue
        english += 1
        if english >= 2:
            return True
    return False
