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
    "2. After the table, expand only the areas that need explanation. Use ### headings "
    "only when there are multiple real sections. Include tagged code fences only when the "
    "user is comparing programming languages/tools and code examples materially help.\n"
    "3. Give a short recommendation only when the user asks which to choose or clearly "
    "needs a decision. Never invent a 'beginner choice' section.\n"
    "Every table row starts and ends with |. Never wrap the table in a fence."
)


def is_comparison_question(text: str) -> bool:
    """True when the user is asking for an X vs Y / feature comparison."""
    cleaned = text.strip()
    if not cleaned:
        return False
    return bool(_COMPARISON_TURN.search(cleaned))


_TECHNICAL_COMPARE_WORDS = (
    "python",
    "java",
    "javascript",
    "typescript",
    "rust",
    "kotlin",
    "swift",
    "react",
    "vue",
    "angular",
    "django",
    "flask",
    "postgres",
    "mysql",
    "mongodb",
    "redis",
    "linux",
    "windows",
    "android",
    "typing",
    "syntax",
    "compiler",
)


def _has_whole_word(haystack: str, word: str) -> bool:
    """Linear whole-word scan — avoid regex over the user turn."""
    lower = haystack.lower()
    start = 0
    n = len(word)
    while True:
        idx = lower.find(word, start)
        if idx < 0:
            return False
        before = lower[idx - 1] if idx > 0 else " "
        after = lower[idx + n] if idx + n < len(lower) else " "
        if not before.isalnum() and not after.isalnum():
            return True
        start = idx + n


def is_structured_comparison_question(text: str) -> bool:
    """Table + code-card compare: languages/tools/features, not tea vs coffee."""
    if not is_comparison_question(text):
        return False
    lower = text.strip().lower()
    if any(
        cue in lower
        for cue in (
            "feature",
            "price",
            "cost",
            "performance",
            "battery",
            "camera",
            "specification",
            "specs",
            "use case",
            "pros and cons",
        )
    ):
        return True
    return any(_has_whole_word(lower, word) for word in _TECHNICAL_COMPARE_WORDS)


_BREVITY_MARKERS = (
    "in one sentence",
    "one sentence",
    "in a word",
    "in one word",
    "in a single word",
    "briefly",
    "keep it short",
    "keep it brief",
    "tldr",
    "tl;dr",
)

BREVITY_REQUEST_HINT = (
    "The user asked for a one-sentence, one-word, or brief answer. "
    "Ignore decorative table/heading layout and match the length they asked. Preserve a "
    "draft/code/visual container only when that container is the requested deliverable."
)


def is_brevity_request(text: str) -> bool:
    """True when the user capped length (one sentence / briefly), not Short style."""
    cleaned = text.strip().lower()
    if not cleaned:
        return False
    return any(marker in cleaned for marker in _BREVITY_MARKERS)


_CHART_TURN = re.compile(
    r"(?:"
    r"\b(?:bar|line|pie|area|scatter|donut)\s+charts?\s+(?:of|for|with|from|using)\b|"
    r"\bcharts?\s+(?:of|for|my)\b|"
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
    "Lead with a ```chart fence of Vega-Lite JSON. At most one short sentence "
    "before the fence. No joke setup. No leftover bare numbers and no "
    "```answer / ```result fence.\n"
    "If they gave numbers, use those as data.values in that order. "
    "If they asked for an example or a generic chart with no series, a short "
    "labelled sample is fine — say it is sample data in that one sentence. "
    "If they asked to chart their real/my data and gave no numbers, ask ONE "
    "question for the values. Do not invent a sample and treat that as the answer.\n"
    "If they also asked for a statistic or explanation, put that after the fence. "
    "Do not stop immediately after the chart unless they only asked for the drawing.\n"
    'First key must be "$schema": "https://vega.github.io/schema/vega-lite/v5.json". '
    "Prefer mark bar/line as asked. Named categories (months, items) go on y "
    'with "sort": null (horizontal bars) so labels stay visible — never '
    "clip them under the plot. Grouped series dodge with yOffset when "
    "category is on y (or xOffset when category is on x).\n"
    "Example shape only:\n"
    "```chart\n"
    '{"$schema":"https://vega.github.io/schema/vega-lite/v5.json",'
    '"description":"A simple bar chart","data":{"values":['
    '{"month":"Jan","inches":5.7},{"month":"Feb","inches":3.5}]},'
    '"mark":"bar","encoding":{"x":{"field":"inches","type":"quantitative"},'
    '"y":{"field":"month","type":"nominal","sort":null}}}\n'
    "```"
)


