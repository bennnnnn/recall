"""Response-format, comparison, and length-style hints."""

import re

from app.services.chat.prompt_constants.math import MATH_INTENT_HINT

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
    "Rich formatting — use these fences to make answers visually clear and "
    "attractive (but don't overuse; 1-2 callouts per long answer max):\n"
    "  - ```tip or ```note — a highlighted callout card (green/blue) for a key "
    "insight, takeaway, or important note.\n"
    "  - ```warning — an amber callout for cautions, gotchas, or common mistakes.\n"
    "  - ```steps — numbered badge rows for multi-step how-tos or procedures. "
    "Prefer this over a plain numbered list when each step is a distinct action.\n"
    "  - ```details — a collapsible section for optional context, longer "
    "explanations, or tangents the user can expand if interested.\n"
    "  - ```comparison — two-column pros/cons card for a single option.\n"
    "  - ```answer — a highlighted final-answer pill for math results or quick Q&A.\n"
    "\n"
    "Writing helper (email, message, reply, caption, social post):\n"
    "  - Put the final send-ready text inside ```email, ```message, ```sms, or "
    "```copy. At most ONE such fence per response. For email/message to a named "
    "person, draft immediately — do not ask what to write.\n"
    "\n"
    "How-to / tips / roadmap / guide / troubleshooting:\n"
    "  - Use ## headings for phases or themes, then ```steps or numbered steps "
    "under each. NEVER put a roadmap, learning plan, tip list, or guide into a "
    "pipe table — multi-column tables are unreadable on a phone.\n"
    "\n" + MATH_INTENT_HINT + "\n"
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
    "- Make answers visually clear: use ```tip / ```note callouts for key "
    "takeaways, ```steps fences for procedures, and ## headings to group "
    "sections. Don't overuse — 1-2 callouts per long answer, not on every reply.\n"
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
        "and bullets — not essay-style paragraphs. Use a pipe table only for a true "
        "X vs Y / feature comparison. Include examples and nuance where useful."
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
    "Use the simplest structure that answers; do not add sections just to look structured."
)

# NOTE: response style (short/balanced/detailed) drives *brevity through the
# prompt* via STYLE_HINTS above — it no longer caps output tokens. A single
# high ceiling (settings.max_output_tokens) is the safety backstop; the daily
# token quota is the real per-user cost guardrail. Capping by style truncated
# large deliverables (HTML pages, graph JSON) mid-fence.
