# ruff: noqa: RUF001
"""Teach-me turns: a lesson one step at a time, not a how-to or reference sheet.

"Teach me python dictionary step by step" used to take the how-to layout
("a one-line goal, then numbered steps") under the answer-first defaults, so
the reply was a compressed reference list: no explanation, no check, no wait.
A lesson outlines the path, teaches one step, asks one check question and
stops. The next turn finds that step (``lesson_step``) and continues from it:
grade the answer, re-explain when it is wrong, then the next step.
"""

from __future__ import annotations

import re

from app.services.text_normalize import collapse_ws

# Asking to be taught, in the shipped UI languages. A task ("teach me how to
# install Docker") keeps its how-to steps; see ``_PROCEDURE``.
_TEACH_TURN = re.compile(
    r"(?:"
    r"\bteach\s+(?:me|us)\b|"
    r"\b(?:can|could|would|will)\s+you\s+teach\b|"
    r"\bhelp\s+me\s+(?:learn|study)\b|"
    r"\bi\s*(?:'d|’d|\s+would)?\s+(?:want|like|love|need)\s+to\s+learn\b|"
    r"\bi\s+wanna\s+learn\b|"
    r"\btutor\s+me\b|"
    r"\bbe\s+my\s+(?:tutor|teacher)\b|"
    r"\b(?:give\s+me\s+)?an?\s+(?:lesson|crash\s+course)\s+(?:on|in|about)\b|"
    # es / pt
    r"\bens[eé]ñ(?:ame|anos|arme)\b|\bquiero\s+aprender\b|\bay[uú]dame\s+a\s+aprender\b|"
    r"\bme\s+ensin[ae]\b|\bensina[- ]me\b|\bquero\s+aprender\b|"
    # fr
    r"\bapprends[- ]moi\b|\benseigne[- ]moi\b|\bje\s+(?:veux|voudrais)\s+apprendre\b|"
    # de
    r"\bbring\s+mir\b[^.?!]{0,60}\bbei\b|"
    r"\bich\s+(?:möchte|will|würde\s+gerne?)\b[^.?!]{0,60}\blernen\b|"
    # it
    r"\binsegnami\b|\b(?:voglio|vorrei)\s+imparare\b|"
    # ru
    r"\bнаучи\s+меня\b|\bобучи\s+меня\b|\bхочу\s+(?:научиться|выучить|изучить)\b|"
    # tr
    r"\böğret(?:ir\s+misin|ebilir\s+misin)?\b|\böğrenmek\s+istiyorum\b|"
    # am
    r"አስተምረኝ|መማር\s*እፈልጋለሁ"
    r")",
    re.IGNORECASE,
)

# A task keeps the how-to layout: the user wants it done, not a lesson.
_PROCEDURE = re.compile(
    r"\b(?:install|uninstall|set\s*up|setup|configure|deploy|download|troubleshoot|"
    r"fix|repair|reset|log\s*in|sign\s*up)\b",
    re.IGNORECASE,
)

# "### Step 2/6 — Accessing values", in any language: a heading (or bold line)
# whose first word is followed by the step and the total ("2 of 6" too).
_LESSON_STEP = re.compile(
    r"^\s*(?:#{1,4}\s+|\*\*)\s*[^\W\d_]+\s+(\d{1,2})\s*(?:/|\s+of\s+)\s*(\d{1,2})\b",
    re.MULTILINE | re.IGNORECASE,
)
_MAX_LESSON_STEPS = 20

TEACHING_HINT = (
    "The user wants to be taught this topic. Run it as a lesson, not a how-to, "
    "roadmap, or reference sheet; this layout replaces the answer-first default for "
    "this turn.\n"
    "- First reply: one short sentence on how the lesson will go (one idea at a "
    "time, a quick check after each), a numbered outline of 4-8 step titles, then "
    "teach Step 1 only.\n"
    "- Each step starts with a heading like `### Step 1/6 — What a dictionary is` "
    "(write the word Step in the reply language; keep the 1/6 numbers). Then a "
    "plain-language explanation in 2-4 short paragraphs, one small example (a "
    "code block for code, a worked example otherwise), and a simple mental model "
    "or analogy when it helps.\n"
    "- One new idea per step. Keep examples tiny and concrete, and define any "
    "term the user may not know in one line.\n"
    "- End every step with exactly one check question: predict the output, fill "
    "in a blank, or choose from options written as plain lines `A.` to `D.`. "
    "Stop there: do not answer it and do not start the next step.\n"
    "- If the user asks for everything at once, a summary, or a cheat sheet, give "
    "the full reference instead."
)

# Short style: the same lesson, smaller steps (the SHORT format bans headings).
TEACHING_SHORT_NOTE = (
    "Response length is SHORT, so keep each step small: one or two short "
    "paragraphs and a one-line example. The step heading and check question stay."
)


def is_teaching_request(text: str) -> bool:
    """True when the user asks to be taught ("teach me X", "I want to learn X")."""
    cleaned = collapse_ws(text)
    if not cleaned or len(cleaned) > 400:
        return False
    if not _TEACH_TURN.search(cleaned):
        return False
    return not _PROCEDURE.search(cleaned)


def lesson_step(text: str | None) -> tuple[int, int] | None:
    """(step, total) of the last lesson step heading in an assistant reply."""
    if not text:
        return None
    found: tuple[int, int] | None = None
    for match in _LESSON_STEP.finditer(text):
        step, total = int(match.group(1)), int(match.group(2))
        if 1 <= step <= total <= _MAX_LESSON_STEPS:
            found = (step, total)
    return found


def lesson_continue_hint(step: int, total: int) -> str:
    """The next turn of a lesson whose last reply taught ``step`` of ``total``."""
    lead = (
        f"A lesson is in progress: your last reply taught Step {step}/{total} and "
        "ended with a check question. Treat this message as the student's answer "
        "or reaction to it.\n"
        "- If they answered, say whether it is right and why in one or two sentences.\n"
        "- If it is wrong, or they say no or that they don't understand, explain the "
        "same idea another way with a new small example and ask a new check "
        "question on it. Do not move on yet.\n"
    )
    if step >= total:
        nxt = (
            f"- Step {total}/{total} was the last step. When they have it, give a "
            "short recap of the whole lesson in 3-5 bullets and offer one bigger "
            "practice exercise or a next topic.\n"
        )
    else:
        nxt = (
            f"- When they have it (right answer, 'got it', 'next'), teach Step "
            f"{step + 1}/{total} in the same format and end with one check question.\n"
        )
    tail = (
        "- If they ask to skip, stop, or get everything at once, do that. If the "
        "message is unrelated to the lesson, answer it normally."
    )
    return lead + nxt + tail