def is_chart_question(text: str) -> bool:
    """True when the user asked to draw a numeric chart (Vega), not define one."""
    cleaned = text.strip()
    if not cleaned:
        return False
    if _is_chart_definition(cleaned) or _chart_request_negated(cleaned):
        return False
    return bool(_CHART_TURN.search(cleaned))


_CHART_KINDS = ("bar", "line", "pie", "area", "scatter", "donut")


def _is_chart_definition(cleaned: str) -> bool:
    lower = cleaned.lower()
    if "what is a chart" in lower or "what's a chart" in lower:
        return True
    for kind in _CHART_KINDS:
        if f"what is a {kind} chart" in lower or f"what's a {kind} chart" in lower:
            return True
        if f"what are {kind} charts" in lower:
            return True
    return False


def _chart_request_negated(cleaned: str) -> bool:
    lower = cleaned.lower()
    if "chart" not in lower:
        return False
    for neg in ("do not", "don't", "dont", "never", "without"):
        start = 0
        while True:
            idx = lower.find(neg, start)
            if idx < 0:
                break
            window = lower[idx : idx + 80]
            if "chart" in window and any(
                verb in window for verb in ("make", "draw", "create", "render", "plot")
            ):
                return True
            start = idx + len(neg)
    return False


_SEQUENCE_CUE = re.compile(r"\bsequence\s+diagram\b", re.IGNORECASE)
_FLOWCHART_CUE = re.compile(
    r"(?:\bflow[\s-]?chart\b|```mermaid\b)",
    re.IGNORECASE,
)
_MERMAID_WORD = re.compile(r"\bmermaid\b", re.IGNORECASE)
_MERMAID_RENDER_CUE = re.compile(
    r"\b(?:draw|show|make|create|render|diagram)\b",
    re.IGNORECASE,
)

MERMAID_FORMAT_HINT = (
    "This turn is a flowchart. Lead with a ```mermaid fence — not a numbered "
    "list, not HTML/SVG, and not a joke setup ('let's brew up some fun'). "
    "At most one short sentence, then the fence. Do not interview for steps.\n"
    "Match the process they asked for. If they named steps or said ~N steps, "
    "emit those nodes — do not invent a 2-box story.\n"
    "Linear process: flowchart TD, one rectangle per step, --> between them. "
    "Start/end may use stadium ([...]); decisions use diamonds.\n"
    "Node labels must not contain raw parentheses — they break the parser. "
    'Quote any label that needs extra words: E["Grind beans"] not '
    "E[Grind Beans (Medium Grind)].\n"
    "Example shape only:\n"
    "```mermaid\n"
    "flowchart TD\n"
    "    start([Start]) --> step[Do the work] --> done([Done])\n"
    "```"
)

SEQUENCE_FORMAT_HINT = (
    "This turn is a sequence diagram, not a flowchart. Lead with a ```mermaid "
    "fence using sequenceDiagram — not flowchart TD, not a numbered list, and "
    "not a joke setup. At most one short sentence, then the fence.\n"
    "Participants and messages they named; do not invent a 2-box story.\n"
    "Example shape only:\n"
    "```mermaid\n"
    "sequenceDiagram\n"
    "    participant Client\n"
    "    participant Server\n"
    "    Client->>Server: request\n"
    "    Server-->>Client: response\n"
    "```"
)


def is_sequence_diagram_question(text: str) -> bool:
    """True when the user asked for a sequence diagram specifically."""
    cleaned = text.strip()
    return bool(cleaned and _SEQUENCE_CUE.search(cleaned))


def is_mermaid_question(text: str) -> bool:
    """True when the user asked for a Mermaid/flowchart/sequence diagram."""
    cleaned = text.strip()
    if not cleaned:
        return False
    if is_sequence_diagram_question(cleaned):
        return True
    if _FLOWCHART_CUE.search(cleaned):
        return True
    return bool(_MERMAID_WORD.search(cleaned) and _MERMAID_RENDER_CUE.search(cleaned))


_CALLOUT_TURN = re.compile(
    r"(?:"
    r"\binclude\s+(?:a\s+)?(?:tip|note|warning)\b|"
    r"\b(?:important\s+|safety\s+)?warning\s+about\b|"
    r"\bcallout\b"
    r")",
    re.IGNORECASE,
)

