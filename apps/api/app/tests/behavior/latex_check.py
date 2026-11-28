"""LaTeX in a finished reply that the phone would show as source.

``docs/fixtures/latex_commands.json`` lists every command the phone draws: inline
maths by its native renderer, display maths by MathJax. The phone's
``lib/math/__tests__/latexCoverage.test.ts`` writes the file and renders every
entry both ways. A reply may use only those commands, and only inside maths
(``$...$``, ``$$...$$``, ``\\(...\\)``, ``\\[...\\]``, or a ``math`` or
``answer`` fence): TeX in prose reaches the screen as written. Other fences hold
code or a picture's JSON, not TeX a reader sees. A word group's own text
(``\\text{…}``, ``\\mathrm{…}``) is drawn as written too: only a script (``_``,
``^``) or a command opens a brace there, so a brace after an escaped underscore
(``\\text{white\\_{pigment}}``, 2026-11-12) is source on screen. So is a dollar the phone
pairs with no other: "$9: 12: 15 $ is the $ 3: 4: 5$" read its first dollar as a price's and
showed the last one, the words between set as maths (2026-11-13). Dollars are paired here as
the phone pairs them (``chat.math_padding.maths_pair_end``); a price's ("$5") stays a sign.
TeX itself refuses a group left open and a second script on one base (``v_A_{vec}``,
2026-11-20), so maths holds neither (``chat.tex_form``). Nor does it hold a sum of money in
a bold or word group (``$M \\approx \\textbf{\\$773}$``, 2026-11-22: ``chat.maths_money``).
"""

from __future__ import annotations

import json
import re
from functools import cache
from pathlib import Path

from app.modules.chat.display_dollars import display_dollar_pair_end
from app.modules.chat.inline_code import escaped_at
from app.modules.chat.markdown_regions import PRICE_TIER
from app.modules.chat.math_padding import maths_pair_end
from app.modules.chat.maths_money import MONEY_GROUP
from app.modules.chat.tex_form import well_formed

FIXTURE = Path(__file__).resolve().parents[5] / "docs" / "fixtures" / "latex_commands.json"

_FENCE = re.compile(r"^(`{3,}|~{3,})([^\n]*)\n(.*?)^\1[ \t]*$", re.DOTALL | re.MULTILINE)
_MATH_FENCES = {"math", "latex", "tex", "answer"}
# Inline maths may hold an escaped dollar (``$C = \\$0.90$``): the phone reads it as the sign.
# Display dollars are read first, as every reader reads them (``chat.display_dollars``).
_SPAN = re.compile(
    r"\\\((.+?)\\\)|\\\[(.+?)\\\]"
    r"|(?<![\\$])\$(?!\$)((?:\\\$|[^$\n])+?)(?<!\\)\$",
    re.DOTALL,
)
_INLINE_CODE = re.compile(r"`[^`\n]*`")
_FORMULA_CHAR = re.compile(r"[^\W_]|[\\\u221e]")
_TEX_IN_PROSE = re.compile(r"\\[A-Za-z]+|[\^_]\{")
_COMMAND = re.compile(r"\\([A-Za-z]+)")
_WORD_GROUP = re.compile(r"\\(?:text|textrm|mathrm|mbox|operatorname)\s*\{")
# What may open a brace inside a word group: an unescaped script mark, or a command.
_OPENS_A_GROUP = re.compile(r"(?:(?<!\\)[_^]|\\[A-Za-z]+)\s*$")
# Display maths and bracketed inline maths, which the phone pairs before any lone dollar.
_DISPLAY = re.compile(r"\\\(.+?\\\)|\\\[.+?\\\]", re.DOTALL)
# A dollar shaped as a formula's closer, after its last digit, letter or bracket and before
# a space or a mark ("3: 4: 5$ ratio"). A price's ("$5", "US$5"), a sign named in words
# ("the $ sign"), a variable ("$HOME", "$Z") and "($M)" are none.
_CLOSER = re.compile(r"(?<=[0-9a-z)}\]])\$(?=[\s.,;:!?)\]]|$)")


def _group_text(body: str, opening: int) -> str:
    """The text of the brace group opened at ``opening``, without its braces."""
    depth = 0
    for at in range(opening, len(body)):
        if body[at] == "{" and body[at - 1] != "\\":
            depth += 1
        elif body[at] == "}" and body[at - 1] != "\\":
            depth -= 1
            if depth == 0:
                return body[opening + 1 : at]
    return body[opening + 1 :]


