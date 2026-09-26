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
# "Teach me (how) to bake bread" asks for a procedure; "teach me how to code"
# asks to learn a skill. The verb after "to" tells them apart.
_TO_VERB = re.compile(
    r"\b(?:(?:teach|help)\s+(?:me|us)\s+(?:how\s+)?to|learn\s+(?:how\s+)?to)\s+([a-z]+)",
    re.IGNORECASE,
)
_LEARNING_VERBS = frozenset(
    {
        "add",
        "analyse",
        "analyze",
        "budget",
        "calculate",
        "code",
        "compute",
        "conjugate",
        "count",
        "debug",
        "differentiate",
        "divide",
        "draw",
        "factor",
        "graph",
        "integrate",
        "invest",
        "learn",
        "multiply",
        "play",
        "program",
        "pronounce",
        "read",
        "reason",
        "say",
        "simplify",
        "sing",
        "solve",
        "speak",
        "spell",
        "study",
        "subtract",
        "think",
        "type",
        "understand",
        "use",
        "write",
    }
)

# "### Step 2/6 — Accessing values": a heading (or bold line) with the word
# Step in an app language, then the step and the total ("2 of 6" too). Other
# numbered headings ("Day 1/7", "Part 2/4") are plans, not lessons.
_STEP_WORDS = r"step|paso|[ée]tape|schritt|passo|etapa|шаг|ad[ıi]m|ደረጃ"
_LESSON_STEP = re.compile(
    r"^\s*(?:#{1,4}\s+|\*\*)\s*(?:" + _STEP_WORDS + r")\s+(\d{1,2})\s*(?:/|\s+of\s+)\s*"
    r"(\d{1,2})\b",
    re.MULTILINE | re.IGNORECASE,
)
_MAX_LESSON_STEPS = 20
_QUESTION_MARKS = ("?", "？", "፧")

TEACHING_HINT = (
    "The user wants to be taught this topic. Run it as an adaptive conversational lesson, "
    "not a how-to, roadmap, reference sheet, or exam; this layout replaces the answer-first "
    "default for this turn.\n"
    "- First reply: one short sentence on how the lesson will go, a numbered outline of 4-8 "
    "step titles, then teach Step 1 only.\n"
    "- Each step starts with a heading like `### Step 1/6 — What a dictionary is` "
    "(write the word Step in the reply language; keep the 1/6 numbers). Then a "
    "plain-language explanation in 2-4 short paragraphs, one small example (a "
    "code block for code, a worked example otherwise), and a simple mental model "
    "or analogy when it helps.\n"
    "- One new idea per step. Keep examples tiny and concrete, and define any "
    "term the user may not know in one line.\n"
    "- End each step with one light understanding check: predict the output, fill "
    "in a blank, or choose from options written as plain lines `A.` to `D.`. "
    "The check is diagnostic, not a pass/fail gate: the learner never has to earn "
    "permission to continue. Stop after the check and wait for their reaction.\n"
    "- Never replay an already-delivered step verbatim on a later turn. If the learner "
    "needs it again, explain it a different way with a fresh example.\n"
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
    return not _asks_for_a_procedure(cleaned)


def _asks_for_a_procedure(cleaned: str) -> bool:
    if _PROCEDURE.search(cleaned):
        return True
    verb = _TO_VERB.search(cleaned)
    return verb is not None and verb.group(1).lower() not in _LEARNING_VERBS


def lesson_step(text: str | None) -> tuple[int, int] | None:
    """(step, total) of the last lesson step in an assistant reply.

    A lesson step ends on its check question, so a numbered how-to that happens
    to say "Step 5/5" without asking anything is not one.
    """
    if not text:
        return None
    found: tuple[int, int] | None = None
    end = 0
    for match in _LESSON_STEP.finditer(text):
        step, total = int(match.group(1)), int(match.group(2))
        if 1 <= step <= total <= _MAX_LESSON_STEPS:
            found, end = (step, total), match.end()
    if found is None or not any(mark in text[end:] for mark in _QUESTION_MARKS):
        return None
    return found


def lesson_continue_hint(step: int, total: int) -> str:
    """Guide the next conversational turn after a delivered lesson step."""
    lead = (
        f"A conversational lesson is in progress: your last reply already taught "
        f"Step {step}/{total} and ended with a quick understanding check. Treat the "
        "student's new message as a natural reaction, not as an exam submission.\n"
        f"- Step {step}/{total} has already been delivered. NEVER reproduce that step's "
        "full explanation, wording, or example again unless the student explicitly asks "
        "to see the exact previous text.\n"
        "- If the answer is correct, or they say 'got it', 'ok', 'next', or similar: "
        "acknowledge briefly and continue.\n"
        "- If the answer is clearly wrong but they are not expressing confusion: correct "
        "the specific misunderstanding in 1-3 sentences, use a fresh tiny example if it "
        "helps, then continue. Do NOT make them retry the same checkpoint and do not "
        "restart the step.\n"
        "- If they explicitly say they are confused, ask why, say they do not understand, "
        "or request another explanation: stay on the current idea, explain it differently "
        "with a NEW analogy/example/representation, then ask one simple check if useful. "
        "Never repeat the old paragraphs or old example.\n"
        "- If the message is gibberish, accidental, or too unclear to count as an answer: "
        "do not grade it. Briefly acknowledge that it may not have been an answer, give "
        "the check answer if needed, and keep the lesson moving.\n"
        "- If they ask a direct question about the current idea, answer it directly, then "
        "resume from where the lesson paused. Never restart from Step 1.\n"
    )
    if step >= total:
        nxt = (
            f"- Step {total}/{total} was the last step. After a correct answer, brief "
            "correction, or unclear input that does not signal confusion, give a short "
            "recap of the whole lesson in 3-5 bullets and offer one bigger practice "
            "exercise or a next topic.\n"
        )
    else:
        nxt = (
            f"- Whenever the action above says to continue, teach Step {step + 1}/{total} "
            "in the same format and end with one light understanding check. Do not repeat "
            f"Step {step}/{total} before it.\n"
        )
    tail = (
        "- If they ask to skip, stop, go back, or get everything at once, follow that "
        "request. If the message is unrelated to the lesson, answer it normally without "
        "replaying the lesson in the same turn."
    )
    return lead + nxt + tail
