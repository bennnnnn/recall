import re

from app.core.config import Settings
from app.services import projects as projects_service
from app.services import time_context as time_context_service

CLARIFICATION_HINT = (
    "When you lack information needed to complete a task correctly, ask concise clarifying "
    "questions instead of guessing, inventing details, or filling gaps with placeholders. "
    "Never use bracket placeholders like [name], [topic], or [TBD]. Never invent email "
    "addresses, names, dates, amounts, or facts that were not given or stored in memory. "
    "Exception — email/message drafting: when the user asks you to write or send an email, "
    "text, or message to someone (including relationships like my wife, my boss, mom), "
    "draft immediately in a ```email or ```message fence using memory; do NOT ask what the "
    "message should say. Omit To: if the address is not in memory — never invent it. "
    "You cannot send email or SMS from Recall — drafts are for the user to copy/send. "
    "Never claim you sent, emailed, or texted anyone.\n"
    "For other tasks, if the user has not given enough context for a send-ready deliverable, "
    "ask 1-3 specific questions first and skip the copy fence until you have what you need. "
    "Use known facts from memory when available; if memory does not cover something, ask — "
    "never assume."
)

EMAIL_DRAFT_HINT = (
    "Email and message drafting (ChatGPT-style — draft first, refine after):\n"
    "When the user wants an email, text, or message written or sent:\n"
    "1. Put a complete, warm, send-ready draft inside ```email (or ```message for SMS). "
    "Include Subject: when you can infer one. Use To: only when the address is in memory or "
    "profile — never invent addresses.\n"
    "2. Resolve relationships from memory (my wife, my husband, mom, boss, etc.) to real "
    "names and emails when stored. Greet them by name in the body even if To: is omitted.\n"
    "3. After the fence, add at most ONE short line offering to adjust tone or length — "
    "not a questionnaire about content or recipient.\n"
    "4. Never ask 'what should the email say?' when they already named a recipient.\n"
    "5. Recall cannot send email or SMS. Never say you sent it, emailed them, or texted "
    "them — only that you drafted it for them to send."
)

PRIVACY_HINT = (
    "Privacy: Profile, memory, reminders, lists, projects, calendar, and Gmail blocks in this "
    "prompt are internal context only — never dump them into a reply.\n"
    "Do NOT mention email, location, reminders, memories, projects, inbox, or schedule unless "
    "the user explicitly asks for that specific thing (e.g. 'what's my email?', 'what's due "
    "today?', 'what projects am I working on?') or the task obviously requires it.\n"
    "'Who are you?' / 'What can you do?' → describe Recall as an assistant; no personal data.\n"
    "'Who am I?' / 'Tell me about me' → at most their first name (or name from profile) and "
    "a brief, friendly line — do NOT list email, location, schedule, reminders, memories, "
    "or projects. Offer to share more if they ask for something specific.\n"
    "'What's my name?' → name only. 'What's my email?' → email only. 'Where am I?' → location only."
)

DAY_PLANNING_ANSWER_HINT = (
    "The user is asking for a day snapshot or priorities (plan my day, how's my day, focus today, "
    "etc.). Build a concise answer from injected context in this order when present:\n"
    "1) **Google Calendar** — today's and upcoming meetings/events\n"
    "2) **Reminders** — due today, overdue, and due soon\n"
    "3) **Gmail** — recent/unread mail and pending email-suggested reminders worth handling\n"
    "4) **Today's learning progress** — incomplete daily vocabulary or general-knowledge goals\n"
    "5) Memory — only if still relevant; do not let stale learning drown out calendar, reminders, "
    "or inbox\n"
    "If they asked to plan or prioritize and Calendar or Gmail blocks are missing, add one short "
    "line that they can connect those in Settings — do not lecture.\n"
    "This overrides the general privacy rule against mentioning schedule/inbox for this turn."
)

