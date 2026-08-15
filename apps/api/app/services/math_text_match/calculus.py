"""Limit / series / integral / calculus-op cues."""

from __future__ import annotations

from dataclasses import dataclass

from app.services.math_text_match.scan import _CALC_OP, _parse_unsigned_number


def calc_op(text: str) -> str | None:
    m = _CALC_OP.search(text)
    return m.group(1).lower() if m else None


def _match_limit_point(s: str) -> tuple[str, int] | None:
    """Match infinity / oo / number at start of ``s``; return (token, end)."""
    low = s.lower()
    for tok in ("-infinity", "infinity", "-inf", "inf", "-oo", "oo"):
        if low.startswith(tok):
            return s[: len(tok)], len(tok)
    start = 1 if s.startswith("-") else 0
    hit = _parse_unsigned_number(s, start)
    if hit is None or (start == 1 and hit[1] == 1):
        return None
    return s[: hit[1]], hit[1]


def _parse_signed_int_token(s: str) -> tuple[str, int] | None:
    start = 1 if s.startswith("-") else 0
    if start >= len(s) or not s[start].isdigit():
        return None
    i = start
    while i < len(s) and s[i].isdigit():
        i += 1
    return s[:i], i


@dataclass(frozen=True)
class LimitHit:
    expr: str
    var: str
    point: str


def _parse_latex_limit(text: str) -> LimitHit | None:
    """Parse ``\\lim_{x \\to 0} expr`` without optional-space regex pumps."""
    idx = text.find("\\lim")
    if idx == -1:
        return None
    rest = text[idx + 4 :]
    while rest.startswith("_") or rest.startswith(" "):
        rest = rest[1:]
    if rest.startswith("{"):
        rest = rest[1:]
    rest = rest.lstrip(" ")
    if not rest or not rest[0].isalpha():
        return None
    var = rest[0]
    rest = rest[1:].lstrip(" ")
    arrow = None
    for candidate in ("\\to", "->", "→"):
        if rest.startswith(candidate):
            arrow = candidate
            break
    if arrow is None:
        return None
    rest = rest[len(arrow) :].lstrip(" ")
    point_hit = _match_limit_point(rest)
    if point_hit is not None:
        point, plen = point_hit
    elif rest.lower().startswith("-\\infty"):
        point, plen = "-\\infty", 7
    elif rest.lower().startswith("\\infty"):
        point, plen = "\\infty", 6
    else:
        return None
    rest = rest[plen:].lstrip(" ")
    if rest.startswith("}"):
        rest = rest[1:].lstrip(" ")
    expr = rest.strip()
    if not expr:
        return None
    return LimitHit(expr=expr, var=var, point=point)


def parse_limit(text: str) -> LimitHit | None:
    lower = text.lower()
    # Compact: lim x->0 expr
    if lower.startswith("lim ") or " lim " in f" {lower} ":
        idx = lower.find("lim ")
        rest = text[idx + 4 :].strip()
        # var
        if not rest:
            return None
        var = rest[0]
        if not var.isalpha():
            return None
        rest_l = rest[1:].lstrip()
        for arrow in ("->", "→"):
            if rest_l.startswith(arrow):
                rest_l = rest_l[len(arrow) :].lstrip()
                break
        else:
            return None
        point_hit = _match_limit_point(rest_l)
        if not point_hit:
            return None
        point, pend = point_hit
        expr = rest_l[pend:].strip()
        if expr.lower().startswith("of "):
            expr = expr[3:].strip()
        if expr:
            return LimitHit(expr=expr, var=var, point=point)
    # Prose: ... as x approaches 0
    as_idx = lower.find(" as ")
    if as_idx != -1 and ("limit" in lower or "lim" in lower):
        before = text[:as_idx].strip()
        for lead in (
            "find ",
            "evaluate ",
            "compute ",
            "what is ",
            "determine ",
            "the ",
            "limit of ",
        ):
            low = before.lower()
            if low.startswith(lead):
                before = before[len(lead) :].strip()
        after = text[as_idx + 4 :].strip()
        if not after or not after[0].isalpha():
            return None
        var = after[0]
        rest = after[1:].lstrip().lower()
        for cue in ("approaches ", "goes to ", "tends to ", "->", "→", "to "):
            if rest.startswith(cue):
                rest = rest[len(cue) :].lstrip()
                break
        else:
            return None
        # prose uses "infinity" / "inf" / number (allow longer "infinity" spelling)
        point_hit = _match_limit_point(rest)
        if point_hit is None:
            for tok in ("-infinity", "infinity"):
                if rest.startswith(tok):
                    point_hit = (tok, len(tok))
                    break
        if not point_hit or not before:
            return None
        return LimitHit(expr=before, var=var, point=point_hit[0])
    return _parse_latex_limit(text)


