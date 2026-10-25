"""A sentence that tells the user about the prompt's own parts comes off a reply.

An investing answer opened: "The memory block contains details that don't match this
conversation. It names a different person and preferences that conflict with what
you've told me, so I'm setting it aside and answering from what you've shared, Dev."
(live chat, 2026-10-25). The prompt asks for no such line (``PRIVACY_HINT``, the saved
memory preamble); this pass removes the ones a model writes anyway.

It is deliberately narrow. A sentence goes only when it names an internal part from a
closed list: a label only Recall's prompt uses ("[Chemistry note]", "saved memory
block", "BEGIN UNTRUSTED CONTENT"), or a word that also has an everyday meaning
("memory block" in C, "system prompt" in prompt writing) together with words about
this user or conversation ("this conversation", "what you've told me", "on file").
The sentence after it goes too when it points back ("It names a different person…").
Never inside a code fence, an inline code span, a table or a heading, never the whole
reply, and never on a turn whose message names one of these parts itself.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from app.services.md_fence_scan import line_fences
from app.services.text_normalize import straighten_apostrophes

if TYPE_CHECKING:
    from app.modules.chat.finalize_passes import FinalizeState

# Labels and wrappers only Recall's prompt writes.
_PROMPT_LABEL = re.compile(
    r"\[(?:chemistry|physics|math) (?:note|context)\]|\bsaved[- ]memory block\b"
    r"|\bknown[- ]facts block\b|\b(?:begin|end) (?:untrusted content|verified (?:math|physics))\b",
    re.IGNORECASE,
)
# Names with an everyday meaning too: internal only beside words about this user.
_PROMPT_PART = re.compile(
    r"\b(?:memory|profile) block\b|\bsystem (?:prompt|message)\b", re.IGNORECASE
)
_ABOUT_THIS_USER = re.compile(
    r"\b(?:this|our) (?:conversation|chat)\b|\bwhat you(?:'ve| have)? (?:told|shared with) me\b"
    r"|\byou(?:'ve| have) told me\b|\bon file\b|\byour name\b|\babout you\b"
    r"|\b(?:a )?different person\b|\bset(?:ting)? (?:it|that|this|them) aside\b",
    re.IGNORECASE,
)
# A sentence that goes on about the one before it.
_POINTS_BACK = re.compile(r"(?:it|this|that|they|these|those)\b", re.IGNORECASE)
# The user asked about prompts or these parts: the reply may name them.
_ASKED_ABOUT = re.compile(
    r"\bprompts?\b|\bmemory block|\bsystem message|\bknown[- ]facts|\bchemistry note"
    r"|\buntrusted content",
    re.IGNORECASE,
)
_INLINE_CODE = re.compile(r"`[^`\n]*`")
_SENTENCE_BREAK = re.compile(r"(?<=[.!?…]) +")
# A line's list marker or quote marker, kept when its sentences change.
_LEAD = re.compile(r"[ \t]*(?:>[ \t]*)*(?:(?:[-*+]|\d{1,3}[.)])[ \t]+)?")
_SKIPPED_STARTS = ("|", "#", "    ", "\t")


def drop_prompt_leaks_pass(state: FinalizeState) -> str:
    """The finalize pass: a model reply loses sentences about the prompt's parts."""
    if state.server_text:
        return state.text
    return drop_prompt_leaks(state.text, state.ctx.user_message_content)


def drop_prompt_leaks(text: str, query: str | None = None) -> str:
    """``text`` without sentences that name the prompt's internal parts, or unchanged."""
    if not text or not (_PROMPT_LABEL.search(text) or _PROMPT_PART.search(text)):
        return text
    if query and _ASKED_ABOUT.search(straighten_apostrophes(query)):
        return text
    lines = text.split("\n")
    owners = line_fences(text)
    out: list[str] = []
    dropped_line = False
    for index, line in enumerate(lines):
        kept = line if owners[index] is not None else _without_leaks(line)
        if kept is None:
            dropped_line = True
            continue
        # A paragraph that went entirely leaves one blank line, not two.
        if dropped_line and not kept.strip() and (not out or not out[-1].strip()):
            continue
        dropped_line = False
        out.append(kept)
    result = "\n".join(out)
    return result if result.strip() else text


def _without_leaks(line: str) -> str | None:
    """The line without its leaking sentences; None when none of it is left."""
    if line.startswith(_SKIPPED_STARTS) or line.lstrip().startswith(("|", "#")):
        return line
    lead_match = _LEAD.match(line)
    lead = lead_match.group(0) if lead_match else ""
    body = line[len(lead) :]
    sentences = _SENTENCE_BREAK.split(body)
    kept: list[str] = []
    after_leak = False
    for sentence in sentences:
        prose = straighten_apostrophes(_INLINE_CODE.sub(" ", sentence))
        if _leaks(prose) or (after_leak and _points_back(prose)):
            after_leak = True
            continue
        after_leak = False
        kept.append(sentence)
    if len(kept) == len(sentences):
        return line
    if not kept:
        return None
    return lead + " ".join(kept)


def _leaks(prose: str) -> bool:
    if _PROMPT_LABEL.search(prose):
        return True
    return bool(_PROMPT_PART.search(prose) and _ABOUT_THIS_USER.search(prose))


def _points_back(prose: str) -> bool:
    return bool(_POINTS_BACK.match(prose.lstrip("*_ ")) and _ABOUT_THIS_USER.search(prose))
