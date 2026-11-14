"""A law's symbols as a formula writes them, read one at a time.

``reduction`` reads a law's side in its symbols to line it up with the numbers a row put
in; this reads each symbol: a letter (v, m), a Greek one (\\theta), with its subscript and
primes, \\Delta before one, or a decorated letter (\\mathcal{E}).
"""

from __future__ import annotations

import re

from app.services.latex_groups import group_end

# A law's symbol in a formula: a letter (v, m), a Greek one (\\theta), either with its
# subscript (v_f, h_{\\max}, t_{\\text{top}}) and primes, \\Delta before one (\\Delta t),
# or a decorated letter (\\mathcal{E}, \\bar{v}).
_GREEK = frozenset(
    {
        "alpha", "beta", "gamma", "delta", "epsilon", "varepsilon", "zeta", "eta", "theta",
        "kappa", "lambda", "mu", "nu", "xi", "rho", "sigma", "tau", "phi", "varphi", "chi",
        "psi", "omega", "Gamma", "Theta", "Lambda", "Phi", "Psi", "Omega",
    }
)  # fmt: skip
_DECORATED = frozenset({"mathcal", "bar", "vec", "hat"})
_COMMAND = re.compile(r"\\([A-Za-z]+)")


def symbol_at(tex: str, start: int) -> tuple[str, int] | None:
    """The symbol written at ``start`` and the index past it, or None when none starts there."""
    if start < len(tex) and tex[start].isascii() and tex[start].isalpha():
        end = start + 1
    else:
        command = _COMMAND.match(tex, start)
        if command is None:
            return None
        word = command.group(1)
        end = command.end()
        if word == "Delta":
            while end < len(tex) and tex[end].isspace():
                end += 1
            inner = symbol_at(tex, end)
            return None if inner is None else (plain_symbol(f"\\Delta {inner[0]}"), inner[1])
        if word in _DECORATED:
            if end >= len(tex) or tex[end] != "{":
                return None
            end = group_end(tex, end)
        elif word not in _GREEK:
            return None
    if end < len(tex) and tex[end] == "_":
        if end + 1 < len(tex) and tex[end + 1] == "{":
            end = group_end(tex, end + 1)
        elif end + 1 < len(tex) and tex[end + 1].isalnum():
            end += 2
        else:
            return None
    while end < len(tex) and tex[end] == "'":
        end += 1
    return plain_symbol(tex[start:end]), end


def plain_symbol(symbol: str) -> str:
    """One spelling of a symbol: ``v_{i}`` is ``v_i``, spaces dropped."""
    text = "".join(symbol.split())
    return re.sub(r"_\{([A-Za-z0-9])\}", r"_\1", text)