@dataclass(frozen=True)
class SeriesHit:
    expr: str
    var: str
    start: str
    end: str


def _parse_latex_series(text: str) -> SeriesHit | None:
    """Parse ``\\sum_{n=1}^{\\infty} expr`` without optional-space regex pumps."""
    idx = text.find("\\sum")
    if idx == -1:
        return None
    rest = text[idx + 4 :]
    while rest.startswith("_") or rest.startswith(" "):
        rest = rest[1:]
    if rest.startswith("{"):
        rest = rest[1:]
    rest = rest.lstrip(" ")
    if not rest or not rest[0].isalpha():
        return None
    var = rest[0]
    rest = rest[1:].lstrip(" ")
    if not rest.startswith("="):
        return None
    rest = rest[1:].lstrip(" ")
    start_hit = _parse_signed_int_token(rest)
    if start_hit is None:
        return None
    start, send = start_hit
    rest = rest[send:].lstrip(" ")
    if rest.startswith("}"):
        rest = rest[1:].lstrip(" ")
    if not rest.startswith("^"):
        return None
    rest = rest[1:].lstrip(" ")
    if rest.startswith("{"):
        rest = rest[1:]
    rest = rest.lstrip(" ")
    end_tok: str | None = None
    low = rest.lower()
    for tok in ("\\infty", "infinity"):
        if low.startswith(tok):
            end_tok = rest[: len(tok)]
            rest = rest[len(tok) :]
            break
    if end_tok is None:
        end_hit = _parse_signed_int_token(rest)
        if end_hit is None:
            return None
        end_tok, eend = end_hit
        rest = rest[eend:]
    rest = rest.lstrip(" ")
    if rest.startswith("}"):
        rest = rest[1:].lstrip(" ")
    expr = rest.strip()
    if not expr:
        return None
    return SeriesHit(expr=expr, var=var, start=start, end=end_tok)


def parse_series(text: str) -> SeriesHit | None:
    lower = text.lower()
    if not any(k in lower for k in ("sum ", "series", "converge", "diverge")):
        # also bare "sum of"
        if "sum" not in lower:
            return None
    # sum|series [of] EXPR from VAR=START to END
    for head in ("sum of ", "series of ", "sum ", "series "):
        idx = lower.find(head)
        if idx == -1:
            continue
        rest = text[idx + len(head) :]
        from_idx = rest.lower().find(" from ")
        if from_idx == -1:
            continue
        expr = rest[:from_idx].strip()
        tail = rest[from_idx + 6 :].strip()
        parts = tail.replace(" ", "")
        # var=START to END — linear scan on compacted digits
        if not parts or not parts[0].isalpha():
            continue
        var = parts[0]
        if len(parts) < 2 or parts[1] != "=":
            continue
        after_eq = parts[2:]
        start_hit = _parse_signed_int_token(after_eq)
        if start_hit is None:
            continue
        start, send = start_hit
        after_start = after_eq[send:]
        if not after_start.lower().startswith("to"):
            continue
        after_to = after_start[2:]
        end_tok: str | None = None
        low_end = after_to.lower()
        for tok in ("infinity", "inf", "oo"):
            if low_end.startswith(tok):
                end_tok = after_to[: len(tok)]
                break
        if end_tok is None:
            end_hit = _parse_signed_int_token(after_to)
            if end_hit is None:
                continue
            end_tok = end_hit[0]
        if expr:
            return SeriesHit(expr=expr, var=var, start=start, end=end_tok)
    return _parse_latex_series(text)


def integral_bounds(expr: str) -> tuple[str, str, str] | None:
    """Return (expr_without_bounds, lo, hi) for trailing ``from LO to HI``."""
    lower = expr.lower()
    idx = lower.rfind(" from ")
    if idx == -1:
        return None
    head = expr[:idx].strip()
    tail = expr[idx + 6 :].strip()
    to_idx = tail.lower().find(" to ")
    if to_idx == -1:
        return None
    lo = tail[:to_idx].strip()
    hi = tail[to_idx + 4 :].strip()
    if head and lo and hi and " " not in hi:
        return head, lo, hi
    return None
