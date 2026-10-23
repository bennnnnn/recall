"""Response-format, comparison and layout hints (reply length is ``length.py``)."""

import re

from app.modules.chat.prompt_constants.chart import is_chart_question
from app.modules.chat.prompt_constants.diagrams import is_mermaid_question

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


_CALLOUT_TURN = re.compile(
    r"(?:"
    r"\binclude\s+(?:a\s+)?(?:tip|note|warning)\b|"
    r"\b(?:important\s+|safety\s+)?warning\s+about\b|"
    r"\bcallout\b"
    r")",
    re.IGNORECASE,
)

CALLOUT_FORMAT_HINT = (
    "This turn asked for a highlighted warning or note. A callout is only "
    "`> Warning:` for a real risk or correction, or a short `> Note:` the reader "
    "must not miss, and only when that label is true. Never for hints, answers, "
    "section intros, emphasis, or decoration. Other points are ordinary bullets "
    "(numbers only if order matters). A `>` quote card is only a cited quotation "
    "whose last line is `— Name`. Do not write a joke setup. Never a pipe table."
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


# A plan over weeks or phases. "From scratch" stays here: "learn Python from
# scratch" is a roadmap, and the hint says one task is still one list of steps.
_HOWTO_TURN = re.compile(
    r"(?:"
    r"\b\d+[\s-]?week(?:s)?\s+plan\b|"
    r"\bweek[\s-]?by[\s-]?week\b|"
    r"\broadmap(?:\s+to\s+learn)?\b|"
    r"\b(?:learning|study)\s+plan\b|"
    r"\bplan\s+to\s+learn\b|"
    r"\bfrom scratch\b|"
    r"\bplan\s+de\s+\d+[\s-]?(?:semana|semanas|semaine|semaines)\b|"
    r"\b\d+[\s-]?wochen[\s-]?plan\b"
    r")",
    re.IGNORECASE,
)

HOWTO_FORMAT_HINT = (
    "This turn is a roadmap or an N-week plan.\n"
    "Do not write a joke setup. Prefer lists over a pipe table—a week-by-week plan "
    "is normally not a schedule grid. If the user explicitly asks for a compact table, "
    "honor that request and keep it to 2-3 columns.\n"
    "Use ## headings per week or phase. Under each: a one-line goal, then "
    "numbered steps or short bullets. Keep vocab/phrases in bullets, not table "
    "columns. One task (make bread from scratch) is not a plan: one numbered list of "
    "steps, no headings."
)


def _owned_by_another_layout(cleaned: str) -> bool:
    """A compare, chart, flowchart or callout ask keeps that layout over a how-to's."""
    return (
        is_comparison_question(cleaned)
        or is_chart_question(cleaned)
        or is_mermaid_question(cleaned)
        or is_callout_question(cleaned)
    )


def is_howto_question(text: str) -> bool:
    """True for learning plans / roadmaps that must stay lists, not schedule tables."""
    cleaned = text.strip()
    if not cleaned or _owned_by_another_layout(cleaned):
        return False
    return bool(_HOWTO_TURN.search(cleaned))


# "How do I make tea", "how to tie a tie", "what are the steps to renew a
# passport": a task the user will do. Feelings and judgment ("how do I know if",
# "how do I deal with") are not steps.
_TASK_HOWTO = re.compile(
    r"^(?:(?:so|ok(?:ay)?|hey|hi|please|quick\s+question)[,!:]?\s+)?"
    r"(?:how\s+(?:do|can|should|would)\s+(?:i|you|we|one)|how\s+to"
    r"|what\s+(?:are|is)\s+the\s+steps?\s+(?:to|for)|(?:give\s+me\s+)?(?:the\s+)?steps\s+to)\s+"
    r"(?!(?:know|tell|feel|deal|cope|forgive|trust|decide|understand|stop\s+(?:feeling|thinking)"
    r"|get\s+over|be\s+(?:happy|confident|happier)|love|say|pronounce|spell)\b)[^\W\d_]",
    re.IGNORECASE,
)
# Asked for as steps anywhere in the message: "walk me through changing a tire",
# "install Python step by step", "receta de pan paso a paso".
_STEPWISE_TURN = re.compile(
    r"(?:"
    r"\bhow (?:do i|to) (?:set up|setup|install|configure|build)\b|"
    r"\bwalk\s+me\s+through\b|"
    r"\bstep[\s-]?by[\s-]?step\b|"
    r"\bpaso\s+a\s+paso\b|"
    r"\b(?:etape|étape)\s+par\s+(?:etape|étape)\b|"
    r"\bschritt[\s-]?f[uü]r[\s-]?schritt\b"
    r")",
    re.IGNORECASE,
)

STEPS_FORMAT_HINT = (
    "This is a how-to task. Give numbered steps, one action each, in the order they are done. "
    "Put what is needed (ingredients, tools, documents) first as a short list when there is "
    "any. A warning or a must-do-first (back up, switch off the power) goes just before the "
    "step it applies to, never after it. Add a one-line tip at the end only if it helps. "
    "No headings for a short task. A goal reached in several independent ways rather than "
    "one sequence (save money, sleep better) takes the ways layout instead: numbered items, "
    "each opening with a bold label."
)


def is_task_howto(text: str) -> bool:
    """True for "how do I <do a task>": numbered steps, not a plan or an essay."""
    cleaned = text.strip()
    if not cleaned or len(cleaned) > 300:
        return False
    if _TASK_HOWTO.search(cleaned) is not None:
        return True
    return _STEPWISE_TURN.search(cleaned) is not None and not _owned_by_another_layout(cleaned)


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
    "This turn asked for a quotation. A `>` quote card is only a cited "
    "quotation whose last line is `— Name`. Do not write a joke setup. Lead "
    "with the quote.\n"
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
# Do NOT teach steps / comparison / details / answer / tip fences as layout.
# A quote card is only a citation. A callout is only Warning or Note.
FORMAT_CONTRACT = (
    "This is a conversational chat. Write normal Markdown — headings, lists, "
    "tables, and blockquotes. Do not invent custom fence names for layout.\n"
    "\n"
    "Explicit format requests win: one paragraph stays one paragraph; requested outline "
    "markers, tables, code, poems, and multiple draft versions keep that shape.\n"
    "Default:\n"
    "  - Simple factual or conversational answer: 1-3 short paragraphs, usually no heading.\n"
    "  - If the answer depends on something the user didn't say (budget, platform, version), "
    "state the assumption in one short clause and answer. Say plainly, once, when you are "
    "unsure; no stacked disclaimers.\n"
    "  - Bullets are for parallel unordered items. Numbers are for steps, rankings, "
    "chronology, priorities, and a list of ways, tips, or ideas the user may point back to "
    '("the second one"). Letters are for alternatives/answer choices or when requested; '
    "roman numerals only when requested. Do not use numbers merely as indentation.\n"
    '  - Several ways, tips, ideas, reasons, benefits, or options ("ways to become rich", '
    '"how to save money"): at most one lead sentence, then a numbered list of about 5-8 items. '
    "Each item opens with a **bold label of 2-5 words**, then a dash and one or two short "
    "sentences; bold at most one key phrase. No sub-bullets unless an item has parts. Over 8 "
    "items: group them under 2-4 short ### headings, numbering continuing across groups. End "
    "with at most one short takeaway line, not a recap. The bold labels alone give the gist.\n"
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
    "  - A `>` quote card is only a cited quotation whose last line is "
    "`— Name`. Every other `>` is ordinary indented prose, not a card and "
    "not a quoted italic paragraph.\n"
    "  - A callout is only `> Warning:` for a real risk or correction, or a "
    "short `> Note:` the reader must not miss, and only when that label is "
    "true. Never for hints, answers, section intros, emphasis, decoration, an "
    "apology, or a remark about the reply itself.\n"
    "  - An everyday example is an ordinary sentence led by *For example,* or a "
    "bullet; a quoted phrase stays inline in “…”. Never a `>`, a callout, or a code "
    "fence for an example that is not code.\n"
    "  - Ending: at most one short plain line, a question or an offer of one concrete "
    "next step (under 15 words, never bold, never a list). None when the answer stands "
    'on its own, and never a generic "Let me know if you have any other questions".\n'
    "\n"
    "Writing helper (email, message, reply, caption, social post):\n"
    "  - If they named what the email/message should say, put only send-ready text "
    "inside ```email, ```message, ```sms, or ```copy now. One by default; multiple only "
    "when the user explicitly requests alternatives.\n"
    "  - If they only asked to write an email with no purpose, ask one question "
    "first — do not invent a generic letter or placeholders.\n"
    "  - Never open ```email / ```sms / ```message as an example of a capability. "
    "Describe drafting in words unless this turn is a request to write one.\n"
    "\n"
    "Coding:\n"
    "  - For a direct code request, lead with one brief approach sentence, then a "
    "language-tagged fence (```python, ```javascript). The tag is the corner label on the "
    "card. Add notes only when they help the user run, understand, or safely change it. "
    "Never put a program in an untagged fence.\n"
    "  - Inline backticks hold code inside prose: names, values, keywords and short "
    'expressions such as `total`, `0`, `for`, `name = "john"` or `nums[i]`. Do not backtick a '
    "phrase or a sentence, and never bold or backtick ordinary words. A multi-line sample is "
    "a tagged fence. An untagged fence has no language label.\n"
    "  - Values and expressions from code stay in backticks, never `$...$` math: write "
    "`total + n`, not $total + n$. Only Big-O may be inline math (`$O(n)$`).\n"
    "  - For a bug or snippet question, inspect the literal snippet first and lead with its "
    "concrete syntax/runtime issue. Prior conversation may explain the likely intent, but it "
    "must not replace the explicit current question or hide a more immediate bug.\n"
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

SHORT_RESPONSE_FORMAT_HINT = (
    "Formatting for SHORT mode: plain text or a few bullets only. No ## headings. "
    "No pipe tables unless the user explicitly requested one. No ```html / ```mermaid / "
    "```chart unless the user explicitly requested a visual."
)

# Compact baseline injected on ALL non-lightweight turns (short, day-plan, quiz).
# Covers the artifacts that make output ugly regardless of turn type.
_UNIVERSAL_FORMAT_CORE = (
    "Never put a colon on its own line — it strands as a lone punctuation mark. "
    "If a label introduces a formula, put the formula on the next line without a trailing colon. "
    "By default, keep paragraphs to 2-3 sentences; an explicitly requested prose length or "
    "shape wins. Avoid 3+ consecutive blank lines. "
    "Lead with the answer; explanation after. No intro paragraph before the conclusion. "
    "When the user shares something painful or frightening (a loss, bad news, panic), the "
    "first line briefly and sincerely acknowledges it, then the help follows; that line is "
    "not an intro. "
    "When the user says a reply missed without saying why, never blame a glitch or a "
    "formatting error; give it again another way (simpler, shorter, another method) or "
    "ask which part missed. "
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

MARKDOWN_BOUNDARY_CONTRACT = (
    "Markdown spacing: put a normal word space outside inline delimiters. "
    "Write at **40 km/h**, never at**40 km/h**. "
    "Write **60 km/h** and **40 km/h**, never **60 km/h**and. "
    "Keep punctuation on the delimiter: **48 km/h**. and **48 km/h**, and (**important**). "
    "Bold a key value, constraint, term, or conclusion. Leave connective prose unbolded, "
    "and do not bold a whole paragraph. "
    "Do not change characters inside code, URLs, or math."
)

CALCULATION_LAYOUT_CONTRACT = (
    "Calculation layout, every subject (not code, whose values stay in `inline code`): one "
    "logical reasoning state per math row. "
    "Keep one definition, one formula, one simple evaluation, or one relationship together, "
    "including $12 + 8 = 20\\text{ km}$, $0.6 + 0.8 = 1.4\\text{ h}$, $20 \\div 4 = 5$, and "
    "$x = \\frac{-b \\pm \\sqrt{b^2-4ac}}{2a}$ on a single row. "
    "A wide formula may scroll; do not break inside a fraction, radical, or matrix. "
    "Put a formula, its substitution, and its result on separate rows: "
    "$v = \\frac{d}{t}$, then $v = \\frac{50}{10}$, then $v = 5$. "
    "An expression with no named quantity is written once, with its working beside it "
    "($\\frac{6!}{4!} = \\frac{720}{24}$), and its result goes alone on the next row; "
    "never repeat the expression as the left side of a second row. "
    "Put independent equations on separate rows, never $t_1 = d/60,\\quad t_2 = d/40$. "
    "Trivial one-step arithmetic is one row with no headings; any longer worked "
    "solution uses the worked-solution layout (Given, Find, Formula, Substitution or "
    "Steps, Answer). "
    "Do not force a line break with HTML."
)

# Statistics and biology have no module yet: chat's continuation_subject names them, so
# their presentation hints stay here until a subject module owns them.
STATISTICS_PRESENTATION_HINT = (
    "This is a statistics answer. Name the statistic and the values that enter it. "
    "When you calculate, follow the calculation layout: one reasoning state per row."
)

BIOLOGY_PRESENTATION_HINT = (
    "This is a quantitative biology answer. Keep the biological quantity and its units visible. "
    "When you calculate, follow the calculation layout: one reasoning state per row."
)

UNIVERSAL_FORMAT_BASELINE = " ".join(
    (
        _UNIVERSAL_FORMAT_CORE,
        MARKDOWN_BOUNDARY_CONTRACT,
        CALCULATION_LAYOUT_CONTRACT,
    )
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
    "paragraph; a chart they ask for leads with ```chart, never a substitute table, "
    "and nothing else gets one (not a single value, a sum or a unit conversion; "
    "y = f(x) is a graph, never a chart); a flowchart leads with ```mermaid; "
    "a real warning leads with `> Warning:`; a note the reader must not miss "
    "may be `> Note:`; hints stay ordinary prose, never a joke essay; "
    "a multi-phase learning plan uses ## headings with lists and a short how-to "
    "is one numbered list, never a schedule table; a quotation ask leads with a "
    "`>` blockquote whose last "
    "line is `— Name`, never "
    'italic `"…" - Author` prose.'
)