def _braces_in_words(body: str) -> list[str]:
    """Each word group in ``body`` whose text holds a brace the phone would draw."""
    found: list[str] = []
    for group in _WORD_GROUP.finditer(body):
        text = _group_text(body, group.end() - 1)
        for at, char in enumerate(text):
            escaped = at > 0 and text[at - 1] == "\\" and not text[:at].endswith("\\\\")
            if char == "{" and not escaped and not _OPENS_A_GROUP.search(text[:at]):
                found.append(f"a brace in a word group: {group.group(0)}{text}}}")
                break
    return found


@cache
def drawn_commands() -> frozenset[str]:
    """Every command name the phone draws."""
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    return frozenset([*data["symbols"], *data["operators"], *data["commands"]])


def _prose_parts(reply: str) -> list[str]:
    """The reply outside its fences."""
    parts: list[str] = []
    last = 0
    for fence in _FENCE.finditer(reply):
        parts.append(reply[last : fence.start()])
        last = fence.end()
    return [*parts, reply[last:]]


def _maths_and_prose(reply: str) -> tuple[list[str], list[str]]:
    maths: list[str] = []
    prose: list[str] = []
    last = 0
    for fence in _FENCE.finditer(reply):
        prose.append(reply[last : fence.start()])
        last = fence.end()
        if fence.group(2).strip().lower() in _MATH_FENCES:
            maths.append(fence.group(3))
    prose.append(reply[last:])

    def take(span: re.Match[str]) -> str:
        body = next(group for group in span.groups() if group is not None)
        # A price range's first tier ("$-$$"): no formula (math_padding._opens_price_range).
        after = span.string[span.end() : span.end() + 1]
        if span.group(0).startswith("$") and after == "$" and _FORMULA_CHAR.search(body) is None:
            return span.group(0)
        maths.append(body)
        return " "

    return maths, [
        _SPAN.sub(take, _without_display_dollars(_INLINE_CODE.sub("", part), maths))
        for part in prose
    ]


def _without_display_dollars(prose: str, maths: list[str] | None = None) -> str:
    """``prose`` with each ``$$`` formula blanked; its text goes to ``maths``."""
    out: list[str] = []
    last = 0
    start = prose.find("$$")
    while start >= 0:
        end = display_dollar_pair_end(prose, start)
        if end is None:
            while start < len(prose) and prose[start] == "$":
                start += 1
            start = prose.find("$$", start)
            continue
        out.append(prose[last:start])
        if maths is not None:
            maths.append(prose[start + 2 : end - 2])
        out.append(" ")
        last = end
        start = prose.find("$$", end)
    return "".join([*out, prose[last:]])


def _shown_dollars(prose: str) -> list[str]:
    """Each ``$`` of ``prose`` the phone pairs with no other that closes a formula."""
    found: list[str] = []
    # Code, a restaurant's price tier ("($$)") and display maths hold no lone dollar.
    plain = PRICE_TIER.sub(" ", _INLINE_CODE.sub(" ", prose))
    for line in _DISPLAY.sub(" ", _without_display_dollars(plain)).split("\n"):
        index = 0
        while index < len(line):
            if line[index] != "$":
                index += 1
                continue
            if line.startswith("$$", index):
                # A price tier ("$$", "$$$") left once display maths is read: no lone dollar.
                while index < len(line) and line[index] == "$":
                    index += 1
                continue
            end = maths_pair_end(line, index)
            if end is not None:
                index = end
                continue
            if not escaped_at(line, index) and _CLOSER.match(line, index) is not None:
                found.append(f"a dollar shown as source: {line[max(0, index - 20) : index + 20]}")
            index += 1
    return found


def latex_problems(reply: str) -> list[str]:
    """Each command the phone cannot draw, and each piece of TeX outside maths."""
    maths, prose = _maths_and_prose(reply)
    drawn = drawn_commands()
    problems = [
        f"the phone draws no \\{name}"
        for body in maths
        for name in _COMMAND.findall(body)
        if name not in drawn
    ]
    problems += [problem for body in maths for problem in _braces_in_words(body)]
    # A sum of money in a bold or word group: its escaped dollar ended the formula on the
    # phone ("M ≈ {\\773}$", 2026-11-22); finalize takes it out (``chat.maths_money``).
    problems += [
        f"a sum of money in a group: {group.group(0)}"
        for body in maths
        for group in MONEY_GROUP.finditer(body)
    ]
    # A group left open or a second script on one base: TeX refuses it, so it reads as source.
    problems += [
        f"TeX the renderer refuses: {body.strip()[:80]}"
        for body in maths
        if well_formed(body) != body
    ]
    problems += [
        f"TeX outside maths: {tex}" for part in prose for tex in _TEX_IN_PROSE.findall(part)
    ]
    problems += [problem for part in _prose_parts(reply) for problem in _shown_dollars(part)]
    return problems
