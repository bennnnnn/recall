"""The answer-card protocol: which ```answer fence the server vouches for.

The phone draws the green check on an ```answer fence only when the fence body
opens with ``verified: true`` (the same header-line style as
``notation: chemistry``). Only the server writes that line, and only on a card
whose value came from a solver: the post-stream fence pass appends it to the
cards it writes, and an instant reply (wholly server text) gets it on every
card. Model text never keeps it:

1. ``strip_forged_verified_markers`` removes the line from the model's reply
   before any server card is added, so the model cannot forge a check.
2. ``normalize_owned_fences`` rewrites every spelling of a model answer fence
   (indented in a list, ``~~~answer``, four backticks, ``` answer``, capital
   ``Answer``, ``result`` / ``final``) to the plain column-0 form, so each
   subject's fence pass sees and demotes all of them, not only ``\\n```answer``.
3. ``strip_verification_claims`` drops the model's own "✅ Verified with SymPy",
   and ``strip_model_simulation_fences`` its own ```simulation scene.

The server writes the line with ``verified_answer_fence`` (post-stream cards)
and ``mark_server_answer_fences`` (an instant reply, once, when it is sent).
The fence scan here is a linear line scan, no nested regex on untrusted text.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Callable
from dataclasses import dataclass

from app.services.md_fence_scan import map_closed_fences

VERIFIED_ANSWER_MARKER = "verified: true"
CHEMISTRY_NOTATION_LINE = "notation: chemistry"
# Header lines a client reads off the top of an answer body. The phone also
# writes ``label: answer`` itself when it moves an **Answer** heading inside.
ANSWER_HEADER_LINES = frozenset({VERIFIED_ANSWER_MARKER, CHEMISTRY_NOTATION_LINE, "label: answer"})
ANSWER_FENCE_LANGS = ("answer", "result", "final")
# Server-owned fences a model must not ship in any spelling.
OWNED_FENCE_LANGS = (*ANSWER_FENCE_LANGS, "simulation")
# Fences whose body a client may read as an answer card. A marker line inside
# any other fence (```yaml, ```python) is code the user asked for, so it stays.
_MARKER_SCRUB_LANGS = frozenset(
    {*ANSWER_FENCE_LANGS, "", "copy", "text", "plain", "clike", "math", "latex", "tex"}
)
_DIAGRAM_FAIL_NOTE = "*Could not render that diagram.*"


def answer_header_and_value(body: str) -> tuple[list[str], str]:
    """Split the protocol header lines off the top of an answer body."""
    lines = body.replace("\r\n", "\n").strip().split("\n")
    headers: list[str] = []
    while lines and lines[0].strip() in ANSWER_HEADER_LINES:
        headers.append(lines.pop(0).strip())
    return headers, "\n".join(lines).strip()


def answer_fence_value(body: str) -> str:
    """The value a reader sees: the body without its protocol header lines."""
    return answer_header_and_value(body)[1]


def verified_answer_body(body: str) -> str:
    """``body`` with the server's verified marker as its first line (idempotent)."""
    headers, value = answer_header_and_value(body)
    rest = [line for line in headers if line != VERIFIED_ANSWER_MARKER]
    return "\n".join([VERIFIED_ANSWER_MARKER, *rest, value]).strip()


def verified_answer_fence(body: str) -> str:
    """The one way the server writes a card it vouches for."""
    return f"```answer\n{verified_answer_body(body)}\n```"


# --- A lenient fence scan for model text -------------------------------------------------

_OPENER = re.compile(r"(?P<tick>`{3,}|~{3,})(?P<info>.*)")


@dataclass(frozen=True)
class _Fence:
    start: int  # line index of the opener
    end: int  # line index of the closer
    lang: str
    tick: str
    prefix: str  # indent and blockquote markers before the opener
    info: str


def _line_prefix(line: str) -> tuple[str, str]:
    """Leading indent and ``>`` quote markers, and the rest of the line."""
    index = 0
    while index < len(line) and line[index] in " \t>":
        index += 1
    return line[:index], line[index:]


def fence_lang(info: str) -> str:
    """The phone's ``parseFenceLang``: first word, cut at ``{ : [``, lower case."""
    words = info.strip().split()
    if not words:
        return ""
    return re.split(r"[{:\[]", words[0], maxsplit=1)[0].lower()


def _opener(line: str) -> tuple[str, str, str] | None:
    prefix, rest = _line_prefix(line)
    match = _OPENER.fullmatch(rest.rstrip("\r"))
    if match is None:
        return None
    tick, info = match.group("tick"), match.group("info")
    if tick[0] == "`" and "`" in info:
        return None  # ```inline``` code on one line, not a fence
    return prefix, tick, info