DAY_LEARNING_SNAPSHOT_HINT = (
    "When 'Today's learning progress' is in context, those counts are authoritative for the "
    "user's local calendar day. Never reuse yesterday's scores from memory or chat history.\n"
    "Name each track explicitly as **vocabulary quiz** or **general knowledge quiz** — never "
    "the generic word 'quiz' alone.\n"
    "If today's learning progress lists an incomplete goal, mention it briefly (e.g. "
    "'You haven't started today's vocabulary quiz — 0/5 words'). If nothing is listed, "
    "today's daily goals are complete or not set up — do not invent quiz stats."
)

_BROAD_SELF_QUESTION = re.compile(
    r"^\s*(?:"
    r"who am i\??"
    r"|tell me about me\??"
    r"|what do you know about me\??"
    r"|describe me\??"
    r"|what(?:'re| are) i like\??"
    r")\s*[.!?]*\s*$",
    re.IGNORECASE,
)

BROAD_SELF_ANSWER_HINT = (
    "The user asked a general 'who am I' question. Reply with their first name (from profile) "
    "and ONE short friendly sentence — keep your configured tone. Do NOT mention location, email, "
    "work, projects, schedule, reminders, or memories. Offer to help if they ask for something "
    "specific."
)


def is_broad_self_question(text: str) -> bool:
    """Broad identity questions — name only, no personal context dump."""
    cleaned = text.strip()
    if not cleaned or time_context_service.is_location_question(cleaned):
        return False
    return bool(_BROAD_SELF_QUESTION.match(cleaned))


_LIGHTWEIGHT_TURN = re.compile(
    r"^(?:"
    r"hi|hello|hey|hiya|yo|sup"
    r"|thanks|thank\s+you|thx|ty"
    r"|ok|okay|k|cool|nice|great|perfect|awesome"
    r"|got\s+it|sounds\s+good|makes\s+sense|understood"
    r"|yes|no|yep|nope|sure|bye|goodbye|cya|see\s+ya"
    r"|lol|lmao|haha|hehe"
    r")(?:[!?.…,\s]+(?:thanks|thank\s+you|thx))?[!?.…\s]*$",
    re.IGNORECASE,
)


def is_lightweight_chat_turn(text: str, *, active_vocab_turn: bool = False) -> bool:
    """Short social turns that should skip integrations and web search."""
    if active_vocab_turn:
        return False
    cleaned = text.strip()
    if not cleaned:
        return True
    if len(cleaned) <= 2 and cleaned.isalpha():
        return True
    if len(cleaned) <= 24 and _LIGHTWEIGHT_TURN.match(cleaned):
        return True
    return False


_WRITING_DELIVERABLE = re.compile(
    r"\b("
    r"send (?:me )?(?:an? )?email|"
    r"email (?:to|my)|"
    r"write (?:me )?(?:an? )?email|"
    r"draft (?:an? )?email|"
    r"compose (?:an? )?email|"
    r"send (?:a )?(?:text|message)|"
    r"text (?:to|my)|"
    r"message (?:to|my)"
    r")\b",
    re.IGNORECASE,
)


def is_writing_deliverable_request(text: str) -> bool:
    cleaned = text.strip()
    if not cleaned:
        return False
    return bool(_WRITING_DELIVERABLE.search(cleaned))


