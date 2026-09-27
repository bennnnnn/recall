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
from typing import Any

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
    r"\b(?:be|become|act\s+as)\s+my\s+(?:tutor|teacher)\b|"
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
# session. Keep the pieces separate so common word orders remain readable and
# elapsed-time statements can be rejected before they become accidental plans.
_DURATION_TEXT = r"\b\d{1,3}[\s-]?(?:day|days|week|weeks|month|months)\b"
_DURATION = re.compile(_DURATION_TEXT, re.IGNORECASE)
_EXPLICIT_LEARNING_PLAN = re.compile(
    r"(?:"
    r"\b(?:learning|study|mastery|training)\s+(?:plan|roadmap|curriculum|schedule)\b|"
    r"\b(?:plan|roadmap)\s+(?:to|for)\s+(?:learn|learning|master|mastering|study|studying)\b|"
    r"\b(?:plan|roadmap)\b[^.?!]{0,45}\b(?:to\s+)?(?:learn|master|study)\b|"
    r"\b(?:curriculum|syllabus|course\s+plan)\b"
    r")",
    re.IGNORECASE,
)
_LEARNING_CUE = re.compile(
    r"\b(?:learn|learning|master|mastering|mastery|study|studying|train|training|"
    r"beginner|intermediate|advanced|senior|course|curriculum|syllabus|skill)\b",
    re.IGNORECASE,
)
_PLAN_CUE = re.compile(r"\b(?:plan|roadmap|curriculum|syllabus|course)\b", re.IGNORECASE)
_TEACH_WITH_DURATION = re.compile(
    rf"\b(?:teach\s+(?:me|us)|help\s+me\s+learn|i\s+(?:want|need|would\s+like)\s+to\s+learn)"
    rf"\b[^.?!]{{0,140}}{_DURATION_TEXT}",
    re.IGNORECASE,
)
_REQUESTED_DURATION_PLAN = re.compile(
    rf"\b(?:give|create|make|build|write|design|show|want|need)\b[^.?!]{{0,80}}"
    rf"{_DURATION_TEXT}[^.?!]{{0,60}}\b(?:plan|roadmap|curriculum|syllabus)\b",
    re.IGNORECASE,
)
_ELAPSED_LEARNING = re.compile(
    rf"(?:"
    rf"\b(?:started|finished|completed|spent)\b[^.?!]{{0,100}}{_DURATION_TEXT}|"
    rf"\b(?:i(?:'ve|\s+have)|we(?:'ve|\s+have)|has|had)\s+(?:already\s+)?(?:been\s+)?"
    rf"(?:learning|studying|practicing|training|working)\b[^.?!]{{0,100}}{_DURATION_TEXT}|"
    rf"\b(?:learned|studied|practiced|trained|worked)\b[^.?!]{{0,100}}\bfor\s+{_DURATION_TEXT}|"
    rf"{_DURATION_TEXT}\s+(?:ago|so\s+far)\b"
    rf")",
    re.IGNORECASE,
)
_NON_LEARNING_PLAN_CUE = re.compile(
    r"\b(?:business|workout|fitness|exercise|meal|diet|launch|marketing|content|"
    r"social\s+media|product|project|travel|vacation|budget|savings|campaign)\b",
    re.IGNORECASE,
)
_INTERNATIONAL_LEARNING_PLAN = re.compile(
    r"(?:"
    r"\bplan\s+de\s+\d{1,3}[\s-]?(?:d[ií]as|dias|semanas|meses|semaines|mois)\b"
    r"[^.?!]{0,80}\b(?:aprender|apprendre|estudiar|étudier|estudar)\b|"
    r"\b\d{1,3}[\s-]?(?:tage|wochen|monate)\b[^.?!]{0,80}\blernplan\b"
    r")",
    re.IGNORECASE,
)

_DAY_COUNT = re.compile(r"\b(\d{1,3})[\s-]?days?\b", re.IGNORECASE)
_PROGRAMMING_TAGS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\bpython\b", re.IGNORECASE), "python"),
    (re.compile(r"\b(?:javascript|js)\b", re.IGNORECASE), "javascript"),
    (re.compile(r"\b(?:typescript|ts)\b", re.IGNORECASE), "typescript"),
    (re.compile(r"\bjava\b", re.IGNORECASE), "java"),
    (re.compile(r"\b(?:c\+\+|cpp)\b", re.IGNORECASE), "cpp"),
    (re.compile(r"\bc#\b", re.IGNORECASE), "csharp"),
    (re.compile(r"\b(?:shell|bash)\b", re.IGNORECASE), "bash"),
    (re.compile(r"\b(?:sql|postgres(?:ql)?)\b", re.IGNORECASE), "sql"),
    (re.compile(r"\bhtml\b", re.IGNORECASE), "html"),
    (re.compile(r"\bcss\b", re.IGNORECASE), "css"),
    (re.compile(r"\b(?:swift|swiftui)\b", re.IGNORECASE), "swift"),
    (re.compile(r"\b(?:kotlin|android)\b", re.IGNORECASE), "kotlin"),
    (re.compile(r"\bgo(?:lang)?\b", re.IGNORECASE), "go"),
    (re.compile(r"\brust\b", re.IGNORECASE), "rust"),
    (re.compile(r"\bruby\b", re.IGNORECASE), "ruby"),
    (re.compile(r"\bphp\b", re.IGNORECASE), "php"),
)