CALLOUT_FORMAT_HINT = (
    "This turn explicitly asked for a highlighted tip/note/warning. Recall renders blockquotes "
    "starting with Tip: / Note: / Warning: as callout cards.\n"
    "Do not write a joke setup. Lead with the advice.\n"
    "Use one matching markdown blockquote—`> Tip: …`, `> Note: …`, or "
    "`> Warning: …`—for the specifically highlighted point. Use ordinary bullets for "
    "other unordered tips; use numbers only if order matters. Never a pipe table."
)


def is_callout_question(text: str) -> bool:
    """True when the user asked for tips/notes/warnings as callouts, not a how-to table."""
    cleaned = text.strip()
    if not cleaned:
        return False
    if (
        is_comparison_question(cleaned)
        or is_chart_question(cleaned)
        or is_mermaid_question(cleaned)
    ):
        return False
    return bool(_CALLOUT_TURN.search(cleaned))


_HOWTO_TURN = re.compile(
    r"(?:"
    r"\b\d+[\s-]?week(?:s)?\s+plan\b|"
    r"\bweek[\s-]?by[\s-]?week\b|"
    r"\broadmap(?:\s+to\s+learn)?\b|"
    r"\b(?:learning|study)\s+plan\b|"
    r"\bplan\s+to\s+learn\b|"
    r"\bfrom scratch\b|"
    r"\bhow (?:do i|to) (?:set up|setup|install|configure|build)\b|"
    r"\bstep[\s-]?by[\s-]?step\b|"
    r"\bplan\s+de\s+\d+[\s-]?(?:semana|semanas|semaine|semaines)\b|"
    r"\b\d+[\s-]?wochen[\s-]?plan\b|"
    r"\bpaso\s+a\s+paso\b|"
    r"\b(?:etape|étape)\s+par\s+(?:etape|étape)\b|"
    r"\bschritt[\s-]?f[uü]r[\s-]?schritt\b"
    r")",
    re.IGNORECASE,
)

HOWTO_FORMAT_HINT = (
    "This turn is a how-to, roadmap, or N-week learning plan.\n"
    "Do not write a joke setup. Prefer lists over a pipe table—a week-by-week plan "
    "is normally not a schedule grid. If the user explicitly asks for a compact table, "
    "honor that request and keep it to 2-3 columns.\n"
    "Use ## headings per week or phase. Under each: a one-line goal, then "
    "numbered steps or short bullets. Keep vocab/phrases in bullets, not table "
    "columns."
)


def is_howto_question(text: str) -> bool:
    """True for learning plans / how-tos that must stay lists, not schedule tables."""
    cleaned = text.strip()
    if not cleaned:
        return False
    if (
        is_comparison_question(cleaned)
        or is_chart_question(cleaned)
        or is_mermaid_question(cleaned)
        or is_callout_question(cleaned)
    ):
        return False
    return bool(_HOWTO_TURN.search(cleaned))


_QUOTE_TURN = re.compile(
    r"(?:"
    r"\b(?:give|share|tell)(?:\s+me)?\s+(?:an?\s+|one\s+)?"
    r"(?:famous\s+|well[- ]known\s+|inspirational\s+|motivational\s+)?"
    r"quotes?\b|"
    r"\b(?:famous|inspirational|motivational)\s+quotes?\b|"
    r"\bquotes?\s+by\b|"
    r"\bquotes?\s+(?:about|on|from)\b|"
    r"\bquotation\s+(?:by|from|about)\b"
    r")",
    re.IGNORECASE,
)
_STOCK_QUOTE = re.compile(
    r"(?:stock\s+quotes?|ticker\s+symbol|\bnasdaq\b|\bnyse\b)",
    re.IGNORECASE,
)

QUOTE_FORMAT_HINT = (
    "This turn asked for a quotation. Recall renders markdown blockquotes "
    "(plain `>`) as a quote card. Do not write a joke setup. Lead with the "
    "quote.\n"
    "Put the quote on `>` lines. Attribution on its own following line as "
    "`— Name` (em dash). Do not wrap the whole thing in straight quotes "
    '(`"…" - Author`) and do not italicize it as a paragraph.\n'
    "Never emit a ```quote fence. At most one short sentence after the card."
)


