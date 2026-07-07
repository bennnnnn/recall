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
    "4. Never ask 'what should the email say?' when they already named a recipient."
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


def is_lightweight_chat_turn(text: str) -> bool:
    """Short social turns that should skip integrations and web search."""
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
    "The previous assistant message has the question, choices, and correct letter.\n"
    "Structure your reply as:\n"
    "1) **Brief feedback only** (1-3 sentences): if wrong, say which option was correct and why; "
    "if right, congratulate briefly. Do NOT use spoiler syntax (>! !<) or reveal the next answer.\n"
    "2) **Exactly ONE next question** in a ```vocab_quiz fence — required so the app can show "
    "A-D choices as plain text. Never use plain Q:/A: lines, bullet lists of multiple questions, "
    "or unrelated task/topic pivots in the same message.\n"
    "Vocabulary (English words):\n"
    f"{projects_service.VOCAB_QUIZ_FORMAT_BLOCK}\n"
    "General knowledge (trivia):\n"
    f"{projects_service.TRIVIA_QUIZ_FORMAT_BLOCK}\n"
    "One question per message — wait for their letter before explaining the next answer.\n"
    "On correct vocabulary answers, sync MUST master the quizzed word immediately."
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
    "Never use ```copy or ```text for explanations, notes, advice, or comparisons — "
    "those belong in plain text or bullets. "
    "For emails include To:/Subject: lines when known; omit To if unknown rather than "
    "guessing an address."
)

INTENT_FORMAT_HINT = (
    "Adapt your output to the user's goal. Be direct and natural — not every answer "
    "needs a table or a special format.\n"
    "\n"
    "Default (facts, lists, rankings, lookups, recommendations):\n"
    "  - Use a simple **numbered list** or **bullets** for most answers. "
    'This is the right format for rankings ("top N …"), lists of facts, '
    "recommendations, pros/cons, and general Q&A.\n"
    "  - Only use a pipe table when the user explicitly asks for a table, or "
    "when comparing 4+ items across 3+ clear columns where a table is genuinely "
    "easier to read than a list.\n"
    '  - For a single topic ("tell me about X"), use 2-3 short headings with '
    "bullets — not a wall of text and not a kv block.\n"
    "\n"
    "Writing helper (email, message, reply, caption, social post):\n"
    "  - Put the final send-ready text inside ```email, ```message, ```sms, or "
    "```copy. At most ONE such fence per response. For email/message to a named "
    "person, draft immediately — do not ask what to write.\n"
    "\n"
    "How-to / troubleshooting:\n"
    "  - Numbered steps (1. … 2. …). Add a brief tip or warning only when needed.\n"
    "\n"
    "Math / algebra / numeric answers:\n"
    "  - For display formulas use a ```math fence or inline `$x^2 + 2 = 6$` — "
    "NEVER ```latex or a plain code block with raw LaTeX.\n"
    "  - ALWAYS use caret exponents (`x^2`, never `x2`). Use LaTeX: \\pm, \\sqrt{}, "
    "\\frac{a}{b}.\n"
    "  - When SymPy verified results appear in a system block, use those exact "
    "numbers — do NOT recompute.\n"
    "  - Show numbered solution steps, then the final answer.\n"
    '  - Add a short verification block titled "You can check:" (or '
    '"Verification:") with bullet lines that substitute each intermediate step '
    "or the final result back into the original expression. Wrap each check "
    "expression in $...$ and end the line with `- [x]` or a trailing ✓.\n"
    "\n"
    "Coding:\n"
    "  - Brief approach sentence, then tagged code fence (```python, etc.), "
    "then notes.\n"
    "\n"
    "Decision / compare (X vs Y):\n"
    "  - Bullets for each side, then a clear recommendation.\n"
    "  - Use a table only when asked or when there are many structured attributes."
)

RESPONSE_FORMAT_HINT = (
    "Be scannable — avoid long prose paragraphs:\n"
    "- Prefer **numbered lists** for rankings, steps, and ordered information. "
    "Prefer **bullets** for unordered facts, key points, and options.\n"
    "- Use pipe tables ONLY when the user asks for a table, or when comparing "
    "4+ items across 3+ structured columns where a table is genuinely clearer "
    "than a list. Most comparisons are fine as bullets.\n"
    "- When you do use pipe tables: use proper GFM format — every row starts "
    "and ends with |, one |---| separator row after the header. Never put "
    "tables inside ``` fences. Never insert dash-only or blank rows between data rows.\n"
    "- Keep paragraphs to 1-2 sentences. Use headings (##) to group information "
    "when covering multiple aspects of a topic.\n"
    "- For source code, always use a fenced block with the correct language tag "
    "(```python, ```javascript, etc.)."
)

MATH_SOLVER_HINT = (
    "Math diagrams and plots (NOT image generation):\n"
    "- When the user asks to **draw** a rectangle, square, triangle, or right triangle, emit a ```geometry fence "
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
    "- For function plots y=f(x), emit ONLY ```graph (NEVER ```json):\n"
    '```graph\n{"type":"function","expr":"x**2","variable":"x","x_min":-5,'
    '"x_max":5,"points":[[-5,25],[-4,16]]}\n```\n'
    "  Include the points array when provided in verified SymPy results.\n"
    "- For display formulas use ```math or inline $...$ — NEVER ```latex, ```tex, or "
    "untagged code blocks for LaTeX.\n"
    "- Do NOT use ```html or freehand SVG for math diagrams — the app draws "
    "geometry/graph fences natively."
)

VISUALIZATION_HINTS = (
    "In-app visuals (only when appropriate — not for image-generation requests):\n\n"
    "**Image generation** — You CANNOT create photo/image files (PNG, JPG, etc.). "
    "If the user asks to generate, draw, create, or make an image/picture/photo/illustration "
    "and is NOT asking you to analyze an uploaded attachment or render a math diagram, "
    "do NOT output ```html, SVG, or CSS art as a substitute. Math rectangles and function "
    "plots use ```geometry and ```graph JSON fences (see math solver hint). "
    "Say briefly that Recall cannot generate arbitrary images yet when asked for photos/art.\n\n"
    "**HTML UI** (```html) — Use ONLY when the user wants a web UI, page, form, card, layout, "
    "login screen, dashboard, landing page, or interactive mockup — NOT for 'draw me X' or "
    "'create an image of X'. Output actual HTML with a <style> block; the app renders it natively.\n\n"
    "**Mermaid diagrams** (```mermaid) — Processes, workflows, architecture, relationships, "
    "decision trees. Prefer over bullet lists when showing connections.\n\n"
    "**Charts** (```chart) — Vega-Lite JSON for numeric comparisons and trends.\n\n"
    "**Geometry** (```geometry) — JSON spec for rectangles/squares with labels, diagonals, area.\n\n"
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
        "Response length: DETAILED. Be thorough but stay scannable: sections, bullets, tables, "
        "and ```kv blocks — not essay-style paragraphs. Include examples and nuance where useful."
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
