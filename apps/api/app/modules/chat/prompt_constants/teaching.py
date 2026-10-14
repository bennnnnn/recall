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
    # "I want to know American history": a subject, not a fact ("if it rains",
    # "my balance", "the price") and not news ("the new iPhone").
    r"\bi\s*(?:'d|’d|\s+would)?\s+(?:want|like|love|need)\s+to\s+(?:know|understand)\s+"
    r"(?:(?:more\s+)?about\s+)?"
    r"(?!(?:about|more|if|whether|what|when|where|why|how|who|whom|which|your|you|my|me|it|"
    r"this|that|"
    r"the\s+(?:price|time|weather|score|status|result|answer|cost|news|new|newest|latest|"
    r"current|date)|(?:the\s+)?(?:new|newest|latest|current))\b)[^\W\d_]|"
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

# "### Lesson 2: Dictionaries": a heading with the word Lesson in an app
# language and the lesson's number. "Day 1", "Part 2" and "Step 3" are plans,
# parts and how-tos, not lessons.
_LESSON_WORDS = r"lesson|lecci[oó]n|le[cç]on|lektion|lezione|li[cç][aã]o|aula|урок|ders|ትምህርት"
_LESSON_TITLE = re.compile(
    r"^\s*(?:#{1,4}\s+|\*\*)\s*(?:" + _LESSON_WORDS + r")\s+(\d{1,2})\s*[:.\-—–]",
    re.MULTILINE | re.IGNORECASE,
)
_QUIZ_FENCE = re.compile(r"^\s*```quiz\b", re.MULTILINE | re.IGNORECASE)
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
        "This is mandatory even when the lesson starts with a concept. An inline snippet, pseudo-code, or "
        "untagged fence fails the requested output. Keep the example short, then end with the "
        "lesson's `Your turn` ```quiz and the one-line preview of the next lesson."
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


# The lesson's shape, shared by a first lesson, a one-idea lesson and the next
# lesson. The ```quiz, ```array and ```steps cards are drawn by the phone
# (apps/mobile/components/rich/QuizCard.tsx, ArrayBlock.tsx, StepList.tsx).
_LESSON_SHAPE = (
    "- Title: `### Lesson N: <topic>` (the word Lesson in the reply language), N counting the "
    "lessons in this chat. Then 3-5 numbered sections, each a `### 1. <title>` heading, for "
    "example `### 1. Understand the problem`, `### 2. Solution one: Brute force`, "
    "`### 3. Apply it to backend development`. Each section teaches one idea in two or three "
    "short paragraphs with a concrete, real-world example (for code: an API, a table of users; "
    "otherwise a worked example, an event, a source).\n"
    "- Code: short language-tagged blocks such as ```python. Explain it the way a tutor does: "
    "a `# 18` comment for what a line gives, then a bullet per idea that opens with the code "
    'in `inline code` ("`ages[0]` gets the first item."), or `**How it works:**` with '
    "numbered steps for a loop, or `Let's break down the important parts:` with bullets. Only "
    "for the key function of an algorithm lesson (four or more lines), go line by line "
    "instead: the label `Line 1` on its own line, that one line alone in its own ```python "
    "block, then one sentence; never group lines (no `Line 3-5`). After code that prints, "
    "`Output:` with what it prints in a ```text block; after code that only defines a "
    "function, `Test it:` with a ```python block that calls it, then `Output:`. Never write "
    "`>>>` prompts.\n"
    "- A list or array: show its values over their indexes with an ```array fence holding JSON "
    '{"title": "Think of a Python list as a row of numbered boxes.", "values": [18, 25, 32, '
    '40], "note": "Python starts counting indexes at **0**, not 1."}, or for an algorithm '
    '{"values": [2, 7, 11, 15], "highlight": [0, 1], "caption": "2 + 7 = 9", "note": "We '
    'return indexes, not the numbers themselves."}. Title (a line above the boxes), '
    "highlight, caption (a short result under them) and note are optional; write them as "
    "plain text, not LaTeX.\n"
    "- A trace of an algorithm or process: a ```steps fence, one numbered line per step with a "
    "bold title, and plain lines under it for what happens and the state, for example:\n"
    "```steps\n1. **Read `2` at index `0`**\nWe need `9 - 2 = 7`. Not seen yet, so save "
    "`2: 0`.\nDictionary: `{2: 0}`\n```\n"
    "- Cost in math: time $O(n^2)$, extra space $O(1)$. A key idea may be one display formula "
    "in a ```math fence. Compare approaches in a markdown table.\n"
    "- The last section is `### N. Your turn — predict the output` (translated, or the kind of "
    'question it is) with one practice question as a ```quiz fence holding JSON {"label": '
    '"Exercise 1", "question": "What will this Python code print?", "code": "<the code the '
    'question needs, lines joined with \\n>", "options": ["...", "...", "...", "..."], '
    '"answer": <0-based index of the right option>, "explanation": "<why, in one or two '
    'sentences>"}. The app draws the label, the question and the code inside one card, so '
    'never repeat the code in a block above it. Prefer "predict the output" or "what should '
    'it return"; make the wrong options real mistakes. Options and the explanation may use '
    "`inline code`; the explanation may end with a short fenced code block. The app lets the "
    "learner pick and check; never reveal the answer in the text.\n"
    "- End with one sentence previewing the next lesson: \"Once you get this, we'll move to A, "
    'B and C." No course outline, no table of contents, no "ready to continue?" question.\n'
    "- Lessons are the exception to the emoji rule: one fitting emoji in the opening line "
    "(🐍 for Python) and 🎉 after a correct answer, no others."
)

