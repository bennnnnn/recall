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

from app.modules.chat.prompt_constants.stuck import stuck_on_a_topic
from app.services.text_normalize import collapse_ws, straighten_apostrophes

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
# "Training" alone is a marathon's or a team's as often as a learner's: a training plan
# is caught by name above, and a marathon one there is a plan that does not teach.
_LEARNING_CUE = re.compile(
    r"\b(?:learn|learning|master|mastering|mastery|study|studying|"
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
# Plans for doing, not learning, by kind: work, travel, events, health, home and money.
# "Plan a 3 day trip to Rome" was a study roadmap ("Learn the Forum's layout → … → Done
# when", 2026-10-29): the list named travel and vacation but not the trip.
_NON_LEARNING_PLAN_CUE = re.compile(
    r"\b(?:business|launch|marketing|content|social\s+media|product|project|campaign|sales|"
    r"travel|vacation|trip|itinerary|holiday|honeymoon|road\s+trip|visit|tour|"
    r"wedding|party|birthday|event|"
    r"workout|fitness|exercise|gym|marathon|running|race|weight\s+loss|lose\s+weight|"
    r"meal|diet|detox|fasting|sleep|"
    r"move|moving|cleaning|declutter|renovation|garden|"
    r"budget|savings|debt|finance)\b",
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


def programming_tag(text: str) -> str | None:
    """The fence tag of the programming topic ``text`` names (``python``), or None."""
    cleaned = collapse_ws(text)
    for pattern, tag in _PROGRAMMING_TAGS:
        if pattern.search(cleaned):
            return tag
    return None


def programming_lesson_contract(text: str) -> str:
    """Return a hard tagged-fence requirement for a named programming topic."""
    tag = programming_tag(text)
    if tag is None:
        return ""
    return (
        "HARD PROGRAMMING-LESSON ACCEPTANCE CHECK (a lesson only; an outline of a whole "
        "language has no code): Before answering, verify the response contains "
        f"the literal opening fence ```{tag}, runnable code on following lines, and a closing ```. "
        "This is mandatory even when the lesson starts with a concept. An inline snippet, pseudo-code, or "
        "untagged fence fails the requested output. Keep the example short, then end with the "
        "lesson's `Your turn` ```quiz and the one-line preview of the next lesson."
    )


def is_learning_plan_request(text: str) -> bool:
    """True for bounded roadmaps/courses that should be delivered in full."""
    cleaned = straighten_apostrophes(collapse_ws(text))
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
    "- The last section is `### N. Your turn`, plus what it asks when it helps (code: `— predict "
    "the output`; history: `— check your understanding`). One practice question as a ```quiz "
    'fence, ```quiz alone on its line and the JSON on the next: {"label": "Exercise 1", '
    '"question": "What will this Python code print?", "code": "<the code it needs, lines joined '
    'with \\n; empty without code>", "options": ["...", "...", "...", "..."], "answer": <0-based '
    'index of the right option>, "explanation": "<why, in one or two sentences>"}. The app draws '
    "the label, question and code in one card; never repeat the code above it. For code prefer "
    '"predict the output" or "what should it return"; make the wrong options real mistakes. Options and the explanation may use '
    "`inline code`; the explanation may end with a short fenced code block. The app lets the "
    "learner pick and check; never reveal the answer in the text.\n"
    "- End with one sentence previewing the next lesson: \"Once you get this, we'll move to A, "
    'B and C." When they asked for one idea, the preview goes deeper into that same idea '
    "(for dictionaries: looping over one, nesting). No course outline, no table of "
    'contents, no "ready to continue?" question.\n'
    "- Unless emoji are off, one fitting emoji in the opening line (🐍 for Python) and 🎉 "
    "after a correct answer, no others."
)

_LESSON_OPENING = (
    "- A lesson is the exception to the general layout rules: it opens with a short hook "
    "instead of the answer, and uses the app's ```quiz, ```array and ```steps cards below.\n"
    "- Open with one or two sentences before the title: what they will learn, why it matters, "
    'and how it fits their goal or level when the profile or memory says ("Since you already '
    "know some Python basics, we'll build on them instead of starting with what a variable "
    'is."). Without that, never claim what they already know.\n'
)

# A whole subject is a map before it is a lesson: "teach me Python" gets the
# topics in order and one question; "teach me Python dictionaries" gets the
# lesson. The model judges the size, in any subject and language.
_SUBJECT_OUTLINE = (
    'First check memory: if it says they are already learning this subject ("Learning '
    'Python: reached Lesson 3, Dictionaries ... Covered: ...") reply with only two lines '
    "and no list: where they got to, then one question offering the next topic after the "
    'last one covered or a fresh start ("Last time we got to dictionaries. Pick up with '
    'functions, or start over?"). Otherwise judge the size of what they asked for.\n'
    "- A whole subject (Python, English, cooking, calculus, guitar, chemistry): do not teach "
    "yet. Reply with one sentence on what it opens up for them, then a numbered list of 5-8 "
    "topics in the order to learn them, each a **bold name** and a few words on what it "
    "lets them do, then one short question: where they are and where to start (for "
    'example "New to it, or do you know some already? Pick a number, or tell me what you '
    'want to make with it."). Tailor the list to a level or goal they or the profile or '
    "memory already gave. No lesson title, no code, no quiz, no headings; under 150 words.\n"
    "- One idea, skill, rule or dish (Python dictionaries, the present perfect, derivatives, "
    "knife skills, an omelette): teach exactly that and nothing past it.\n"
)

TEACHING_HINT = (
    "The user wants to learn something. "
    + _SUBJECT_OUTLINE
    + "For one idea, teach Lesson 1 now, complete, in this shape:\n"
    + _LESSON_OPENING
    + "- Start where they are: skip what they already know, and tie the example to their "
    "goal.\n" + _LESSON_SHAPE
)

# "Help me understand two sum", or stuck on a topic ("I don't understand recursion",
# stuck.py): one idea, explained in full now, building to the answer in one reply.
_WALKTHROUGH = re.compile(
    r"(?:\bhelp\s+me\s+understand|\bwalk\s+me\s+through|\bbreak\s+down)\s+"
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
    cleaned = straighten_apostrophes(collapse_ws(text))
    if not cleaned or len(cleaned) > 400:
        return False
    match = _WALKTHROUGH.search(cleaned)
    if match is None:
        return stuck_on_a_topic(cleaned) and not _PROCEDURE.search(cleaned)
    rest = cleaned[match.start() :]
    first_object = rest.split()[3:4] if rest.lower().startswith("walk me through") else []
    if first_object and _TASK_OBJECT.fullmatch(first_object[0]):
        return False
    return not (_PROCEDURE.search(cleaned) or re.search(r"\bhow\s+(?:to|do\s+i)\b", rest, re.I))


def is_teaching_request(text: str) -> bool:
    """True for interactive tutoring, not a procedure or full learning roadmap."""
    cleaned = straighten_apostrophes(collapse_ws(text))
    if not cleaned or len(cleaned) > 400:
        return False
    if not _TEACH_TURN.search(cleaned):
        return False
    if is_learning_plan_request(cleaned):
        return False
    # "Teach me by asking questions" says how, not what: no lesson yet.
    if is_standing_preference(cleaned):
        return False
    return not _asks_for_a_procedure(cleaned)


# How the user wants to be taught or answered from now on, with no question of
# its own yet: "When teaching me, explain one concept at a time…", "From now on,
# use examples", "I learn best by doing", "Don't give me the answer, give hints".
# Read sentence by sentence on the collapsed, lower-cased text.
_PREF_LEAD = (
    r"^(?:(?:ok(?:ay)?|hey|hi|hello|so|also|and|btw|one\s+more\s+thing|quick\s+note|note)"
    r"[,!:.]?\s+)?(?:please\s+)?"
)
# What an instruction about replies starts with.
_PREF_DO = (
    r"(?:(?:please|just|only)\s+)?(?:(?:always|never|don't|do\s+not)\s+)?"
    r"(?:explain|teach|tutor|give|show|use|ask|quiz|test|answer|reply|respond|keep|start|begin|"
    r"end|finish|break|walk|include|add|check|let\s+me|make|write|focus|avoid|stop|wait|pause|"
    r"stick|limit|define|summari[sz]e|repeat|correct|challenge|guide|offer|provide|format|skip|"
    r"number|label|cite|speak|talk|tell|go\s+(?:one|step|slow|slowly|through|over)|"
    r"be\s+(?:more|less|concise|brief|direct|honest|clear|patient|simple|short|detailed|blunt|"
    r"gentle|critical|thorough|specific|shorter|longer|simpler|clearer))\b"
)
_PREF_SENTENCE: tuple[re.Pattern[str], ...] = (
    # "When teaching me, …" / "When you explain things to me, …"
    re.compile(
        _PREF_LEAD
        + r"when(?:ever)?\s+(?:you(?:'re|\s+are)?\s+)?(?:teach|teaching|tutor|tutoring|explain|"
        r"explaining|help|helping|answer|answering|reply|replying|respond|responding|show|showing|"
        r"giv(?:e|ing))\s+(?:me|us|things|stuff|concepts|topics|something|anything)\b"
        r"(?:\s*,\s*|(?:\s+[\w']+){0,3}\s*,\s*|\s+)"
        r"(?:" + _PREF_DO + r"|i\s+(?:prefer|like|love|want|need|learn)\b|"
        r"you\s+(?:should|must|can|could)\b|(?:can|could|would|will)\s+you\b|try\s+to\b|"
        r"make\s+sure\b)"
    ),
    # "When I ask you for code, always add comments"
    re.compile(
        _PREF_LEAD + r"when(?:ever)?\s+i\s+ask\s+(?:you\s+)?(?:for|about|to|a|an|anything|"
        r"something|questions?)\b[^,.;?!]{0,60},\s*" + _PREF_DO
    ),
    # "From now on, …" / "Going forward, your answers should …"
    re.compile(
        _PREF_LEAD + r"(?:from\s+now\s+on|going\s+forward|moving\s+forward|from\s+here\s+on"
        r"(?:\s+out)?|in\s+(?:the\s+)?future|for\s+future\s+(?:answers|replies|lessons|chats|"
        r"questions))\s*,?\s+(?:(?:you(?:'ll|\s+will|\s+should|\s+must|\s+can)?|your\s+"
        r"(?:answers|replies|responses|explanations|lessons|examples)\s+(?:should|must|"
        r"need\s+to|will)|i\s+(?:want|need|'d\s+like|would\s+like)\s+you\s+to)\s+)?" + _PREF_DO
    ),
    # "Use simple words from now on."
    re.compile(
        _PREF_LEAD + _PREF_DO + r"[^.?!]{0,160}\b(?:from\s+now\s+on|going\s+forward|"
        r"from\s+here\s+on(?:\s+out)?|in\s+(?:the\s+)?future)\s*[.!]?$"
    ),
    # "Always explain …" / "Can you always give examples?"
    re.compile(
        _PREF_LEAD + r"(?:(?:can|could|would|will)\s+you\s+(?:please\s+)?|i\s+(?:want|need|'d\s+"
        r"like|would\s+like)\s+you\s+to\s+)?(?:always|never)\s+(?:please\s+)?(?:explain|teach|"
        r"give|show|use|ask|quiz|test|answer|reply|respond|include|start|begin|end|break|walk|"
        r"check|define|summari[sz]e|cite|add|keep|write|tell|go\s+(?:one|step|slow|slowly|"
        r"through|over)|be\s+(?:more|less|concise|brief|direct|honest|clear|patient|simple|"
        r"short|detailed|blunt|gentle|critical|thorough|specific|shorter|simpler|clearer))\b"
    ),
    # "I want you to explain one concept at a time"
    re.compile(
        _PREF_LEAD + r"i\s+(?:want|need|'d\s+like|would\s+like)\s+you\s+to\s+(?:always\s+|only\s+)?"
        r"(?:explain|teach)\s+(?:me\s+)?(?:things\s+|concepts\s+|everything\s+)?(?:one\s+"
        r"(?:concept|thing|step|idea|topic)\s+at\s+a\s+time|step\s+by\s+step|slowly|simply|"
        r"with\s+(?:examples|analogies)|using\s+examples|like\s+(?:a|i'm|im))\b"
    ),
    # "I learn best by doing" / "I'm a visual learner"
    re.compile(_PREF_LEAD + r"i\s+learn\s+(?:best|better|most|faster|more\s+easily|well)\b"),
    re.compile(
        _PREF_LEAD + r"i(?:'m|\s+am)\s+an?\s+(?:visual|hands[- ]on|auditory|kinesthetic|"
        r"practical|slow|fast|reading)\s+learner\b"
    ),
    re.compile(
        _PREF_LEAD + r"i\s+(?:prefer|like|love|want|need)\s+to\s+(?:learn|be\s+taught|study)\s+"
        r"(?:by|with|through|using|one|step|slowly|in\s+small|from\s+examples)\b"
    ),
    re.compile(
        _PREF_LEAD + r"i\s+(?:prefer|like|love|need|want)\s+(?:it\s+)?when\s+you\s+(?:explain|"
        r"teach|give|use|show|ask|quiz|test|keep|break|walk|go|start|include|check)\b"
    ),
    re.compile(
        _PREF_LEAD + r"i\s+(?:prefer|like|want|need)\s+(?:short|shorter|brief|briefer|concise|"
        r"detailed|simple|simpler|step[- ]by[- ]step|practical|real[- ]world|lots\s+of|more|"
        r"fewer|less|plain|clear)\s+(?:answers|replies|responses|explanations|examples|"
        r"exercises|lessons|steps|hints|analogies|language|words)\b(?!\s+(?:of|about|on)\b)"
    ),
    # "Teach me by asking questions" / "teach me one concept at a time"
    re.compile(
        _PREF_LEAD + r"(?:(?:can|could|would|will)\s+you\s+)?teach\s+me\s+(?:by|using|with|"
        r"through|via|one\s+(?:concept|thing|step|idea|topic|lesson)\s+at\s+a\s+time|step\s+by\s+"
        r"step|slowly|in\s+small\s+steps|like\s+(?:a|i'm|im|i\s+am))\b"
    ),
    # "Don't give me the answer, give hints" / "Only give me hints"
    re.compile(
        _PREF_LEAD + r"(?:just\s+)?(?:don't|do\s+not|never|stop)\s+(?:just\s+)?(?:give|giving|"
        r"tell|telling|show|showing)\s+me\s+(?:the\s+)?(?:full\s+|final\s+|whole\s+)?"
        r"(?:answers?|solutions?)\b"
    ),
    re.compile(
        _PREF_LEAD + r"(?:just\s+|only\s+)?give\s+me\s+(?:only\s+)?(?:hints|clues|a\s+hint|"
        r"nudges)\s+(?:instead|first|rather|not|only)\b"
    ),
    re.compile(_PREF_LEAD + r"(?:only\s+(?:give\s+me\s+)?hints|hints?\s+only)\b"),
)
# A reminder ("always remind me to drink water"), a memory command ("keep in
# mind that I'm vegetarian") or a problem to work on is not a preference about
# replies.
_PREF_NOT = re.compile(
    r"\b(?:remind|reminders?|alarm|notify|notifications?|wake\s+me|ping\s+me|alert\s+me|"
    r"remember|forget|keep\s+in\s+mind)\b|\d\s*[-+*/=^×÷]\s*\d|=|```",
    re.IGNORECASE,
)
# A second sentence that asks for the topic now: "Teach me Python." / "Let's start."
_PREF_TOPIC_NOW = re.compile(
    r"\blet'?s\s+(?:start|begin|learn|study|do|go|talk)\b|\bstart\s+with\s+(?!an?\s)"
    r"|\bi\s+(?:want|need|'d\s+like|would\s+like)\s+to\s+(?:learn|know|understand|study)\b"
    r"|\b(?:topic|subject)\s+is\b"
)
# "Teach me by examples about cooking" names a topic after all.
_PREF_NAMES_TOPIC = re.compile(r"\b(?:how\s+to|how\s+do|about|what\s+is|what\s+are)\b|:\s*\S")


def _preference_sentence(sentence: str) -> bool:
    if not any(pattern.search(sentence) for pattern in _PREF_SENTENCE):
        return False
    teach_by = re.search(r"\bteach\s+me\s+(?:by|using|with|through|via|like)\b", sentence)
    return not (teach_by and _PREF_NAMES_TOPIC.search(sentence[teach_by.end() :]))


def is_standing_preference(text: str) -> bool:
    """True when the user says how to teach or answer them from now on, and asks nothing yet.

    "When teaching me yesterday you…", "from now on I'll wake at 6" and "always
    remind me to drink water" are not: a memory, a plan of their own, a reminder.
    """
    cleaned = collapse_ws(text or "").replace("’", "'").casefold()
    if not cleaned or len(cleaned) > 400 or _PREF_NOT.search(cleaned):
        return False
    sentences = [part for part in re.split(r"(?<=[.!?])\s", cleaned) if part.strip()]
    found = False
    for sentence in sentences:
        if _preference_sentence(sentence):
            found = True
            continue
        # Any other sentence is context; a question or a topic makes it a request.
        if "?" in sentence or _PREF_TOPIC_NOW.search(sentence) or _TEACH_TURN.search(sentence):
            return False
    return found


STANDING_PREFERENCE_HINT = (
    "The user is telling you how to teach or answer them from now on; there is no question "
    "to answer yet. Do not start a lesson, answer a topic, or mention photos, images or "
    "files. Reply with one or two sentences agreeing, then a short bullet list restating "
    "what you will do in their terms (for example: one concept at a time; a practical "
    "example for each; a short exercise for them to solve before moving on), then one "
    "question asking what they want to learn first. If this chat already has a topic or "
    "lesson, offer to continue it that way instead. For a preference about answers rather "
    "than teaching (shorter replies, no emoji), one sentence is enough. Keep to it in later "
    "replies."
)


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