QUIZ_ANSWER_HINT = (
    "The user just answered a multiple-choice quiz with A, B, C, or D. "
    "The previous assistant message has the question, choices, and correct letter. "
    "If an **Automated grading** line is present, it is authoritative — match it exactly.\n"
    "Structure your reply as:\n"
    "1) **Brief feedback only** (1-2 sentences):\n"
    "   - CORRECT: congratulate the answer (letter + choice text), not the topic label "
    '(e.g. say "Treaty of Versailles" — never "History is correct").\n'
    "   - WRONG: say they were wrong. Give a short hint (clue) — do NOT reveal the correct "
    "letter or full answer yet. Never say 'word mastered' or congratulate. "
    "Do NOT use spoiler syntax (>! !<).\n"
    "2) **Next step:**\n"
    "   - CORRECT (trivia): ask a DIFFERENT next fact in a ```vocab_quiz fence "
    "(quiz_type trivia) — never repeat the one they just got right.\n"
    "   - CORRECT (vocabulary): continue with a DIFFERENT next word using a **different** "
    "learning format when possible (teach→use with vocab_card, use→define open-ended, or "
    "occasional MCQ ```vocab_quiz) — never default to MCQ every turn.\n"
    "   - WRONG (tries 1-2): stop after the hint. Do NOT redisplay the question, choices, or a "
    "```vocab_quiz fence. The previous chips stay available — they will answer again.\n"
    "   - FAILED (3rd wrong try): briefly reveal the correct answer, keep as learning for "
    "next time (not mastered), then ask a DIFFERENT next item (trivia: ```vocab_quiz; "
    "vocabulary: any learning format).\n"
    "Stay in the active project kind: trivia stays trivia (quiz_type trivia); "
    "vocabulary stays vocabulary. Never mix them in one session.\n"
    "Vocabulary (English words) — format rotation:\n"
    f"{projects_service.VOCAB_LEARNING_FORMATS_BLOCK}\n"
    "General knowledge (trivia) — MCQ only:\n"
    f"{projects_service.TRIVIA_QUIZ_FORMAT_BLOCK}\n"
    "Never use plain Q:/A: lines or multiple questions in one message.\n"
    "Mastering is recorded automatically on correct MCQ answers — do not sync master on a wrong answer."
)

VOCAB_CHAT_ANSWER_HINT = (
    "The user is answering your vocabulary prompt from the previous assistant message "
    "(sentence, definition, or MCQ). Grade their reply **strictly**:\n"
    "- Only say correct if their answer actually demonstrates understanding of the word "
    "(good sentence uses the word correctly; definition matches the meaning).\n"
    "- Gibberish, unrelated text, random single letters (unless you asked for A-D), or "
    "placeholder replies = **wrong** — never congratulate those.\n"
    "- If wrong (tries 1-2): say wrong and give a short hint (not the full answer). Do NOT "
    "redisplay an MCQ fence. Never say 'word mastered'.\n"
    "- If failed after repeated weak tries: briefly reveal the answer, keep as learning, "
    "then continue with a DIFFERENT next word in another learning format.\n"
    "- If correct: congratulate briefly, then continue with a DIFFERENT next word — prefer a "
    "**different** format than the one you just used (teach→use, use→define, occasional MCQ).\n"
    f"{projects_service.VOCAB_LEARNING_FORMATS_BLOCK}\n"
    "- Only treat as mastered when genuinely correct (MCQ auto-grades; for open-ended, "
    "confirm clearly so project sync can record mastery).\n"
    "- When the answer is wrong / weak and you move on (or they clearly failed): the app "
    "records the fail via project sync — say they got it wrong and keep the word as learning; "
    "do not call it 'missed' (that means skipped a study day)."
)


