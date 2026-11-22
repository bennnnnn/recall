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
this user's chat with Recall ("this conversation", "what you've told me", "your … on
file"; not a bare "your name" or "about you", which an answer about a CMS or an LLM
uses). The sentence after it goes too when it points back ("It names a different
person…"). Never inside a code fence, an inline code span, a table, a heading or a
quote, never the whole reply, and never on a turn whose recent messages name these
parts or prompt writing, or whose message asks about language models or Recall's memory.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Set as AbstractSet
from functools import cache
from typing import TYPE_CHECKING, Any

from app.modules.chat.narration import without_narration
from app.modules.chat.prompt_rule_text import prompt_rule_text
from app.services.md_fence_scan import line_fences, map_fence_blocks
from app.services.text_normalize import straighten_apostrophes

if TYPE_CHECKING:
    from app.modules.chat.finalize_passes import FinalizeState

logger = logging.getLogger(__name__)

# Labels and wrappers only Recall's prompt writes.
_PROMPT_LABEL = re.compile(
    r"\[(?:chemistry|physics|math) (?:note|context)\]|\bsaved[- ]memory block\b"
    r"|\bknown[- ]facts block\b|\b(?:begin|end) (?:untrusted content|verified (?:math|physics))\b"
    # "No verified block is present": "each verified block is added to the chain" is bitcoin.
    r"|\bverified (?:math|physics|chemistry) block\b|\bno verified block\b"
    r"|\bverified block (?:is|was) (?:present|given|shown|provided|attached)\b",
    re.IGNORECASE,
)
# An instruction copied from the prompt's rules: "Do not describe the work as math,
# algebra, or solving equations." opened a Class 8 speed answer (2026-10-30). Read only
# against the fixed rules (``prompt_rule_text``), never a turn's memory, to-dos or
# documents, and only in an instruction's shape.
_INSTRUCTION = re.compile(
    r"(?:do not|don't|never|always|when|if no|use|copy|put|give|state)\b", re.IGNORECASE
)
_WORDS = re.compile(r"[a-z0-9']+")
# Names with an everyday meaning too: internal only beside words about this user.
_PROMPT_PART = re.compile(
    r"\b(?:memory|profile) block\b|\bsystem (?:prompt|message)\b", re.IGNORECASE
)
_ABOUT_THIS_USER = re.compile(
    r"\b(?:this|our) (?:conversation|chat)\b|\bwhat you(?:'ve| have)? (?:told|shared with) me\b"
    r"|\byou(?:'ve| have) told me\b|\byour? \w+(?: \w+)? on file\b"
    r"|\b(?:a )?different person\b|\bset(?:ting)? (?:it|that|this|them) aside\b",
    re.IGNORECASE,
)
# The reply on its own presentation rules, which only the prompt set: "This is a
# school-style physics problem, so I'll walk through the reasoning without emoji." (live,
# 2026-11-03, a scanned equilibrium problem). Emoji are a style rule of the prompt's; a
# reply that says it uses or skips them is telling the user about its instructions.
_STYLE_RULE = re.compile(
    r"\bemoji-free\b"
    r"|\b(?:without|no|skip(?:ping)?|avoid(?:ing)?|leave out|leaving out|drop(?:ping)?|"
    r"add(?:ing)?|us(?:e|ing)|includ(?:e|ing)|sprinkl(?:e|ing))\s+(?:the\s+|any\s+|a few\s+|some\s+)?"
    r"emojis?\b",
    re.IGNORECASE,
)
_FIRST_PERSON = re.compile(r"\b(?:i'll|i will|i'm|i am|i've|let me|we'll)\b", re.IGNORECASE)
_ASKED_ABOUT_STYLE = re.compile(r"\bemoji|[\U0001F300-\U0001FAFF]", re.IGNORECASE)
# An opening that labels the message and announces the plan, whatever the plan is: "This
# is a current-events question, so I'll check …", "This is a school-style physics
# problem, so I'll walk through …". The answer that follows is the plan carried out.
_SELF_LABEL = re.compile(
    r"(?:this|that|it)(?:'s| is| looks like| sounds like| seems like) (?:a|an) [^.!?\n]{0,80}?"
    r"\b(?:question|problem|request|task|query|topic|one)\b[^.!?\n]{0,80}?"
    r"(?:,|\bso|\band)\s+(?:i(?:'ll| will| am going to|'m going to)|let me|we(?:'ll| will))\b"
    # To the sentence's end, past a decimal point; a colon starts the answer itself.
    r"[^:!?\n]*?[.!](?=\s|$)",
    re.IGNORECASE,
)
# A sentence that goes on about the one before it.
_POINTS_BACK = re.compile(r"(?:it|this|that|they|these|those)\b", re.IGNORECASE)
# The user's latest messages name these parts or ask about prompt writing.
_ASKED_ABOUT_PARTS = re.compile(
    r"\bmemory block|\bsystem (?:message|prompt)|\bknown[- ]facts|\bchemistry note"
    r"|\buntrusted content|\bprompt (?:engineering|injection|templates?)\b"
    r"|\b(?:user|good|better|my) prompts?\b|\bprompts? (?:for|to) (?:chatgpt|gpts?|an? (?:ai|llm))"
    r"|\bverified block",
    re.IGNORECASE,
)
# This message asks about language models or about what Recall remembers. Only this
# one: "I asked ChatGPT earlier" two messages back says nothing about this reply.
_ASKED_ABOUT_MODELS = re.compile(
    r"\bllms?\b|\bgpts?\b|\bchatgpt\b|\bchat ?bots?\b|\blanguage models?\b"
    r"|\bai (?:agents?|assistants?|models?)\b|\byour memory\b|\byou remember\b"
    r"|\b(?:know|remember) about me\b",
    re.IGNORECASE,
)
# How many of the user's latest messages say what the chat is about.
_RECENT_USER_MESSAGES = 4
_INLINE_CODE = re.compile(r"`[^`\n]*`")
_SENTENCE_BREAK = re.compile(r"(?<=[.!?…]) +")
# A line's list marker, kept when its sentences change.
_LEAD = re.compile(r"[ \t]*(?:(?:[-*+]|\d{1,3}[.)])[ \t]+)?")
_SKIPPED_STARTS = ("|", "#", ">", "    ", "\t")


def drop_prompt_leaks_pass(state: FinalizeState) -> str:
    """The finalize pass: a model reply loses sentences about the prompt's parts."""
    if state.server_text:
        return state.text
    return drop_prompt_leaks(state.text, *_recent_user_lines(state), rules=_rule_grams())


def drop_prompt_lines(text: str) -> str:
    """What stands in when the pass fails: every line with a sentence that names a part
    of the prompt or copies one of its rules goes, in code and quotes too."""
    try:
        rules: AbstractSet[str] = _rule_grams()
    except Exception:
        logger.exception("prompt rules unreadable; dropping only lines that name its parts")
        rules = frozenset()
    return "\n".join(line for line in text.split("\n") if not _leaking_line(line, rules))


def _leaking_line(line: str, rules: AbstractSet[str]) -> bool:
    if quotes_the_prompt(line):
        return True
    lead = _LEAD.match(line.lstrip(" \t>#|"))
    body = line.lstrip(" \t>#|")[lead.end() if lead else 0 :]
    for sentence in _SENTENCE_BREAK.split(body):
        prose = straighten_apostrophes(_INLINE_CODE.sub(" ", sentence))
        if _leaks(prose) or (rules and _copies(prose, rules)):
            return True
    return False


@cache
def _rule_grams() -> frozenset[str]:
    return frozenset(_grams(prompt_rule_text(), 4))


def _recent_user_lines(state: FinalizeState) -> list[str]:
    return _asked_lines(state.ctx)


def _asked_lines(ctx: Any) -> list[str]:
    """The message and the user's messages just before it."""
    earlier = [
        content
        for message in getattr(ctx, "prompt_messages", None) or []
        if message.get("role") == "user" and isinstance(content := message.get("content"), str)
    ]
    return [getattr(ctx, "user_message_content", None) or "", *earlier[-_RECENT_USER_MESSAGES:]]


# A quotation: between its marks, or from an opening mark to the line's end (a cut-off reply
# never closed it). A short quotation takes both its marks, so its closing one never opens
# the next (review, #2536).
_QUOTED = re.compile(
    r"\"([^\"\n]*)\"|\u201c([^\u201d\n]*)\u201d|[\"\u201c]([^\"\u201d\n]*)$", re.MULTILINE
)
_QUOTE_WORDS = re.compile(r"[a-z']+")
# A model may open a quotation curly and close it straight: every mark is read as one.
_STRAIGHT_QUOTES = str.maketrans({"\u201c": '"', "\u201d": '"'})
# Words in a row a quotation shares with the rules: on 9,487 live replies, none quoted six
# of the rules' words in a row but the two that sent the model's notes as the reply.
_QUOTE_RUN = 6
_SPANS_NOT_PROSE = re.compile(r"`[^`\n]*`|\$[^$\n]*\$")


@cache
def _rule_runs() -> frozenset[str]:
    words = _QUOTE_WORDS.findall(prompt_rule_text().lower())
    return frozenset(
        " ".join(words[at : at + _QUOTE_RUN]) for at in range(len(words) - _QUOTE_RUN + 1)
    )


def quotes_the_prompt(text: str) -> bool:
    """``text`` quotes Recall's own rules: a quotation in its prose (never in code or maths)
    that runs six of the rules' words in a row. A reply that says them as its own words
    follows them (an example reply the rules give, the quadratic formula); one that quotes
    them is the model reasoning about its instructions, sent as the answer ('The system
    instructions say: "Worked calculation: this question asks for a value …"', live,
    2026-11-22, the reply opening on a wrong 42,000)."""
    prose = _SPANS_NOT_PROSE.sub(" ", map_fence_blocks(text, lambda _fence, _body: "\n"))
    # A curly apostrophe is the rules' straight one: user's stays one word (review, #2536).
    prose = straighten_apostrophes(prose).translate(_STRAIGHT_QUOTES)
    runs = _rule_runs()
    for quote in _QUOTED.finditer(prose):
        said = next(group for group in quote.groups() if group is not None)
        words = _QUOTE_WORDS.findall(said.lower())
        if any(
            " ".join(words[at : at + _QUOTE_RUN]) in runs
            for at in range(len(words) - _QUOTE_RUN + 1)
        ):
            return True
    return False


def reply_quotes_the_prompt(reply: str, ctx: Any) -> bool:
    """A reply that quotes the prompt's rules, on a turn that never asked about them."""
    return quotes_the_prompt(reply) and not _asked_about(tuple(_asked_lines(ctx)))


def _grams(text: str, size: int) -> set[str]:
    words = _WORDS.findall(text.lower())
    return {" ".join(words[at : at + size]) for at in range(len(words) - size + 1)}


def drop_prompt_leaks(
    text: str,
    *asked: str | None,
    instructions: str = "",
    rules: frozenset[str] | None = None,
) -> str:
    """``text`` without sentences that name the prompt's internal parts or copy one of
    its ``instructions``, or unchanged.

    ``asked`` is what the user wrote this turn, then just before it.
    """
    prompt: AbstractSet[str] = rules if rules is not None else _grams(instructions, 4)
    # A leak copies a run of rules; one sentence that matches is advice the reply gives
    # ("Never open with a rhetorical hook." in tips on blog intros, review 2026-10-30).
    if _copied_count(text, prompt) < 2:
        prompt = frozenset()
    style = _STYLE_RULE.search(text) is not None and not any(
        line and _ASKED_ABOUT_STYLE.search(line) for line in asked
    )
    text = _without_self_label(text)
    quoted = quotes_the_prompt(text)
    if not text or not (
        _PROMPT_LABEL.search(text) or _PROMPT_PART.search(text) or prompt or style or quoted
    ):
        return text
    if _asked_about(asked):
        return text
    lines = text.split("\n")
    owners = line_fences(text)
    out: list[str] = []
    dropped_line = False
    for index, line in enumerate(lines):
        kept = line if owners[index] is not None else _without_leaks(line, prompt)
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


def _without_self_label(text: str) -> str:
    """``text`` without an opening sentence that labels the message and announces the plan;
    as it was when that sentence is the whole reply."""
    stripped = text.lstrip()
    if stripped.startswith(_SKIPPED_STARTS) or stripped.startswith(("```", "~~~")):
        return text
    # Planning about the person or memory, to nobody (``narration``).
    spoken = without_narration(stripped)
    if spoken != stripped:
        return spoken
    label = _SELF_LABEL.match(straighten_apostrophes(stripped))
    if label is None:
        return text
    rest = stripped[label.end() :].lstrip(" \t")
    # What follows must start a sentence: a stop inside one ("e.g. one per mass", "Fig. 2")
    # would leave a fragment, so the reply stays as written.
    if rest and not (rest[0] == "\n" or rest[0].isupper() or rest[0] in "*_#>[`$(\"'-|"):
        return text
    rest = rest[1:].lstrip("\n") if rest.startswith("\n") else rest
    return rest if rest.strip() else text


def _asked_about(asked: tuple[str | None, ...]) -> bool:
    """The user asked about these parts lately, or about models or memory just now."""
    lines = [straighten_apostrophes(line) for line in asked if line]
    if any(_ASKED_ABOUT_PARTS.search(line) for line in lines):
        return True
    return bool(asked and asked[0] and _ASKED_ABOUT_MODELS.search(lines[0]))


def _copies(sentence: str, prompt: AbstractSet[str]) -> bool:
    """An instruction of six words or more, half its four-word runs the prompt's own."""
    grams = _grams(sentence, 4)
    return (
        len(grams) >= 3
        and _INSTRUCTION.match(sentence.lstrip("*_ -")) is not None
        and len(grams & prompt) * 2 >= len(grams)
    )


def _copied_count(text: str, prompt: AbstractSet[str]) -> int:
    if not prompt:
        return 0
    sentences = _SENTENCE_BREAK.split(text.replace("\n", " "))
    return sum(_copies(sentence, prompt) for sentence in sentences)


def _without_leaks(line: str, prompt: AbstractSet[str] | None = None) -> str | None:
    """The line without its leaking sentences; None when none of it is left."""
    if line.startswith(_SKIPPED_STARTS) or line.lstrip().startswith(("|", "#", ">")):
        return line
    if quotes_the_prompt(line):
        # A quotation of the rules runs across its sentences: split, no piece of it may read
        # as one, so the line goes whole (review, #2536).
        return None
    lead_match = _LEAD.match(line)
    lead = lead_match.group(0) if lead_match else ""
    body = line[len(lead) :]
    sentences = _SENTENCE_BREAK.split(body)
    kept: list[str] = []
    after_leak = False
    copied = 0
    for sentence in sentences:
        prose = straighten_apostrophes(_INLINE_CODE.sub(" ", sentence))
        copy = bool(prompt) and _copies(prose, prompt or frozenset())
        copied += copy
        if _leaks(prose) or copy or (after_leak and _points_back(prose)):
            after_leak = True
            continue
        after_leak = False
        kept.append(sentence)
    if len(kept) == len(sentences):
        return line
    # A paragraph mostly copied from the prompt: its short pieces ("Do not recompute.")
    # are the prompt's too.
    if not kept or (copied >= 2 and copied * 2 >= len(sentences)):
        return None
    return lead + " ".join(kept)


def _leaks(prose: str) -> bool:
    if _PROMPT_LABEL.search(prose) or quotes_the_prompt(prose):
        return True
    if _STYLE_RULE.search(prose) and _FIRST_PERSON.search(prose):
        return True
    return bool(_PROMPT_PART.search(prose) and _ABOUT_THIS_USER.search(prose))


def _points_back(prose: str) -> bool:
    return bool(_POINTS_BACK.match(prose.lstrip("*_ ")) and _ABOUT_THIS_USER.search(prose))
