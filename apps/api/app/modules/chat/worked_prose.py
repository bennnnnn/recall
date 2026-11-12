# ruff: noqa: RUF001 -- maths signs are read as written.
r"""Words a model wrote in a ```worked block, with the maths in them marked as maths.

A block's word fields (a formula's heading, a move, what a given or the unknown is, a
part's title, a note after the answer) reach the phone as text, and a model writes maths
into them: "Substitution x = \tan t", "evenness of \ln\cos t", "KE = \frac{1}{2}mv^2"
(DeepSeek, 2026-11-11). ``prose_maths`` keeps the maths the model delimited (``$…$``,
``\(…\)``) and marks each other run of maths as one ``$…$``: a command or a script starts
it, and it runs on over signs, numbers, brace groups, the letters glued to them ("mv" in
``\frac{1}{2}mv^2``), a symbol a sign joins ("x =", "KE ="), never over a word of the
sentence. Two runs that meet are one, so no ``$…$$…$`` reaches the phone, which reads a
``$`` right after another as no maths and shows the source. A ``$`` the words keep (a price,
"$5") is written ``\$``.
"""

from __future__ import annotations

import re

# Maths the model marked itself: ``\(…\)``, ``\[…\]`` or ``$…$`` (a ``$`` before a space or
# a closing one after it is a price's, never maths).
_MARKED = re.compile(
    r"\\\((?P<paren>.+?)\\\)|\\\[(?P<bracket>.+?)\\\]"
    r"|(?<![\\$])\$(?=\S)(?P<dollar>(?:\\\$|[^$\n])*?\S)(?<!\\)\$"
)
_CODE_MARKS = re.compile(r"`")
_TEX_SPACE = re.compile(r"\\[,;:! ]")
_EMPHASIS = re.compile(r"[*_]")
# A backslash before anything but a letter or a dollar ("5\%") is no command.
_LONE_BACKSLASH = re.compile(r"\\(?![A-Za-z$])")
_BARE_DOLLAR = re.compile(r"(?<!\\)\$")
# An underscore inside a word joins two words ("per_sheep"); elsewhere it marks emphasis.
_JOINED_WORDS = re.compile(r"(?<=[^\W_])_(?=[^\W_])")
# Where maths starts in words: a command, or a script on what it raises ("v_0", "m^{2}"),
# never an underscore inside a word ("per_sheep").
_MATHS_START = re.compile(
    r"\\[A-Za-z]|(?<=[A-Za-z0-9)\]}])[\^_](?=[{(\\]|-?\d|[A-Za-z](?![A-Za-z]))"
)
_COMMAND = re.compile(r"\\[A-Za-z]+")
_NUMBER = re.compile(r"\d+(?:\.\d+)?")
_RUN = re.compile(r"[^\W\d_]+")
# A relation joins whole sides ("KE ="); a sign joins terms ("a +").
_RELATIONS = frozenset("=<>≤≥≈≠")
_SIGNS = frozenset("+-*/^_|!()[]×·−") | _RELATIONS
_CLOSES = {")": "(", "]": "["}
_OPENS = {"(": ")", "[": "]"}
# What a run of maths never ends on, or starts with: it joins the maths to the words.
_TRAILING = frozenset("=+-*/<>^_,≤≥≈≠")
_LEADING = frozenset("=+*/<>,≤≥≈≠")
# A side of a relation as short as a symbol's name ("KE", "mgh"); a longer run is a word.
_SIDE_LETTERS = 3
# Kinds of token a run of letters may be glued to, with no space, and stay maths.
_GLUES = frozenset({"command", "group", "number", "letters", "sign"})


def _group_end(text: str, opening: int) -> int:
    """Where the brace group opened at ``opening`` ends (past its ``}``), or the text's end."""
    depth = 0
    for at in range(opening, len(text)):
        if text[at] == "{":
            depth += 1
        elif text[at] == "}":
            depth -= 1
            if depth == 0:
                return at + 1
    return len(text)


def _token(text: str, at: int) -> tuple[int, str] | None:
    """The maths token at ``at``, its end and its kind, or None where nothing maths starts."""
    char = text[at]
    command = _COMMAND.match(text, at)
    if command is not None:
        end = command.end()
        while end < len(text) and text[end] == "{":
            end = _group_end(text, end)
        return end, "command" if end == command.end() else "group"
    if char == "{":
        return _group_end(text, at), "group"
    if char in _SIGNS:
        return at + 1, "relation" if char in _RELATIONS else "sign"
    if (number := _NUMBER.match(text, at)) is not None:
        return number.end(), "number"
    if (run := _RUN.match(text, at)) is not None:
        return run.end(), "letter" if run.end() - at == 1 else "letters"
    return None