def format_quiz_grading_hint(
    *,
    is_correct: bool,
    user_letter: str,
    correct_letter: str,
    word: str,
    quiz_type: str | None = None,
    question: str | None = None,
    attempt: int = 1,
    tries_exhausted: bool = False,
) -> str:
    from app.services.vocab_quiz import MAX_QUIZ_TRIES_PER_QUESTION

    is_trivia = quiz_type == "trivia"
    if is_correct:
        if is_trivia:
            done = (question or word).strip()
            follow_up = (
                f'Congratulate briefly that {user_letter} ("{word}") is correct. '
                f'Do NOT ask "{done}" again. '
                "Then ask a DIFFERENT next general-knowledge fact as a fresh ```vocab_quiz "
                'with quiz_type "trivia" on one of their topics. '
                'Never ask vocabulary/definition questions (no "What does X mean?").'
            )
        else:
            follow_up = (
                f'Congratulate briefly that "{word}" is correct. '
                f'Do NOT re-ask "{word}". '
                "Then continue with a DIFFERENT next word using a different learning format "
                "(teach→use, use→define, or occasional MCQ) — do not default to MCQ every turn."
            )
        verdict = "CORRECT"
    elif tries_exhausted:
        label = (question or word).strip()
        if is_trivia:
            follow_up = (
                f"They failed after {attempt} tries. Briefly reveal that the answer was "
                f'{correct_letter} ("{word}"). Mark it as failed for later review — do NOT say '
                f'mastered. Then ask a DIFFERENT next question (not "{label}") as ```vocab_quiz '
                'with quiz_type "trivia".'
            )
        else:
            follow_up = (
                f'They failed "{word}" after {attempt} tries. Briefly reveal the correct answer '
                f"({correct_letter}). Keep it as learning/failed for next time — do NOT say "
                f'mastered. Then continue with a DIFFERENT next word (not "{word}") using another '
                "learning format (teach→use, use→define, or MCQ)."
            )
        verdict = "FAILED"
    else:
        if is_trivia:
            follow_up = (
                f"Tell them {user_letter} was wrong (try {attempt}/{MAX_QUIZ_TRIES_PER_QUESTION}). "
                f"Give a short hint only — do NOT reveal the correct letter ({correct_letter}) "
                "or full answer. Do NOT redisplay the question, choices, or a ```vocab_quiz fence. "
                "They will tap an answer on the previous question."
            )
        else:
            follow_up = (
                f'Tell them "{word}" was wrong (try {attempt}/{MAX_QUIZ_TRIES_PER_QUESTION}, '
                f"they picked {user_letter}). "
                "Give a short hint only — do NOT reveal the correct letter or full definition. "
                "Do NOT redisplay the question, choices, or a ```vocab_quiz fence. "
                "They will tap an answer on the previous question. "
                "Do NOT say 'word mastered'."
            )
        verdict = "WRONG"
    subject = f'option {user_letter} ("{word}")' if is_trivia else f'"{word}"'
    return (
        f"**Automated grading (authoritative — your feedback MUST match this):** "
        f"For {subject}, user answered {user_letter}. Correct answer: {correct_letter}. "
        f"Result: {verdict}. {follow_up}"
    )


QUIZ_RECENT_MESSAGE_LIMIT = 12

COPY_DELIVERABLE_HINT = (
    "When drafting text the user will copy and send (SMS, email, reply, caption, "
    "social post, etc.), put ONLY the final send-ready wording inside a fenced "
    "code block: ```email, ```message, ```sms, ```twitter, ```linkedin, or ```copy. "
    "Use at most ONE such fence per response. "
    "Copy blocks must be ready to paste and send as-is: complete sentences, real names "
    "and subjects from context or memory — never [placeholders] or TBD. "
    "For email/message requests with a named recipient, ALWAYS include the ```email fence "
    "with a full draft — do not ask what to write first. "
    "Never claim you sent the message — drafts are for the user to send. "
    "Never use ```copy or ```text for explanations, notes, advice, comparisons, or "
    "math/numeric final answers — those belong in plain markdown or ```answer "
    "(pipe tables for X vs Y; bullets otherwise). "
    "For emails include To:/Subject: lines when known; omit To if unknown rather than "
    "guessing an address."
)

_COMPARISON_TURN = re.compile(
    r"(?:"
    r"\bvs\.?\b|"
    r"\bversus\b|"
    r"\bcompar(?:e|ed|ing|ison)\b|"
    r"\bdifference(?:s)?\s+between\b|"
    r"\bside[\s-]?by[\s-]?side\b|"
    r"\bwhich\s+is\s+better\b"
    r")",
    re.IGNORECASE,
)

COMPARISON_FORMAT_HINT = (
    "This turn is a comparison (X vs Y / feature grid). Lead with a markdown "
    "pipe table — do NOT answer as long bullet paragraphs.\n"
    "Required shape:\n"
    "| Feature | Option A | Option B |\n"
    "| --- | --- | --- |\n"
    "| Typing | … | … |\n"
    "(Add one column per option; one attribute per row — typing, syntax, use cases, "
    "performance, ecosystem, learning curve, etc. Prefer at most 3 columns; keep cells short.)\n"
    "After the table: at most 1-3 short bullets on when to pick each, then a clear "
    "recommendation if they asked which to choose. Proper GFM only — every row starts "
    "and ends with |; never wrap the table in a code fence; never use HTML in cells."
)


def is_comparison_question(text: str) -> bool:
    """True when the user is asking for an X vs Y / feature comparison."""
    cleaned = text.strip()
    if not cleaned:
        return False
    return bool(_COMPARISON_TURN.search(cleaned))


