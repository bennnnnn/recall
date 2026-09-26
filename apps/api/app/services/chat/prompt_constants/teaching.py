# ruff: noqa: RUF001
"""Adaptive tutoring and learning-plan routing.

Teach-me turns are conversations, not pass/fail quizzes. The assistant shows a
small roadmap, teaches one concept at a time, and adapts to correct, wrong,
confused, accidental, or off-topic follow-ups without replaying already-seen
content.

Learning-plan requests ("70-day Python plan", "4-week roadmap") are separate:
they should return a complete actionable roadmap with examples, practice,
projects, and milestones rather than entering the one-step-at-a-time tutor.
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

# A bounded roadmap/course request is different from an interactive teach-me
# session. It asks for the whole progression now.
_LEARNING_PLAN_TURN = re.compile(
    r"(?:"
    r"\b(?:give|make|create|build|write)\s+(?:me\s+)?(?:an?\s+)?"
    r"(?:(?:\d+)[\s-]?(?:day|days|week|weeks|month|months)\s+)?"
    r"(?:(?:learning|study|mastery)\s+)?(?:plan|roadmap)\b|"
    r"\b(?:learning|study|mastery)\s+(?:plan|roadmap)\b|"
    r"\b(?:plan|roadmap)\s+(?:to|for)\s+(?:learn|master|study)\b|"
    r"\b\d+[\s-]?(?:day|days|week|weeks|month|months)\b"
    r"[^.?!]{0,120}\b(?:plan|roadmap|learn|master|study|beginner|advanced|senior)\b|"
    r"\b(?:learn|master|study)\b[^.?!]{0,100}\b(?:in|over)\s+"
    r"\d+[\s-]?(?:day|days|week|weeks|month|months)\b|"
    r"\bteach\s+(?:me|us)\b[^.?!]{0,100}\b(?:in|over)\s+"
    r"\d+[\s-]?(?:day|days|week|weeks|month|months)\b|"
    # es / pt / fr / de
    r"\bplan\s+de\s+\d+[\s-]?(?:d[ií]as|dias|semanas|meses|semaines|mois)\b|"
    r"\b\d+[\s-]?(?:tage|wochen|monate)\b[^.?!]{0,80}\blernplan\b"
    r")",
    re.IGNORECASE,
)

LEARNING_PLAN_HINT = (
    "The user wants a complete learning roadmap now, not a thin topic list and not "
    "an interactive quiz. Make the plan actionable and easy to scan on mobile.\n"
    "- Match the requested duration and target. If the target is unrealistic as a job "
    "title or experience level, calibrate it in one sentence, then still give the "
    "strongest achievable knowledge/skill plan.\n"
    "- Start with an at-a-glance progression: phase/day ranges, focus, and the concrete "
    "ability the learner should have at the end of each phase. Use short headings and lists, "
    "not a schedule-style table unless the user explicitly asked for one.\n"
    "- Then make the roadmap specific. For a named N-day plan up to about 90 days, account "
    "for every day (or only group adjacent 2-3 days when they intentionally share one skill). "
    "Do not collapse a 70-day request into ten vague weekly bullets.\n"
    "- Each learning unit should say what to learn, show a concrete example when useful, "
    "say exactly what to practice/build, and state the expected outcome. For programming, "
    "include tiny code examples where they clarify the skill.\n"
    "- Include progressive exercises/projects, review/checkpoint days, milestones, and a "
    "repeatable daily study routine. End with what the learner should be able to do by the "
    "final day and what still requires real production experience.\n"
    "- Avoid empty advice such as 'master X', 'practice Y', or 'learn best practices' without "
    "naming the subskills, exercise, deliverable, or success criterion."
)


def is_learning_plan_request(text: str) -> bool:
    """True for bounded roadmaps/courses that should be delivered in full."""
    cleaned = collapse_ws(text)
    if not cleaned or len(cleaned) > 800:
        return False
    return bool(_LEARNING_PLAN_TURN.search(cleaned))


TEACHING_HINT = (
    "The user wants an adaptive conversational lesson, not a static quiz, slideshow, "
    "roadmap, or reference sheet. Understanding is the goal; checks are diagnostic, "
    "never gates.\n"
    "- First reply: one short sentence on how the lesson will work, then a numbered outline "
    "that covers the essential scope before teaching Step 1 only. Usually use 6-12 meaningful "
    "top-level steps; group related basics instead of omitting important operations, patterns, "
    "or real-world use just to keep the outline short. Do not dump the whole course unless the "
    "user asks for everything at once.\n"
    "- Each step starts with a heading like `### Step 1/6 — What a dictionary is` "
    "(translate the word Step to the reply language; keep the 1/6 numbers). Explain one "
    "main idea in plain language, use 2-4 short paragraphs at most, and show one small "
    "concrete example (code for programming, a worked example otherwise). Add an analogy "
    "or visual mental model when it genuinely helps.\n"
    "- End the step with ONE low-pressure conversational question (for example, whether "
    "they want to answer, ask something, see another example, or continue). Keep a question "
    "mark in that final prompt so the lesson can be recognized on the next turn. A knowledge "
    "check is optional and should be labeled as optional/quick when used; never say they "
    "must answer correctly before continuing.\n"
    "- Do not force a multiple-choice question after every tiny idea. Prefer natural "
    "predict/explain/try-it prompts; use A-D only when choices actually help.\n"
    "- Treat mistakes as information for teaching, not failure. Never punish a wrong, "
    "partial, accidental, or unclear response by restarting the lesson. Never replay an "
    "already-delivered step verbatim unless the learner explicitly asks to see it again.\n"
    "- If the learner asks for everything at once, a summary, a cheat sheet, or a full "
    "roadmap, switch to that format immediately."
)

# Short style: the same lesson, smaller steps (the SHORT format bans headings).
TEACHING_SHORT_NOTE = (
    "Response length is SHORT, so keep each step small: one or two short "
    "paragraphs and a one-line example. Keep the step heading and one low-pressure "
    "question/invitation so the conversation can continue naturally."
)


def is_teaching_request(text: str) -> bool:
    """True for interactive tutoring, not a procedure or full learning roadmap."""
    cleaned = collapse_ws(text)
    if not cleaned or len(cleaned) > 400:
        return False
    if not _TEACH_TURN.search(cleaned):
        return False
    if is_learning_plan_request(cleaned):
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
    """Adaptive policy for the turn after a delivered lesson step."""
    lead = (
        f"A lesson is in progress. The learner has ALREADY SEEN Step {step}/{total}. "
        "Do not reproduce that step, its paragraphs, its example, or its check question "
        "verbatim. The latest message is a reaction to the lesson, not automatically an "
        "exam answer. Checks are diagnostic, never gates.\n"
        "Interpret the learner's intent first:\n"
        "- Correct answer / 'got it' / 'ok' / 'next': acknowledge in one short sentence, "
        "then continue.\n"
        "- Plausible wrong or partial answer: correct only the specific misunderstanding "
        "in 1-3 sentences, preferably with a FRESH tiny example, then continue to the next "
        "step unless the learner explicitly says they are confused or wants to stay here. "
        "Do not require a second correct attempt to unlock progress.\n"
        "- Explicit confusion ('I don't understand', 'why?', 'show me another example'): "
        "stay on the concept, explain it a DIFFERENT way with a new analogy/example, and "
        "end with one low-pressure check or choice to continue. Never paste the old lesson.\n"
        "- Accidental, nonsensical, keyboard-smash, or unclear input: do NOT grade it as "
        "wrong. Briefly acknowledge it, give the prior check's answer if that helps close "
        "the loop, and continue the lesson instead of restarting the step.\n"
        "- A coherent off-topic question: answer it normally and then resume from the "
        "next lesson step when natural; never replay the previous step as context.\n"
    )
    if step >= total:
        nxt = (
            f"- Step {total}/{total} was the final lesson step. Once the learner is not "
            "asking for clarification on it, give a short 3-5 bullet recap and one optional "
            "larger practice exercise or next topic.\n"
        )
    else:
        nxt = (
            f"- Normal progression is Step {step + 1}/{total}. Teach that next step in the "
            "same concise tutor format and end with one low-pressure question/invitation.\n"
        )
    tail = (
        "- If the learner asks to skip, stop, change topics, or get everything at once, "
        "follow that request immediately. Maintain conversational continuity; optimize for "
        "understanding, not test completion."
    )
    return lead + nxt + tail
