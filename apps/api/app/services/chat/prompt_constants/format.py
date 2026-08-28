"""Response-format, comparison, and length-style hints."""

import re

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
    "This turn is X vs Y. Layout (do not write a wall of prose):\n"
    "1. Lead with a GFM pipe table. Use their option names as columns. "
    "Cells are one short phrase. NEVER put source code, ``` fences, <br>, or HTML in a cell.\n"
    "| Area | First option | Second option |\n"
    "| --- | --- | --- |\n"
    "| Typing | Dynamically typed | Statically typed |\n"
    "2. AFTER the table, ### headings for the rows they asked about. Under each: "
    "1-2 sentences, then a tagged code fence per option (```python then ```java, "
    "or the languages they named) — those render as code cards. "
    "Do not dump code as indented prose.\n"
    "3. End with ### Which should a beginner choose? (or equivalent) and a short "
    "recommendation.\n"
    "Every table row starts and ends with |. Never wrap the table in a fence."
)


def is_comparison_question(text: str) -> bool:
    """True when the user is asking for an X vs Y / feature comparison."""
    cleaned = text.strip()
    if not cleaned:
        return False
    return bool(_COMPARISON_TURN.search(cleaned))


_CHART_TURN = re.compile(
    r"(?:"
    r"\b(?:bar|line|pie|area|scatter|donut)\s+charts?\b|"
    r"\bhistograms?\b|"
    r"\bvega(?:-lite)?\b|"
    r"```(?:chart|vega|vega-lite|plot)\b|"
    r"\b(?:make|draw|show|create|render|plot)\s+a\s+"
    r"(?:bar\s+|line\s+|pie\s+|area\s+)?charts?\b"
    r")",
    re.IGNORECASE,
)

CHART_FORMAT_HINT = (
    "This turn is a numeric chart. Recall renders Vega-Lite in the bubble — "
    "you CAN draw this chart. NEVER say you cannot draw / cannot literally "
    "draw a chart. NEVER substitute a markdown table, mermaid, or ASCII bars.\n"
    "Lead with a ```chart fence of Vega-Lite JSON. At most one short sentence, "
    "then the fence. No joke setup.\n"
    "Use the numbers they gave as data.values. First key must be "
    '"$schema": "https://vega.github.io/schema/vega-lite/v5.json". '
    "Prefer mark bar/line as asked.\n"
    "Example shape only:\n"
    "```chart\n"
    '{"$schema":"https://vega.github.io/schema/vega-lite/v5.json",'
    '"description":"A simple bar chart","data":{"values":['
    '{"month":"Jan","inches":5.7},{"month":"Feb","inches":3.5}]},'
    '"mark":"bar","encoding":{"x":{"field":"month","type":"nominal"},'
    '"y":{"field":"inches","type":"quantitative"}}}\n'
    "```"
)


def is_chart_question(text: str) -> bool:
    """True when the user asked for a numeric chart (Vega), not a flowchart."""
    cleaned = text.strip()
    if not cleaned:
        return False
    return bool(_CHART_TURN.search(cleaned))


# One layout contract. The model writes Markdown; Recall upgrades presentation.
# Do NOT teach tip / steps / comparison / details / answer as model-chosen UI —
# those cards still render if an old message has the fence.
FORMAT_CONTRACT = (
    "This is a conversational chat. Write normal Markdown — headings, lists, "
    "tables, and blockquotes. Do not invent custom fence names for layout.\n"
    "\n"
    "Default (facts, lists, rankings, lookups, recommendations, tips, how-tos):\n"
    "  - Numbered list or bullets. This is the right format for rankings "
    '("top N …"), tips, roadmaps, troubleshooting, and general Q&A.\n'
    '  - For a single topic ("tell me about X"), use 2-3 short headings with '
    "bullets — not a wall of text and not a table.\n"
    "  - How-to / roadmap / guide: ## headings for phases, numbered steps under "
    "each. NEVER put a roadmap, learning plan, tip list, or how-to into a "
    "pipe table — those belong as lists, not grids.\n"
    "  - Callouts: a blockquote starting with Tip: / Note: / Warning: "
    "(plain `>`). Not a fence.\n"
    "\n"
    "Writing helper (email, message, reply, caption, social post):\n"
    "  - Put the final send-ready text inside ```email, ```message, ```sms, or "
    "```copy. At most ONE such fence per response. For email/message to a named "
    "person, draft immediately — do not ask what to write.\n"
    "\n"
    "Coding:\n"
    "  - Brief approach sentence, then a tagged code fence (```python, "
    "```javascript, etc.), then notes. Never put source code in an untagged "
    "fence.\n"
    "\n"
    "Decision / compare (ONLY when the user asks X vs Y, A vs B vs C, or a "
    "feature comparison — not for tips, roadmaps, or how-tos):\n"
    "  - Lead with a **markdown pipe table** (Feature | A | B). One attribute "
    "per row. Cells are one short phrase.\n"
    "  - NEVER put source code, ``` fences, <br>, or HTML in a cell — that "
    "shatters the grid. Code samples go AFTER the table under ### headings "
    "as tagged fences (```python, ```java).\n"
    "  - After the examples, a short which-to-choose recommendation if they asked.\n"
    "  - Proper GFM: every row starts and ends with |; never wrap the table "
    "in a code fence. Prefer 2-3 columns.\n"
    "\n"
    "Tables: use a pipe table when aligned rows and columns help lookup or "
    "comparison (schedules, measurements, matrices, lookup grids, X vs Y). "
    "Never for tips, how-tos, roadmaps, guides, checklists, or single-topic advice."
)