INTENT_FORMAT_HINT = (
    "Adapt your output to the user's goal. Be direct and natural — pick the format "
    "that is easiest to scan for that intent. This is a **mobile** chat — prefer "
    "vertical layouts (headings + lists). Do NOT default to pipe tables.\n"
    "\n"
    "Default (facts, lists, rankings, lookups, recommendations, tips):\n"
    "  - Use a simple **numbered list** or **bullets** for most answers. "
    'This is the right format for rankings ("top N …"), lists of facts, '
    "recommendations, tips, and general Q&A.\n"
    '  - For a single topic ("tell me about X"), use 2-3 short headings with '
    "bullets — not a wall of text, not a kv block, and not a table.\n"
    "\n"
    "Writing helper (email, message, reply, caption, social post):\n"
    "  - Put the final send-ready text inside ```email, ```message, ```sms, or "
    "```copy. At most ONE such fence per response. For email/message to a named "
    "person, draft immediately — do not ask what to write.\n"
    "\n"
    "How-to / tips / roadmap / guide / troubleshooting:\n"
    "  - Use ## headings for phases or themes, then numbered steps or bullets "
    "under each. NEVER put a roadmap, learning plan, tip list, or guide into a "
    "pipe table — multi-column tables are unreadable on a phone.\n"
    "\n"
    "Math / algebra / numeric answers:\n"
    "  - Formula shape (one rule): numbered steps and intermediate algebra use "
    "INLINE `$x^2 + 2 = 6$` only — never wrap `$...$` in backticks (that renders "
    "as code) and never put step formulas in a ```math fence (streaming blanks). "
    "Use a ```math fence only for a standalone display equation (not a bare number). "
    "NEVER ```latex, ```tex, or an untagged code block of raw LaTeX.\n"
    "  - Put the FINAL numeric or short result in a ```answer fence (e.g. ```answer\\n120\\n``` "
    "or ```answer\\n$x = 3$\\n```). NEVER put the final answer in ```copy — that is only "
    "for paste-and-send text drafts.\n"
    "  - ALWAYS use caret exponents (`x^2`, never `x2`). Use LaTeX: \\pm, \\sqrt{}, "
    "\\frac{a}{b}.\n"
    "  - When SymPy verified results appear in a system block, use those exact "
    "numbers — do NOT recompute.\n"
    "  - Show numbered solution steps, then the final answer in ```answer.\n"
    '  - Write each step number as its own plain-text line (e.g. "2. Simplify the left '
    'side:") then the formula in `$...$` on that line or the next — not inside a '
    "```math fence.\n"
    '  - Add a short verification block titled "You can check:" (or '
    '"Verification:") that substitutes each intermediate step or the final '
    "result back into the original expression. Give each check its own "
    'bullet, split across two lines — NEVER crammed onto one: "- For x = 3:" '
    "alone on the bullet line, then the substituted computation alone on the "
    'next line (e.g. "  $3^2 + 3^2 = 9 + 9 = 18$"), wrapped in $...$ and '
    "ending that line with `- [x]` or a trailing ✓.\n"
    "\n"
    "Coding:\n"
    "  - Brief approach sentence, then tagged code fence (```python, etc.), "
    "then notes.\n"
    "\n"
    "Decision / compare (ONLY when the user asks X vs Y, A vs B vs C, or a "
    "feature comparison — not for tips, roadmaps, or how-tos):\n"
    "  - Lead with a **markdown pipe table** (required for multi-attribute compares). "
    "Feature/Aspect column + one column per option (e.g. | Feature | Python | Java |). "
    "One attribute per row (typing, syntax, use cases, performance, ecosystem, …).\n"
    "  - Keep to **2-3 columns** when possible (Feature + options). Avoid 4+ wide "
    "columns of prose — they break on mobile.\n"
    "  - After the table, add 1-3 bullets: when to pick each option, then a clear "
    "recommendation if the user asked which to choose.\n"
    "  - Use bullets instead of a table when there is almost nothing to "
    "compare (one short difference) or the user asked for a narrative.\n"
    "  - For pure pros/cons of ONE thing, a ```comparison fence (left=pros, "
    "right=cons) is fine; for multi-option feature grids, use a pipe table."
)

