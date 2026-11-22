"""TeX a model wrote, in the form a renderer draws: every brace closed, one subscript and one
superscript on each base.

The worked block's Required line read ``v_A_{vec}`` and its card ``(-16\\hat{i} + 0\\hat{j})\\
\\mathrm{m/s``, the brace never closed (the owner's chat, 2026-11-20). TeX refuses both, a
double subscript and a group that never ends, so the phone drew them as source. Both are
mistakes of form with one reading:

- a group left open is closed at the field's end, as the writer stopped;
- a second superscript on one base belongs to the base with its first, as TeX reads
  ``{x^2}^3``; a second subscript is more of the first, ``v_{A,vec}``: one subscript that
  names both, never a script of a script (``{{V_{small}}_{cone}}_{volume}``, 2026-11-21);
- a closing brace with no group open is a stray, left out: ``\\frac{1}{2}}`` lost its card
  when the record was refused for it (review, 2026-11-20).
"""

from __future__ import annotations


def well_formed(tex: str) -> str:
    """``tex`` with its groups closed, a stray closing brace left out, and its scripts one
    per base."""
    return _one_script_each(_groups_closed(tex))


def _groups_closed(tex: str) -> str:
    out: list[str] = []
    depth = 0
    at = 0
    while at < len(tex):
        char = tex[at]
        if char == "\\":
            out.append(tex[at : at + 2])  # an escaped brace (\{, \}) or a command's letter
            at += 2
            continue
        if char == "{":
            depth += 1
        elif char == "}":
            if depth == 0:
                at += 1
                continue
            depth -= 1
        out.append(char)
        at += 1
    return "".join(out) + "}" * depth


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
    """Each base's second subscript or superscript set on the base with its first, inside
    every group too: ``\\frac{v_A_{vec}}{2}`` holds one (Claude on #2509)."""
    out: list[str] = []
    at = 0
    while at < len(tex):
        if tex[at] in "_^":  # a script with no base of its own: as written
            out.append(tex[at])
            at += 1
            continue
        start, at = at, _token_end(tex, at)
        base = _within(tex[start:at])
        seen: set[str] = set()
        # The base and the words of its one subscript, while it has no superscript: a
        # second subscript joins them.
        subscript: tuple[str, str] | None = None
        while (mark := _skip_spaces(tex, at)) < len(tex) and tex[mark] in "_^":
            script = _skip_spaces(tex, mark + 1)
            end = _token_end(tex, script) if script < len(tex) else script
            words = _within(tex[script:end])
            if tex[mark] == "_" and subscript is not None:
                # "r_{frustum}_{top}" is one subscript of both, r_{frustum,top}: set on its
                # base, {r_{frustum}}_{top} read as a script of a script (2026-11-21).
                joined = f"{subscript[1]},{_inner(words)}"
                base, subscript, at = f"{subscript[0]}_{{{joined}}}", (subscript[0], joined), end
                continue
            if tex[mark] in seen:
                base, seen = f"{{{base}}}", set()
            seen.add(tex[mark])
            subscript = (base, _inner(words)) if tex[mark] == "_" and seen == {"_"} else None
            base += tex[at:script] + words
            at = end
        out.append(base)
    return "".join(out)


def _inner(token: str) -> str:
    """A script's words without its braces."""
    return token[1:-1] if len(token) >= 2 and token[0] == "{" and token[-1] == "}" else token


def _within(token: str) -> str:
    """A group's contents with one script each; any other token as it is."""
    if len(token) >= 2 and token[0] == "{" and token[-1] == "}":
        return "{" + _one_script_each(token[1:-1]) + "}"
    return token