def _closes(line: str, tick: str) -> bool:
    _prefix, rest = _line_prefix(line)
    run = rest.strip()
    return len(run) >= len(tick) and run == tick[0] * len(run)


def _scan(lines: list[str]) -> tuple[list[_Fence], dict[int, str]]:
    """Closed fences, and for every line inside an open or closed fence its lang."""
    fences: list[_Fence] = []
    inside: dict[int, str] = {}
    index = 0
    while index < len(lines):
        opened = _opener(lines[index])
        if opened is None:
            index += 1
            continue
        prefix, tick, info = opened
        lang = fence_lang(info)
        cursor = index + 1
        while cursor < len(lines) and not _closes(lines[cursor], tick):
            inside[cursor] = lang
            cursor += 1
        if cursor >= len(lines):
            break  # unclosed: the rest of the reply is this fence's body
        fences.append(_Fence(index, cursor, lang, tick, prefix, info))
        index = cursor + 1
    return fences, inside


def _is_marker_line(line: str) -> bool:
    """``verified: true`` however it is dressed: any case, spacing, or invisible marks."""
    _prefix, rest = _line_prefix(line)
    compact = "".join(
        char
        for char in rest
        if not char.isspace() and unicodedata.category(char) not in {"Cf", "Cc", "Zs"}
    )
    return compact.lower() == "verified:true"


def strip_forged_verified_markers(text: str) -> str:
    """Drop every ``verified: true`` line a model wrote where a client could read it."""
    if "verified" not in text.lower():
        return text
    lines = text.split("\n")
    _fences, inside = _scan(lines)
    kept = [
        line
        for number, line in enumerate(lines)
        if not (_is_marker_line(line) and inside.get(number, "") in _MARKER_SCRUB_LANGS)
    ]
    return "\n".join(kept)


def _dedent(line: str, prefix: str) -> str:
    if line.startswith(prefix):
        return line[len(prefix) :]
    head, rest = _line_prefix(line)
    return rest if len(head) <= len(prefix) else line[len(prefix) :]


def normalize_owned_fences(text: str, langs: tuple[str, ...] = OWNED_FENCE_LANGS) -> str:
    """Rewrite each closed server-owned fence to a column-0 ```lang block.

    The subject fence passes match ``\\n```answer`` exactly. A model that
    indents its answer fence in a list, or writes ``~~~answer`` or four
    backticks, gets the same card on the phone, so it must get the same
    demotion here.
    """
    lower = text.lower()
    if not any(lang in lower for lang in langs):
        return text
    lines = text.split("\n")
    fences, _inside = _scan(lines)
    out: list[str] = []
    cursor = 0
    for fence in fences:
        if fence.lang not in langs:
            continue
        canonical = fence.prefix == "" and fence.tick == "```" and fence.info == fence.lang
        if canonical:
            continue
        out.extend(lines[cursor : fence.start])
        if out and out[-1].strip():
            out.append("")  # a column-0 fence after a list line starts its own block
        out.append(f"```{fence.lang}")
        out.extend(_dedent(line, fence.prefix) for line in lines[fence.start + 1 : fence.end])
        out.append("```")
        if fence.end + 1 < len(lines) and lines[fence.end + 1].strip():
            out.append("")
        cursor = fence.end + 1
    if cursor == 0:
        return text
    out.extend(lines[cursor:])
    return "\n".join(out)


def mark_server_answer_fences(text: str) -> str:
    """Add the verified marker to every answer card in wholly server-written text."""
    ended_open = not text.endswith("\n")
    for lang in ANSWER_FENCE_LANGS:
        # The scan consumes the closer's newline, so the replacement restores it.
        text = map_closed_fences(text, lang, lambda body: verified_answer_fence(body) + "\n")
    return text.rstrip("\n") if ended_open else text


def demote_answer_body(body: str) -> str:
    """A model answer fence as plain prose: its value, never its header lines.

    One line of TeX (``x = 2 \\text{ or } x = 3``) is wrapped in ``$...$`` so
    it reads as math, not as backslashes; chemistry text stays as written.
    """
    headers, value = answer_header_and_value(body)
    if not value:
        return ""
    tex = CHEMISTRY_NOTATION_LINE not in headers and "\n" not in value
    if tex and "$" not in value and any(mark in value for mark in ("\\", "^", "_", "{")):
        value = f"${value}$"
    return f"{value}\n"


def demote_answer_fences(text: str) -> str:
    """Unwrap every answer fence to prose. No solver, so safe after a timeout."""
    text = normalize_owned_fences(text, ANSWER_FENCE_LANGS)
    for lang in ANSWER_FENCE_LANGS:
        text = map_closed_fences(text, lang, demote_answer_body)
    return text