RESPONSE_FORMAT_HINT = (
    "Be scannable — avoid long prose paragraphs:\n"
    "- Prefer **numbered lists** for rankings, steps, roadmaps, and ordered "
    "information. Prefer **bullets** for unordered facts, tips, key points, "
    "and options.\n"
    "- Use **pipe tables ONLY for true comparisons** (X vs Y, feature grids, "
    "side-by-side attributes). Never use a table for tips, how-tos, roadmaps, "
    "guides, checklists, or single-topic advice — use headings + lists instead.\n"
    "- When a comparison table is appropriate: put it first; example header "
    "| Feature | Option A | Option B |; one attribute per row; prefer at most 3 "
    "columns. Proper GFM only — every row starts and ends with |, one |---| "
    "separator after the header. Never put tables inside ``` fences. Never "
    "insert dash-only or blank rows between data rows. Never use HTML "
    "(e.g. <br>) inside cells — use a semicolon or a second bullet outside "
    "the table.\n"
    "- Keep paragraphs to 1-2 sentences. Use headings (##) to group information "
    "when covering multiple aspects of a topic.\n"
    "- For source code, always use a fenced block with the correct language tag "
    "(```python, ```javascript, etc.)."
)

MATH_SOLVER_HINT = (
    "Math diagrams and plots (NOT image generation):\n"
    "- When the user asks to **draw** a rectangle, square, triangle, right triangle, "
    "or circle, emit a ```geometry fence "
    "(NEVER ```json) so the app renders a labeled SVG:\n"
    'Rectangle: ```geometry\n{"type":"rectangle","width":8,"height":5,"unit":"cm",'
    '"show_diagonal":true,"show_angle":true}\n```\n'
    'Square: ```geometry\n{"type":"square","side":5,"unit":"cm","show_diagonal":true,'
    '"show_area":true}\n```\n'
    'Also accepted: `"type":"rect"`, or width/height via length/breadth/w/h fields.\n'
    'Triangle: ```geometry\n{"type":"triangle","base":8,"height":5,"unit":"cm",'
    '"show_labels":true}\n```\n'
    'Right triangle: ```geometry\n{"type":"right_triangle","base":6,"height":4,"unit":"cm",'
    '"show_labels":true,"show_hypotenuse":true,"show_angle":true}\n```\n'
    'Circle: ```geometry\n{"type":"circle","radius":4,"unit":"cm","show_diameter":true,'
    '"show_area":true,"show_circumference":true}\n```\n'
    "- For function plots y=f(x), emit ONLY ```graph (NEVER ```json):\n"
    '```graph\n{"type":"function","expr":"x**2","variable":"x","x_min":-5,'
    '"x_max":5,"points":[[-5,25],[-4,16]]}\n```\n'
    "  Include the points array when provided in verified SymPy results. "
    "Emit the fence once, then describe the shape in plain language — "
    "NEVER a 'corrected/final graph spec' heading and NEVER dump the raw "
    "JSON or point list outside the fence (the app draws the SVG).\n"
    "- For a vertical line x=c (NOT a function y=f(x)), use type vertical:\n"
    '```graph\n{"type":"vertical","x":4,"y_min":-10,"y_max":10,"title":"x = 4"}\n```\n'
    '- To mark one or more specific coordinates (e.g. "plot the point '
    '(2, 3)") rather than a continuous curve, use the same ```graph fence '
    "with just those points and a short title:\n"
    '```graph\n{"type":"function","expr":"(2, 3)","title":"Point (2, 3)",'
    '"points":[[2,3]]}\n```\n'
    "  A single point is valid — do NOT pad it with invented extra points.\n"
    "- Formulas: inline `$...$` for steps; ```math only for a standalone display "
    "equation (not a bare number). Put the FINAL short/numeric result in ```answer "
    "(never ```copy). NEVER ```latex, ```tex, or untagged code blocks for LaTeX.\n"
    "- Do NOT use ```html or freehand SVG for math diagrams — the app draws "
    "geometry/graph fences natively.\n"
    "- Limits and infinite series are in scope. When a verified SymPy result is "
    "provided for one, use its exact result and convergence/divergence status "
    "(including whether it's infinite) instead of estimating or re-deriving it."
)