def is_quote_question(text: str) -> bool:
    """True when the user asked for a famous / attributed quotation, not a stock quote."""
    cleaned = text.strip()
    if not cleaned:
        return False
    if _STOCK_QUOTE.search(cleaned):
        return False
    return bool(_QUOTE_TURN.search(cleaned))


# One layout contract. The model writes Markdown; Recall upgrades presentation.
# Do NOT teach tip / steps / comparison / details / answer as model-chosen UI —
# those cards still render if an old message has the fence.
FORMAT_CONTRACT = (
    "This is a conversational chat. Write normal Markdown — headings, lists, "
    "tables, and blockquotes. Do not invent custom fence names for layout.\n"
    "\n"
    "Explicit format requests win: one paragraph stays one paragraph; requested outline "
    "markers, tables, code, poems, and multiple draft versions keep that shape.\n"
    "Default:\n"
    "  - Simple factual or conversational answer: 1-3 short paragraphs, usually no heading.\n"
    "  - Bullets are for parallel unordered items. Numbers are only for steps, rankings, "
    "chronology, or priorities. Letters are for alternatives/answer choices or when requested; "
    "roman numerals only when requested. Do not use numbers merely as indentation.\n"
    '  - For a single topic ("tell me about X"), a short paragraph or flat bullets '
    "is enough. Use 2-3 short headings only when they group real sections — not a "
    "parent bullet whose children are more bullets, and not a wall of text or a table.\n"
    "  - Nest at most one level and preserve meaning: unordered children stay bullets; "
    "ordered children stay numbers. If the user requests letters/roman numerals, use clear "
    "plain labels such as `A.` or `I.` even if Markdown does not auto-number them. Two short sibling "
    "facts can stay on one line after the label instead of nesting "
    "(`**Powers:** 8² = 64, 8³ = 512`).\n"
    "  - Short how-to: one numbered list. Multi-phase roadmap/guide: ## headings for "
    "phases and numbered steps under each. Prefer lists to a pipe table unless the user "
    "explicitly requested a compact grid.\n"
    "  - Callouts: a blockquote starting with Tip: / Note: / Warning: "
    "(plain `>`). Not a fence.\n"
    "  - Famous quotes: a markdown blockquote (`>`), attribution on its own "
    "line as `— Name`. Not a ```quote fence and not a quoted italic paragraph.\n"
    "\n"
    "Writing helper (email, message, reply, caption, social post):\n"
    "  - If they named what the email/message should say, put only send-ready text "
    "inside ```email, ```message, ```sms, or ```copy now. One by default; multiple only "
    "when the user explicitly requests alternatives.\n"
    "  - If they only asked to write an email with no purpose, ask one question "
    "first — do not invent a generic letter or placeholders.\n"
    "\n"
    "Coding:\n"
    "  - For a direct code request, lead with the code or one brief approach sentence, "
    "then a tagged code fence (```python, ```javascript, etc.). Add notes only when they "
    "help the user run, understand, or safely change it. Never put source code in an untagged "
    "fence.\n"
    "\n"
    "Decision / compare (ONLY when the user asks X vs Y, A vs B vs C, or a "
    "feature comparison — not for tips, roadmaps, or how-tos):\n"
    "  - Casual preference (tea vs coffee): a short paragraph is enough — no table "
    "required.\n"
    "  - Feature, product, or language compare: lead with a **markdown pipe table** "
    "(Feature | A | B). One attribute "
    "per row. Cells are one short phrase.\n"
    "  - NEVER put source code, ``` fences, <br>, or HTML in a cell — that "
    "shatters the grid. Code samples go AFTER the table under ### headings "
    "as tagged fences (```python, ```java).\n"
    "  - After the examples, a short which-to-choose recommendation if they asked.\n"
    "  - Proper GFM: every row starts and ends with |; never wrap the table "
    "in a code fence. Prefer 2-3 columns.\n"
    "\n"
    "Tables: use a pipe table when aligned rows and columns help lookup or "
    "comparison (timetables, measurements, matrices, lookup grids, X vs Y). "
    "Do not choose one for tips, how-tos, roadmaps, guides, or single-topic advice unless "
    "the user explicitly requested a compact table."
)

# Compat aliases — one contract, two historical names.
INTENT_FORMAT_HINT = FORMAT_CONTRACT
RESPONSE_FORMAT_HINT = FORMAT_CONTRACT