LEARNING_PLAN_HINT = (
    "The user wants a complete learning roadmap now, not a thin topic list and not "
    "an interactive quiz. Make the plan actionable and easy to scan on mobile.\n"
    "- Match the requested duration and target. If the target is unrealistic as a job "
    "title or experience level, calibrate it in one sentence, then still give the "
    "strongest achievable knowledge/skill plan.\n"
    "- Start with an at-a-glance progression: phase/day ranges, focus, and the concrete "
    "ability the learner should have at the end of each phase. When it improves clarity, show "
    "the path as a compact arrow progression such as `Foundations → Core skills → Projects`. "
    "Use short headings and lists, not a schedule-style table unless the user explicitly asked for one.\n"
    "- Then make the roadmap specific. For a named N-day plan up to about 90 days, write "
    "one compact entry for every day, in order. A 70-day plan must explicitly contain "
    "`Day 1` through `Day 70` with no missing day and no broad multi-week ranges. Only group "
    "2-3 adjacent days when the user explicitly asks for grouping. Do not collapse a 70-day "
    "request into ten vague weekly bullets.\n"
    "- Keep a long daily plan within the response budget: make each day one compact line "
    "(roughly 20-30 words) in the shape `Topic → Practice/build → Done when ...`. Put one "
    "short runnable example after each major phase instead of expanding every day into a "
    "mini-essay. Reserve room for the final day, milestones, daily routine, and caveat.\n"
    "- Every phase must name what to learn, show a concrete example, say exactly what to "
    "practice/build, and make the expected outcome verifiable. For a programming roadmap, "
    "include small runnable code examples in tagged fences throughout the progression—not only prose. "
    "For a plan around 70 days, 4-6 short code blocks spread across phases is enough.\n"
    "- Include progressive exercises and projects, review/checkpoint days, milestones, and a "
    "repeatable daily study routine. End with what the learner should be able to do by the "
    "final day and what still requires longer-term real-world practice or experience; for "
    "software engineering, distinguish learned skills from actual production experience. Before "
    "sending a named daily plan, silently verify that its last requested day is present.\n"
    "- Avoid empty advice such as 'master X', 'practice Y', or 'learn best practices' without "
    "naming the subskills, exercise, deliverable, or success criterion."
)


def learning_plan_daily_contract(text: str) -> str:
    """Return an exact day-label contract for bounded daily roadmaps."""
    match = _DAY_COUNT.search(collapse_ws(text))
    if match is None:
        return ""
    count = int(match.group(1))
    if count < 2 or count > 90:
        return ""
    labels = " | ".join(f"Day {day}" for day in range(1, count + 1))
    programming_rule = ""
    tag = _programming_tag(text)
    if tag:
        checkpoints = sorted({max(1, round(count * fraction / 5)) for fraction in range(1, 6)})
        locations = ", ".join(f"Day {day}" for day in checkpoints)
        programming_rule = (
            f"\n- Include exactly five short runnable ```{tag} code blocks total, placed after "
            f"{locations}. Inline snippets do not count."
        )
    return (
        f"HARD DAILY-COVERAGE CONTRACT FOR THIS {count}-DAY PLAN:\n"
        f"- The daily breakdown must contain exactly {count} separate Markdown lines, one per day.\n"
        "- Every line must begin with one bold day label in this shape: "
        "`- **Day N — Topic:** Learn → Practice/build → Done when ...`.\n"
        "- Do not combine days, skip a number, or use a day range in the daily breakdown.\n"
        f"- Required labels, in order: {labels}.\n"
        f"- Keep every day line compact so Day {count} and all closing sections fit.\n"
        "- After the daily lines, include these exact headings: `### Checkpoints and milestones`, "
        "`### Daily routine`, and `### Production-experience note`. Under the last heading, "
        "write the exact sentence `Production experience takes longer than this roadmap.` "
        f"before briefly explaining why.{programming_rule}"
    )


def _programming_tag(text: str) -> str | None:
    cleaned = collapse_ws(text)
    for pattern, tag in _PROGRAMMING_TAGS:
        if pattern.search(cleaned):
            return tag
    return None