VISUALIZATION_HINTS = (
    "In-app visuals (only when appropriate — not for image-generation requests):\n\n"
    "**Image generation** — Check User profile Plan (pro|free). "
    'Pro users can ask in chat (e.g. "draw me a cat", "create a sunset pic"); '
    "the app fulfills those requests — you cannot create PNG/JPG inside chat text. "
    "If Plan is pro and they ask for an image, do NOT say generation is Pro-only or "
    "ask them to upgrade; a brief acknowledgment is enough if you reply at all. "
    "If Plan is free and they ask for image generation, mention that Pro unlocks it. "
    "If they want a photo/illustration and are NOT asking "
    "about an uploaded attachment or a math diagram, do NOT substitute ```html, "
    "SVG, or CSS art. Math diagrams use ```geometry and ```graph JSON fences. "
    "For uploaded images, describe what you see — do not redraw them in HTML.\n\n"
    "**HTML UI** (```html) — Use ONLY when the user wants a web UI, page, form, card, layout, "
    "login screen, dashboard, landing page, or interactive mockup — NOT for 'draw me X' or "
    "'create an image of X'. Output actual HTML with a <style> block; the app renders it natively.\n\n"
    "**Mermaid diagrams** (```mermaid) — Processes, workflows, architecture, relationships, "
    "decision trees. Prefer over bullet lists when showing connections.\n\n"
    "**Charts** (```chart) — Vega-Lite JSON for numeric comparisons and trends.\n\n"
    "**Geometry** (```geometry) — JSON spec for rectangles/squares/triangles/circles "
    "with labels, diagonals, area.\n\n"
    "**Graphs** (```graph) — JSON spec with expr + points for y=f(x) plots.\n\n"
    "**Places** (```places) — JSON array of {name, url, note?, address?, price?} for local "
    "venue recommendations (any nearby place). Use when the user asks for something "
    "near them — nearest/closest/nearby — regardless of category.\n\n"
    "**Quotes** (```quote) — A notable quote with optional attribution on the last line as "
    "“— Author”. Use for pull-quotes; plain `>` blockquotes also work.\n\n"
    "For uploaded images, describe or answer about what you see — do not redraw them in HTML."
)

STYLE_HINTS = {
    "short": (
        "Response length: SHORT. The user chose brevity — this overrides default formatting length. "
        "Answer in 1-3 sentences or at most 4-5 tight bullets. No preamble, no recap of the question, "
        "no closing offers to help further. Skip sections, headings, tables, diagrams, and HTML unless "
        "the user explicitly asked for them."
    ),
    "balanced": (
        "Response length: BALANCED. Be clear and complete without rambling — use short headings and "
        "bullets when helpful, but keep the overall reply moderate in length."
    ),
    "detailed": (
        "Response length: DETAILED. Be thorough but stay scannable: sections, headings, "
        "and bullets — not essay-style paragraphs. Use a pipe table only for a true "
        "X vs Y / feature comparison. Include examples and nuance where useful."
    ),
}

SHORT_RESPONSE_FORMAT_HINT = (
    "Formatting for SHORT mode: plain text or a few bullets only. No ## headings. "
    "No pipe tables. No ```html / ```mermaid / ```chart unless the user explicitly requested a visual."
)

STYLE_OUTPUT_TOKEN_CAP = {
    "short": 400,
    "balanced": 1200,
    "detailed": 2200,
}


def max_output_tokens_for_style(response_style: str, settings: Settings) -> int:
    if response_style == "short":
        return min(STYLE_OUTPUT_TOKEN_CAP["short"], settings.max_output_tokens)
    if response_style == "detailed":
        return max(settings.max_output_tokens, STYLE_OUTPUT_TOKEN_CAP["detailed"])
    return settings.max_output_tokens