def _island_end(text: str, at: int) -> int:
    """Where the maths from ``at`` ends: past each command, group, sign and number, the
    letters glued to them ("\\frac{1}{2}mv"), a symbol a function or a sign takes
    ("\\cos t", "= x"), and an integral's differential; never a word after a space."""
    end, last, integral = at, "", False
    while end < len(text):
        start = end
        while start < len(text) and text[start] == " ":
            start += 1
        token = _token(text, start) if start < len(text) else None
        if token is None:
            break
        after, kind = token
        spaced = start > end
        integral = integral or text.startswith("\\int", start)
        if kind == "letters" and spaced:
            differential = integral and re.fullmatch(r"d[A-Za-z]", text[start:after])
            if not (differential or (last == "relation" and after - start <= _SIDE_LETTERS)):
                break
        # A letter after a group and a space ("\sqrt{2} a lot") is the sentence's again.
        if kind == "letter" and spaced and last == "group":
            break
        end, last = after, kind
    return end


def _island_start(text: str, at: int, floor: int) -> int:
    """Where the maths that reaches ``at`` starts: back over signs and numbers, the letters
    glued to it ("mv" of "mv^2"), and a symbol a sign joins on ("x =", "KE ="); never a word
    of the sentence ("the", "speed")."""
    start = cursor = at
    right = "sign" if text[at] in "^_" else "command"
    while cursor > floor:
        before = cursor
        while before > floor and text[before - 1] == " ":
            before -= 1
        if before == floor:
            break
        spaced, char = before < cursor, text[before - 1]
        if (
            char in _SIGNS
            or char.isdigit()
            or (char == "." and text[before - 2 : before - 1].isdigit())
        ):
            cursor = before - 1
            start, right = (
                cursor,
                "relation" if char in _RELATIONS else "sign" if char in _SIGNS else "number",
            )
            continue
        run = re.search(r"[^\W\d_]+$", text[floor:before])
        if run is None:
            break
        size = len(run.group())
        glued = not spaced and right in _GLUES
        joined = (right == "sign" and size == 1) or (right == "relation" and size <= _SIDE_LETTERS)
        if not (glued or joined):
            break
        cursor = before - size
        start, right = cursor, "letters"
    return start


def _trimmed(text: str, start: int, end: int) -> tuple[int, int]:
    """The run without what belongs to the words around it: a bracket it does not open
    ("x = \\pi/3)" in "(at x = \\pi/3)"), a sign at its end, a relation at its start."""
    while end > start:
        last = text[end - 1]
        unopened = last in _CLOSES and text.count(last, start, end) > text.count(
            _CLOSES[last], start, end
        )
        if not (last.isspace() or unopened or last in _TRAILING):
            break
        end -= 1
    while start < end:
        first = text[start]
        unclosed = first in _OPENS and text.count(first, start, end) > text.count(
            _OPENS[first], start, end
        )
        if not (first.isspace() or unclosed or first in _LEADING):
            break
        start += 1
    return start, end


def _words(text: str) -> str:
    """Words as text: emphasis marks go, a stray backslash goes, a ``$`` stays a sign."""
    plain = _LONE_BACKSLASH.sub("", _EMPHASIS.sub("", _JOINED_WORDS.sub(" ", text)))
    return _BARE_DOLLAR.sub(r"\\$", plain)


def _unmarked(text: str, pieces: list[tuple[str, str]]) -> None:
    """``text``, words with no maths marks, as word and maths pieces."""
    plain = _TEX_SPACE.sub(" ", text)
    done = 0
    while (found := _MATHS_START.search(plain, done)) is not None:
        start, end = _trimmed(
            plain, _island_start(plain, found.start(), done), _island_end(plain, found.start())
        )
        pieces.append(("words", plain[done:start]))
        pieces.append(("maths", plain[start:end]))
        done = max(end, found.end())
    pieces.append(("words", plain[done:]))


def _joined(pieces: list[tuple[str, str]]) -> str:
    """The pieces as one line; two runs of maths with nothing but a space between are one."""
    out: list[tuple[str, str]] = []
    for kind, text in pieces:
        if kind == "maths" and not text.strip():
            continue
        gap = out[-1] if out and out[-1][0] == "words" and not out[-1][1].strip() else None
        if kind == "maths" and len(out) > 1 and gap is not None and out[-2][0] == "maths":
            out[-2:] = [("maths", f"{out[-2][1]}{gap[1]}{text}")]
        elif kind == "maths" and out and out[-1][0] == "maths":
            out[-1] = ("maths", f"{out[-1][1]}{text}")
        else:
            out.append((kind, text))
    shown = "".join(f"${text.strip()}$" if kind == "maths" else _words(text) for kind, text in out)
    return " ".join(shown.split())


def prose_maths(text: str) -> str:
    r"""``text``, words a model wrote, with each run of maths in it as inline maths:
    "evenness of \ln\cos t" → "evenness of $\ln\cos t$", "KE = \frac{1}{2}mv^2" →
    "$KE = \frac{1}{2}mv^2$", "at x = \pi/3" → "at $x = \pi/3$". Markdown marks and a stray
    backslash go from the words around the maths, and a price's ``$`` is ``\$``."""
    plain = _CODE_MARKS.sub("", text)
    pieces: list[tuple[str, str]] = []
    done = 0
    for marked in _MARKED.finditer(plain):
        _unmarked(plain[done : marked.start()], pieces)
        maths = marked.group("paren") or marked.group("bracket") or marked.group("dollar")
        pieces.append(("maths", maths))
        done = marked.end()
    _unmarked(plain[done:], pieces)
    return _joined(pieces)