def programming_lesson_contract(text: str) -> str:
    """Return a hard tagged-fence requirement for a named programming topic."""
    tag = _programming_tag(text)
    if tag is None:
        return ""
    return (
        "HARD PROGRAMMING-LESSON ACCEPTANCE CHECK: Before answering, verify the response contains "
        f"the literal opening fence ```{tag}, runnable code on following lines, and a closing ```. "
        "This is mandatory even when Step 1 is conceptual. An inline snippet, pseudo-code, or "
        "untagged fence fails the requested output. Keep the example short, then end with the "
        "lesson's one conversational question."
    )


def is_learning_plan_request(text: str) -> bool:
    """True for bounded roadmaps/courses that should be delivered in full."""
    cleaned = collapse_ws(text)
    if not cleaned or len(cleaned) > 800:
        return False
    if _INTERNATIONAL_LEARNING_PLAN.search(cleaned):
        return True
    explicit = _EXPLICIT_LEARNING_PLAN.search(cleaned)
    duration = _DURATION.search(cleaned)
    if explicit and (not _NON_LEARNING_PLAN_CUE.search(cleaned) or _LEARNING_CUE.search(cleaned)):
        return True
    if duration is None:
        return False
    if _ELAPSED_LEARNING.search(cleaned) and not _TEACH_WITH_DURATION.search(cleaned):
        return False
    if _NON_LEARNING_PLAN_CUE.search(cleaned) and not _LEARNING_CUE.search(cleaned):
        return False
    if _REQUESTED_DURATION_PLAN.search(cleaned) or _TEACH_WITH_DURATION.search(cleaned):
        return True
    around_duration = cleaned[max(0, duration.start() - 140) : duration.end() + 140]
    return bool(_LEARNING_CUE.search(around_duration) or _PLAN_CUE.search(around_duration))


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
    "(translate the word Step to the reply language). The denominator must match the number "
    "of top-level outline steps: an 8-step outline uses Step 1/8, never a hard-coded /6. Explain one "
    "main idea in plain language, use 2-4 short paragraphs at most, and show one small "
    "concrete example (code for programming, a worked example otherwise). In a programming "
    "lesson, put that example in a language-tagged fence such as ` ```python `—never make the "
    "only example inline or use an untagged fence. Add an analogy "
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
    if verb is None:
        return False
    action = verb.group(1).lower()
    # "Teach me how to pass an interview/exam" is preparation/tutoring, not a
    # one-off procedure like installing Docker or tying a knot.
    if action == "pass" and re.search(
        r"\b(?:interview|exam|test|assessment|coding\s+challenge)\b",
        cleaned,
        re.IGNORECASE,
    ):
        return False
    return action not in _LEARNING_VERBS


def lesson_step(text: str | None) -> tuple[int, int] | None:
    """(step, total) of the last lesson step in an assistant reply.

    A lesson step ends on a low-pressure question/invitation, so a numbered
    how-to that happens to say "Step 5/5" without asking anything is not one.
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


def active_lesson_step(messages: list[Any] | None) -> tuple[int, int] | None:
    """Lesson state from the most recent assistant reply in an oldest-first window."""
    for message in reversed(messages or []):
        if getattr(message, "role", None) != "assistant":
            continue
        content = getattr(message, "content", None)
        return lesson_step(content if isinstance(content, str) else None)
    return None


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
        "- Explicit confusion ('I don't understand', 'why?', 'show me another example', or "
        "'no' to an understanding question): stay on the concept and begin with the exact "
        f"same `### Step {step}/{total} — ...` heading, but explain it a DIFFERENT way with a "
        "new analogy/example. End with one low-pressure conversational question containing "
        "a question mark so lesson state survives the next turn. Never paste the old lesson.\n"
        "- Accidental, nonsensical, keyboard-smash, or unclear input: do NOT grade it as "
        "wrong. Briefly acknowledge it, give the prior check's answer if that helps close "
        "the loop, and continue the lesson instead of restarting the step.\n"
        "- If the learner both answers and asks a question, answer their question before "
        "resuming progression.\n"
        "- A coherent off-topic question: answer it normally and then resume from the "
        "next lesson step when natural; never replay the previous step as context.\n"
        "- Do not repeat the original lesson outline on follow-up turns.\n"
    )
    if step >= total:
        nxt = (
            f"- Step {total}/{total} was the final lesson step. Once the learner is not "
            "asking for clarification on it, give a short 3-5 bullet recap and one optional "
            "larger practice exercise or next topic.\n"
        )
    else:
        nxt = (
            f"- Normal progression is Step {step + 1}/{total}. Start with a heading like "
            f"`### Step {step + 1}/{total} — ...`, teach one main idea with a fresh example, "
            "and end with one low-pressure conversational question containing a question mark "
            "so the lesson remains recognizable on the next turn.\n"
        )
    tail = (
        "- If the learner asks to skip, stop, change topics, get everything at once, or "
        "switch to quiz/test/practice-only mode, follow that request immediately instead of "
        "forcing normal lesson progression. Maintain conversational continuity; optimize for "
        "understanding, not test completion. Do not score or grade the learner unless asked."
    )
    return lead + nxt + tail