STYLE_HINTS = {
    "short": (
        "Response length: SHORT. The user chose brevity — this overrides default formatting length. "
        "Answer in 1-3 sentences or at most 4-5 tight bullets. No preamble, no recap of the question, "
        "no closing offers to help further. Skip sections, headings, tables, diagrams, and HTML unless "
        "the user explicitly asked for them. Explicit prose/draft/code format requests still win."
    ),
    "balanced": (
        "Response length: BALANCED. Be clear and complete without rambling — use short headings and "
        "bullets when helpful, but keep the overall reply moderate in length. "
        "Lead with the answer; explanation after."
    ),
    "detailed": (
        "Response length: DETAILED. Be thorough but stay scannable: use sections, headings, "
        "and bullets when they fit the task. If the user requested an essay, article, story, "
        "letter, or paragraph, preserve that prose form. Use a pipe table for timetables, "
        "measurements, lookup grids, and X vs Y comparisons — not for tips or how-tos. "
        "Include examples and nuance where useful."
    ),
}

SHORT_RESPONSE_FORMAT_HINT = (
    "Formatting for SHORT mode: plain text or a few bullets only. No ## headings. "
    "No pipe tables unless the user explicitly requested one. No ```html / ```mermaid / "
    "```chart unless the user explicitly requested a visual."
)

# Compact baseline injected on ALL non-lightweight turns (short, day-plan, quiz).
# Covers the artifacts that make output ugly regardless of turn type.
UNIVERSAL_FORMAT_BASELINE = (
    "Never put a colon on its own line — it strands as a lone punctuation mark. "
    "If a label introduces a formula, put the formula on the next line without a trailing colon. "
    "By default, keep paragraphs to 2-3 sentences; an explicitly requested prose length or "
    "shape wins. Avoid 3+ consecutive blank lines. "
    "Lead with the answer; explanation after. No intro paragraph before the conclusion. "
    "Never use decorative headings (Introduction, Background, Overview, Conclusion, "
    '"Let\'s dive in"). Headings only when they group real sections. '
    "Do not decorate with emoji unless the user used them. "
    "Use named markdown links like [OpenAI docs](url), not raw URLs, unless asked. "
    "Do not restate the question. "
    "Use the simplest structure that answers; do not add sections just to look structured. "
    "Honor an explicit request for a table, paragraph, outline marker, or code block. "
    "Never invent a pipe table for tips, how-tos, roadmaps, or checklists. "
    "Use a pipe table for timetables, measurements, lookup grids, and X vs Y comparisons. "
    "Never open with a rhetorical hook (Ah, the eternal question; Great question; "
    "Let's break it down)."
)

# Slim/casual turns: ChatGPT-shaped, not a rich-fence pack.
COMPACT_RESPONSE_FORMAT_HINT = (
    "Casual turn: lead with the answer in the first sentence. Plain prose or at "
    "most 4 short bullets. No ## headings and no pipe tables unless they explicitly "
    "asked for a table or an X vs Y compare. If they pasted a phrase or fragment, "
    "correct or complete it — do not invent a topic essay or joke about the words."
)

# Appended after the tone line so "funny" cannot override answer-first format.
TONE_FORMAT_GUARD = (
    "Configured tone is word choice only. Do not add a joke setup or recap "
    "before the answer. Funny never means a bit about the question. "
    "If they asked for one sentence, one word, or briefly, skip decorative tables and headings; "
    "keep a draft/code fence only when it is the requested deliverable. "
    "Do not invent a decorative table before the answer — a feature or language "
    "compare leads with the pipe table; a casual preference can be a short "
    "paragraph; a numeric chart leads with ```chart, "
    "never a substitute table; a flowchart leads with ```mermaid; "
    "a tips/warning ask leads with `> Tip:` / `> Warning:`, never a joke essay; "
    "a learning plan / how-to leads with ## headings and lists, never a "
    "schedule table; a quotation ask leads with a `>` blockquote, never "
    'italic `"…" - Author` prose.'
)

# NOTE: response style (short/balanced/detailed) drives *brevity through the
# prompt* via STYLE_HINTS above — it no longer caps output tokens. A single
# high ceiling (settings.max_output_tokens) is the safety backstop; the daily
# token quota is the real per-user cost guardrail. Capping by style truncated
# large deliverables (HTML pages, graph JSON) mid-fence.
