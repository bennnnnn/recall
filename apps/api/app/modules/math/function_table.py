"""Every function a maths message may apply: how it is written, read and whether it is solved.

One table, so the reader that checks a reading kept each function (``function_calls.py``)
and the solver that declines a function it does not model (``solve/solved_functions.py``)
can never disagree about a name. Each row says:

- ``name``: the one name a function is counted under (``ln``, ``lg`` and ``log`` are ``log``);
- ``written``: the names a message may write before a bracket;
- ``read_as``: other spellings a reading may hold it in (SymPy's ``Abs``, the ``%`` of mod,
  ``cos`` for where ``sec`` is undefined), as regular expressions;
- ``solved``: whether an equation in it is one the solvers work, and ``sympy`` the SymPy
  function that stands for it in a parse (``None`` for a root, which parses to a power).

``REQUEST_WORDS`` are the verbs and nouns of a request written against a bracket
(``Solve(2x + 1 = 5)``): never a function.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.modules.math.function_names import HYPERBOLIC, TRIG


@dataclass(frozen=True)
class MathFunction:
    name: str
    written: tuple[str, ...]
    read_as: tuple[str, ...] = ()
    solved: bool = False
    sympy: str | None = None


_RECIPROCAL_PARTNER = {"sec": ("cos",), "csc": ("sin",), "cot": ("tan", "cos")}


def _trig_rows() -> tuple[MathFunction, ...]:
    rows = []
    for name in (*TRIG, *HYPERBOLIC):
        # A reciprocal is read through its partner: where sec(x) is undefined, cos(x) = 0.
        rows.append(MathFunction(name, (name,), _RECIPROCAL_PARTNER.get(name, ()), True, name))
        rows.append(MathFunction(f"a{name}", (f"a{name}", f"arc{name}"), (), True, f"a{name}"))
    return tuple(rows)


FUNCTIONS: tuple[MathFunction, ...] = (
    *_trig_rows(),
    MathFunction("log", ("log", "ln", "lg"), (), True, "log"),
    MathFunction("exp", ("exp",), (r"(?<![^\W\d_])[eE]\s*(?:\^|\*\*)",), True, "exp"),
    MathFunction("abs", ("abs",), (), True, "Abs"),
    MathFunction("sqrt", ("sqrt",), ("root", "√"), True),
    MathFunction("cbrt", ("cbrt",), ("root", "∛", r"1\s*/\s*3"), True),
    MathFunction("root", ("root",), ("sqrt", "cbrt"), True),
    MathFunction("floor", ("floor",), ("⌊",)),
    MathFunction("ceiling", ("ceil", "ceiling"), ("⌈",)),
    MathFunction("sign", ("sign", "sgn", "signum")),
    MathFunction("frac", ("frac",)),
    MathFunction("round", ("round",)),
    MathFunction("trunc", ("trunc",)),
    MathFunction("mod", ("mod", "modulo"), ("%",)),
    MathFunction("congruence", (), ("≡", "equiv", "congruen")),
    MathFunction("max", ("max",)),
    MathFunction("min", ("min",)),
    MathFunction("gcd", ("gcd", "hcf", "gcf")),
    MathFunction("lcm", ("lcm",)),
    MathFunction("heaviside", ("heaviside",)),
    MathFunction("piecewise", ("piecewise",)),
    MathFunction("factorial", ("factorial",), ("!",)),
    MathFunction("gamma", ("gamma", "Γ")),
    MathFunction("zeta", ("zeta", "ζ")),
    MathFunction("erf", ("erf", "erfc")),
    MathFunction("totient", ("totient",)),
    MathFunction("choose", ("ncr", "choose", "binomial", "binom", "comb"), (r"combinations?",)),
    MathFunction("permute", ("npr", "perm"), (r"permutations?",)),
    MathFunction("det", ("det",), ("determinant",)),
    MathFunction("re", ("re",)),
    MathFunction("im", ("im",)),
    MathFunction("arg", ("arg",)),
    MathFunction("conjugate", ("conjugate",)),
    MathFunction("sum", ("sum",)),
    MathFunction("mean", ("mean",), ("average",)),
    MathFunction("median", ("median",)),
    MathFunction("mode", ("mode",)),
    MathFunction("variance", ("var", "variance")),
    MathFunction("stdev", ("std", "stdev"), ("standard_deviation",)),
)

BY_NAME = {function.name: function for function in FUNCTIONS}
# Each name a message may write, lowercased, and the function it names.
WRITTEN = {written.lower(): function for function in FUNCTIONS for written in function.written}
UNSOLVED_WRITTEN = tuple(
    written for function in FUNCTIONS if not function.solved for written in function.written
)
SOLVED_SYMPY = tuple(function.sympy for function in FUNCTIONS if function.solved and function.sympy)

REQUEST_WORDS = frozenset(
    {
        "solve", "simplify", "evaluate", "calculate", "compute", "find", "determine",
        "factor", "factorise", "factorize", "expand", "differentiate", "derive",
        "derivative", "integrate", "integral", "limit", "lim", "graph", "plot", "sketch",
        "draw", "show", "check", "verify", "convert", "what", "whats", "is", "of", "and",
        "or", "the", "for", "if", "then", "where", "when", "with", "let", "given", "answer",
        "equation", "expression", "inequality", "system", "value", "values", "point",
        "points", "interval", "domain", "range", "area", "at", "to", "in", "on",
    }
) - frozenset(WRITTEN)  # fmt: skip