def strip_model_simulation_fences(text: str) -> str:
    """A ```simulation scene is solver-sampled. The model's own never ships."""
    if "simulation" not in text.lower():
        return text
    normalized = normalize_owned_fences(text, ("simulation",))
    stripped = map_closed_fences(normalized, "simulation", lambda _body: "")
    if stripped == normalized:
        return text
    cleaned = re.sub(r"\n{3,}", "\n\n", stripped).strip()
    return cleaned or _DIAGRAM_FAIL_NOTE


def map_outside_fences(text: str, transform: Callable[[str], str]) -> str:
    """Apply ``transform`` to each run of lines outside any fence."""
    lines = text.split("\n")
    fences, inside = _scan(lines)
    fenced = set(inside)
    for fence in fences:
        fenced.update((fence.start, fence.end))
    if not fenced:
        return transform(text)
    # An unclosed fence's opener line is fenced too.
    for number in inside:
        opener = number - 1
        while opener >= 0 and opener in inside:
            opener -= 1
        if opener >= 0:
            fenced.add(opener)
    out: list[str] = []
    run: list[str] = []
    for number, line in enumerate(lines):
        if number in fenced:
            if run:
                out.append(transform("\n".join(run)))
                run = []
            out.append(line)
        else:
            run.append(line)
    if run:
        out.append(transform("\n".join(run)))
    return "\n".join(out)


# --- Claims of verification the server did not make -------------------------------------

_CHECK_MARKS = "✅✔☑✓"  # ✅ ✔ ☑ ✓
_CLAIM_VERB = r"(?:verified|checked|confirmed|double[- ]checked)"
_CHECKER = (
    r"(?:sympy|sym\s*py|the\s+(?:symbolic\s+)?solver|a\s+(?:symbolic\s+)?solver|"
    r"the\s+(?:symbolic\s+|math\s+)+engine|a\s+(?:symbolic\s+)?(?:math\s+)?engine|"
    r"symbolic\s+(?:math|algebra)|a\s+computer\s+algebra\s+system|a\s+cas|"
    r"the\s+cas|the\s+server|the\s+app)"
)
# ✅ Verified with SymPy. / ✓ Checked
_EMOJI_CLAIM = re.compile(
    rf"[ \t]*[{_CHECK_MARKS}]️?[ \t]*(?:\*\*|__|\*|_)?[ \t]*{_CLAIM_VERB}\b"
    rf"(?:[ \t]+(?:with|by|using|via|in)[ \t]+(?:{_CHECKER}|[A-Za-z][\w.-]*))?"
    r"[ \t]*(?:\*\*|__|\*|_)?[ \t]*[.!]?(?:\*\*|__|\*|_)?",
    re.IGNORECASE,
)
# (verified) / (verified with SymPy) / [checked]
_PAREN_CLAIM = re.compile(
    rf"[ \t]*[(\[][ \t]*[{_CHECK_MARKS}]?️?[ \t]*{_CLAIM_VERB}"
    r"(?:[ \t]+(?:with|by|using|via|in)[ \t]+[^)\]\n]{1,40})?[ \t]*[)\]]",
    re.IGNORECASE,
)
# A sentence that says a solver checked the result: "This was verified by the solver."
_SENTENCE_CLAIM = re.compile(
    rf"(?:(?<=^)|(?<=[.!?\n])[ \t]*)[^.!?\n]*\b{_CLAIM_VERB}[ \t]+(?:with|by|using|via|in)[ \t]+"
    rf"{_CHECKER}\b[^.!?\n]*[.!]?",
    re.IGNORECASE,
)
# A "Verified answer:" / "**Verified result:**" label opening a line keeps its job
# as a label and loses the claim. Mid-sentence wording is left alone.
_LABEL_CLAIM = re.compile(
    r"^(?P<lead>[ \t>]*(?:\*\*|__)?[ \t]*)verified[ \t]+(?P<noun>answer|result|solution)"
    r"(?=[ \t]*(?:\*\*|__)?[ \t]*:)",
    re.IGNORECASE | re.MULTILINE,
)


def _claimless(prose: str) -> str:
    out = _EMOJI_CLAIM.sub("", prose)
    out = _PAREN_CLAIM.sub("", out)
    out = _SENTENCE_CLAIM.sub("", out)
    out = _LABEL_CLAIM.sub(
        lambda match: f"{match.group('lead') or ''}{match.group('noun').capitalize()}", out
    )
    out = re.sub(r"[ \t]+\n", "\n", out)
    return re.sub(r"\n{3,}", "\n\n", out)


def strip_verification_claims(text: str) -> str:
    """Remove the model's own "verified" claims from prose (fences untouched).

    Only for a turn the server did not verify: there the check mark is absent
    by design, and text that says otherwise would fake it.
    """
    lower = text.lower()
    if not any(word in lower for word in ("verif", "checked", "confirmed")):
        return text
    return map_outside_fences(text, _claimless).strip()