_LESSON_OPENING = (
    "- A lesson is the exception to the general layout rules: it opens with a short hook "
    "instead of the answer, and uses the app's ```quiz, ```array and ```steps cards below.\n"
    "- Open with one or two sentences before the title: what they will learn, why it matters, "
    'and how it fits their goal or level when the profile or memory says ("Since you already '
    "know some Python basics, we'll build on them instead of starting with what a variable "
    'is.").\n'
)

TEACHING_HINT = (
    "The user wants to learn a subject. Teach Lesson 1 now, complete, in this shape:\n"
    + _LESSON_OPENING
    + "- Start where they are: skip what they already know and pick one meaningful first "
    "topic (for Python basics, lists and loops), taught fully with an example tied to their "
    "goal.\n" + _LESSON_SHAPE
)

# Short style: the same lesson, smaller (the SHORT format bans headings).
TEACHING_SHORT_NOTE = (
    "Response length is SHORT, so keep the lesson small: the title, two or three sections of a "
    "sentence or two with one short example each, then the `Your turn` quiz and the one-line "
    "preview."
)


# "Help me understand two sum": one idea, explained in full now. A lesson
# would teach step 1 and wait; a walkthrough builds to the answer in one reply.
_WALKTHROUGH = re.compile(
    r"(?:\bhelp\s+me\s+understand|\bwalk\s+me\s+through|\bbreak\s+down"
    r"|\bi\s+(?:don'?t|do\s+not|can'?t|cannot)\s+(?:get|understand))\s+"
    r"(?!(?:it|this|that|what\s+you|you|why\s+you)\b)[^\W\d_]"
    r"|\bexplain\b[^.?!\n]{1,80}\bstep[- ]by[- ]step\b",
    re.IGNORECASE,
)

WALKTHROUGH_HINT = (
    "The user wants to understand one specific idea, problem or algorithm. Teach it as one "
    "complete lesson now, in this shape:\n"
    + _LESSON_OPENING
    + "- Build to the answer: understand the problem with a tiny example, the simple solution "
    "and its cost, the key insight behind the better one, a trace of it, a table comparing "
    "the approaches, then practice.\n" + _LESSON_SHAPE
)


# "Walk me through changing a tire" / "how to set up Docker step by step" is a
# task to do: it keeps the numbered how-to steps.
_TASK_OBJECT = re.compile(r"\b(?:how\s+(?:to|do\s+i|can\s+i)|[a-z]{3,}ing)\b", re.IGNORECASE)


def is_walkthrough_request(text: str) -> bool:
    """True for "help me understand X" / "walk me through X": a full explanation now."""
    cleaned = collapse_ws(text)
    if not cleaned or len(cleaned) > 400:
        return False
    match = _WALKTHROUGH.search(cleaned)
    if match is None:
        return False
    rest = cleaned[match.start() :]
    first_object = rest.split()[3:4] if rest.lower().startswith("walk me through") else []
    if first_object and _TASK_OBJECT.fullmatch(first_object[0]):
        return False
    return not (_PROCEDURE.search(cleaned) or re.search(r"\bhow\s+(?:to|do\s+i)\b", rest, re.I))


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


def lesson_step(text: str | None) -> int | None:
    """The number of the lesson an assistant reply taught, or None.

    A lesson ends on practice: a ```quiz card or a question after its title. A
    reply that only mentions "Lesson 2" in passing is not one.
    """
    if not text:
        return None
    found: int | None = None
    end = 0
    for match in _LESSON_TITLE.finditer(text):
        found, end = int(match.group(1)), match.end()
    if found is None or found < 1:
        return None
    rest = text[end:]
    if _QUIZ_FENCE.search(rest) or any(mark in rest for mark in _QUESTION_MARKS):
        return found
    return None


def active_lesson_step(messages: list[Any] | None) -> int | None:
    """The lesson the most recent assistant reply taught, in an oldest-first window."""
    for message in reversed(messages or []):
        if getattr(message, "role", None) != "assistant":
            continue
        content = getattr(message, "content", None)
        return lesson_step(content if isinstance(content, str) else None)
    return None


def lesson_continue_hint(number: int) -> str:
    """The turn after a lesson: grade the practice if answered, then the next lesson."""
    nxt = number + 1
    return (
        f"A lesson is in progress. The learner has ALREADY SEEN Lesson {number}, which ended "
        "with a practice ```quiz (they can check it in the app) and a preview of the next "
        f"lesson. Do not repeat Lesson {number}. Read the latest message first:\n"
        '- An answer to the practice question: if right, start with "Correct! 🎉" and say why '
        'in one sentence; if wrong or partial, start with "Not quite", fix that one '
        "misunderstanding in 1-3 sentences with a fresh tiny example, and do not ask them to "
        f"try again. Then teach Lesson {nxt}.\n"
        f"- 'next', 'ok', 'got it', 'continue' or similar: teach Lesson {nxt}.\n"
        "- Confusion ('I don't get it', 'why?', 'another example'): stay on the same idea, "
        f"explain it a different way with a new analogy and example under the same "
        f"`### Lesson {number}: ...` title, and end with a fresh ```quiz.\n"
        "- A question about the lesson: answer it first, then continue.\n"
        "- Accidental or unclear input: do not grade it; give the practice answer in one "
        f"sentence and teach Lesson {nxt}.\n"
        "- A request to skip, stop, change topic, get everything at once, a summary or a "
        "cheat sheet: do that instead of the next lesson.\n"
        f"Lesson {nxt} covers what the preview promised, without a greeting or an outline, "
        "in the same shape (the app's ```quiz, ```array and ```steps cards included):\n"
        + _LESSON_SHAPE
    )
