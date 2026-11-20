"""TeX a model wrote, in the form a renderer draws: every brace closed, one subscript and one
superscript on each base.

The worked block's Required line read ``v_A_{vec}`` and its card ``(-16\\hat{i} + 0\\hat{j})\\
\\mathrm{m/s``, the brace never closed (the owner's chat, 2026-11-20). TeX refuses both, a
double subscript and a group that never ends, so the phone drew them as source. Both are
mistakes of form with one reading:

- a group left open is closed at the field's end, as the writer stopped;
- a second script on one base belongs to the base with its first, ``{v_A}_{vec}``, as TeX
  reads ``{x^2}^3``.

A closing brace with no group open has no reading: the field is refused, and the record
holding it goes (``worked_solution``).
"""

from __future__ import annotations


def well_formed(tex: str) -> str | None:
    """``tex`` with its groups closed and its scripts one per base; None when a brace closes
    a group that never opened."""
    closed = _groups_closed(tex)
    return None if closed is None else _one_script_each(closed)


def _groups_closed(tex: str) -> str | None:
    depth = 0
    at = 0
    while at < len(tex):
        char = tex[at]
        if char == "\\":
            at += 2  # an escaped brace (\{, \}) or a command's first letter
            continue
        if char == "{":
            depth += 1
        elif char == "}":
            if depth == 0:
                return None
            depth -= 1
        at += 1
    return tex + "}" * depth


def _token_end(tex: str, at: int) -> int:
    """Past the token at ``at``: a command, a group, or one character."""
    if tex[at] == "\\":
        end = at + 1
        while end < len(tex) and tex[end].isalpha():
            end += 1
        return max(end, at + 2) if end == at + 1 else end
    if tex[at] == "{":
        depth = 0
        for end in range(at, len(tex)):
            if tex[end] == "{" and tex[end - 1] != "\\":
                depth += 1
            elif tex[end] == "}" and tex[end - 1] != "\\":
                depth -= 1
                if depth == 0:
                    return end + 1
        return len(tex)
    return at + 1


def _skip_spaces(tex: str, at: int) -> int:
    while at < len(tex) and tex[at] in " \t":
        at += 1
    return at


def _one_script_each(tex: str) -> str:
    """Each base's second subscript or superscript set on the base with its first."""
    out: list[str] = []
    at = 0
    while at < len(tex):
        if tex[at] in "_^":  # a script with no base of its own: as written
            out.append(tex[at])
            at += 1
            continue
        start, at = at, _token_end(tex, at)
        base = tex[start:at]
        seen: set[str] = set()
        while (mark := _skip_spaces(tex, at)) < len(tex) and tex[mark] in "_^":
            script = _skip_spaces(tex, mark + 1)
            end = _token_end(tex, script) if script < len(tex) else script
            if tex[mark] in seen:
                base, seen = f"{{{base}}}", set()
            seen.add(tex[mark])
            base += tex[at:end]
            at = end
        out.append(base)
    return "".join(out)
