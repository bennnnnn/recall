"""A function's bare argument ends before the next function name: ``sin x cos x`` is
sin(x)·cos(x).

SymPy's implicit application runs a bare argument on through every product, so it read
``sin x cos x`` as sin(x·cos x), and ``2 sin x cos x``, ``ln x sin x`` and ``sin θ cos θ`` the
same way: each a checked derivative, integral or value of a function nobody wrote
(2026-11-14). This step runs on SymPy's tokens before that one and closes the argument where
the next function name starts. Explicit brackets (``sin(x cos x)``), a nested name with
nothing after it (``sin cos x``), a power's operand (``x^cos x``) and anything ending the
argument sooner (``sin x + cos x``, ``sin x/cos x``) are left as they were. A name nested in
the argument ends it where its own argument ends: ``ln sin x cos x`` is ln(sin x)·cos x,
never ln(sin x·cos x).
"""

from __future__ import annotations

from tokenize import ENDMARKER, NAME, NEWLINE, NUMBER, OP
from typing import Any

from app.modules.math.function_names import MATH_FUNCTION_NAMES

_Token = tuple[int, str]


def _is_function(token: _Token) -> bool:
    return token[0] == NAME and token[1] in MATH_FUNCTION_NAMES


def _is_op(token: _Token, *values: str) -> bool:
    return token[0] == OP and token[1] in values


def _group_end(tokens: list[_Token], at: int) -> int | None:
    """Just past the bracket that opens at ``at``; None when it never closes."""
    depth = 0
    for index in range(at, len(tokens)):
        if _is_op(tokens[index], "("):
            depth += 1
        elif _is_op(tokens[index], ")"):
            depth -= 1
            if depth == 0:
                return index + 1
    return None


def _operand_end(tokens: list[_Token], at: int) -> int | None:
    """Just past one operand of ``**``: a bracket, a number (``Integer(2)``) or a name."""
    if at >= len(tokens):
        return None
    token = tokens[at]
    if _is_op(token, "+", "-"):
        return _operand_end(tokens, at + 1)
    if _is_op(token, "("):
        return _group_end(tokens, at)
    if token[0] == NAME and at + 1 < len(tokens) and _is_op(tokens[at + 1], "("):
        return _group_end(tokens, at + 1)
    return at + 1 if token[0] in (NAME, NUMBER) else None


def _past_power(tokens: list[_Token], after: int) -> int | None:
    """Past the power on the function before ``after`` (``sin**2 x``) and the product mark
    the normaliser puts after its digits; None when the power is no operand read here."""
    at = after
    if at < len(tokens) and _is_op(tokens[at], "**"):
        end = _operand_end(tokens, at + 1)
        if end is None:
            return None
        at = end + 1 if end < len(tokens) and _is_op(tokens[end], "*") else end
    return at if at < len(tokens) else None


def _nested_end(tokens: list[_Token], at: int) -> int | None:
    """Where the names nested from ``at`` (``sin x`` of ``ln sin x cos x``) meet the next
    function name: the innermost one's argument, bare or bracketed, ends there. None when
    it ends first, which leaves the whole to SymPy (``ln sin x + 1``)."""
    start: int | None = at
    while start is not None and _is_function(tokens[start]):
        start = _past_power(tokens, start + 1)
    if start is None:
        return None
    if _is_op(tokens[start], "("):
        group = _group_end(tokens, start)
        if group is None or group >= len(tokens):
            return None
        if _is_function(tokens[group]):
            return group
        following = group + 1
        if _is_op(tokens[group], "*") and following < len(tokens):
            return group if _is_function(tokens[following]) else None
        return None
    return _argument_end(tokens, start) if tokens[start][0] in (NAME, NUMBER) else None


def _argument_end(tokens: list[_Token], start: int) -> int | None:
    """Where a bare argument meets the next function name, as SymPy would carry it there:
    on through products and brackets, never past another operator. None when it ends
    first."""
    depth = 0
    for index in range(start, len(tokens)):
        token = tokens[index]
        if _is_op(token, "("):
            depth += 1
        elif _is_op(token, ")"):
            if depth == 0:
                return None
            depth -= 1
        elif depth == 0 and _is_function(token):
            previous = tokens[index - 1]
            if _is_op(previous, "**"):
                return None  # ``sin x^cos x``: the name is a power's, not the next factor
            return index - 1 if _is_op(previous, "*") else index
        elif token[0] in (ENDMARKER, NEWLINE) or (
            depth == 0 and token[0] == OP and token[1] not in ("*", "**")
        ):
            return None
    return None


def close_bare_arguments(tokens: list[_Token], _local_dict: Any, _global_dict: Any) -> list[_Token]:
    """A SymPy parser transformation: ``sin x cos x`` → ``sin (x) cos x``."""
    out: list[_Token] = []
    index = 0
    while index < len(tokens):
        token = tokens[index]
        out.append(token)
        index += 1
        if not _is_function(token):
            continue
        start = _past_power(tokens, index)
        if start is None:
            continue
        if _is_function(tokens[start]):
            # ``ln sin x cos x`` is ln(sin x)·cos x: the outer argument ends with the inner.
            end = _nested_end(tokens, start)
        elif tokens[start][0] in (NAME, NUMBER):
            end = _argument_end(tokens, start)
        else:
            continue  # bracketed or signed: SymPy reads it as written
        if end is None:
            continue
        out.extend(tokens[index:start])
        out.append((OP, "("))
        out.extend(tokens[start:end])
        out.append((OP, ")"))
        index = end
    return out