# Compat aliases — one contract, two historical names.
INTENT_FORMAT_HINT = FORMAT_CONTRACT
RESPONSE_FORMAT_HINT = FORMAT_CONTRACT

STYLE_HINTS = {
    "short": (
        "Response length: SHORT. The user chose brevity — this overrides default formatting length. "
        "Answer in 1-3 sentences or at most 4-5 tight bullets. No preamble, no recap of the question, "
        "no closing offers to help further. Skip sections, headings, tables, diagrams, and HTML unless "
        "the user explicitly asked for them."
    ),
    "balanced": (
        "Response length: BALANCED. Be clear and complete without rambling — use short headings and "
        "bullets when helpful, but keep the overall reply moderate in length. "
        "Lead with the answer; explanation after."
    ),
    "detailed": (
        "Response length: DETAILED. Be thorough but stay scannable: sections, headings, "
        "and bullets — not essay-style paragraphs. Use a pipe table for schedules, "
        "measurements, lookup grids, and X vs Y comparisons — not for tips or how-tos. "
        "Include examples and nuance where useful."
    ),
}

SHORT_RESPONSE_FORMAT_HINT = (
    "Formatting for SHORT mode: plain text or a few bullets only. No ## headings. "
    "No pipe tables. No ```html / ```mermaid / ```chart unless the user explicitly requested a visual."
)

# Compact baseline injected on ALL non-lightweight turns (short, day-plan, quiz).
# Covers the artifacts that make output ugly regardless of turn type.
UNIVERSAL_FORMAT_BASELINE = (
    "Never put a colon on its own line — it strands as a lone punctuation mark. "
    "If a label introduces a formula, put the formula on the next line without a trailing colon. "
    "Keep paragraphs to 2-3 sentences. Avoid 3+ consecutive blank lines. "
    "Lead with the answer; explanation after. No intro paragraph before the conclusion. "
    "Never use decorative headings (Introduction, Background, Overview, Conclusion, "
    '"Let\'s dive in"). Headings only when they group real sections. '
    "Do not decorate with emoji unless the user used them. "
    "Use named markdown links like [OpenAI docs](url), not raw URLs, unless asked. "
    "Do not restate the question. "
    "Use the simplest structure that answers; do not add sections just to look structured. "
    "Never invent a pipe table for tips, how-tos, roadmaps, or checklists. "
    "Use a pipe table for schedules, measurements, lookup grids, and X vs Y comparisons. "
    "Never open with a rhetorical hook (Ah, the eternal question; Great question; "
    "Let's break it down)."
)

# Slim/casual turns: ChatGPT-shaped, not a rich-fence pack.
COMPACT_RESPONSE_FORMAT_HINT = (
    "Casual turn: lead with the answer in the first sentence. Plain prose or at "
    "most 4 short bullets. No ## headings and no pipe tables unless they asked "
    "for a checklist or an X vs Y compare. If they pasted a phrase or fragment, "
    "correct or complete it — do not invent a topic essay or joke about the words."
)

# Appended after the tone line so "funny" cannot override answer-first format.
TONE_FORMAT_GUARD = (
    "Configured tone is word choice only. Do not add a joke setup or recap "
    "before the answer. Funny never means a bit about the question. "
    "Do not invent a decorative table before the answer — an X vs Y compare "
    "still leads with the pipe table; a numeric chart leads with ```chart, "
    "never a substitute table."
)

# NOTE: response style (short/balanced/detailed) drives *brevity through the
# prompt* via STYLE_HINTS above — it no longer caps output tokens. A single
# high ceiling (settings.max_output_tokens) is the safety backstop; the daily
# token quota is the real per-user cost guardrail. Capping by style truncated
# large deliverables (HTML pages, graph JSON) mid-fence.
