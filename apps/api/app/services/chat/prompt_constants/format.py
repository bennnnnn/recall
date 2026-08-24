"""Response-format, comparison, and length-style hints.

The default response protocol is intentionally small: ordinary replies use
standard Markdown. App-specific rich fences are reserved for dedicated tool or
intent paths (math verification, drafts, graphs, geometry, etc.) instead of
being decorative choices the LLM has to remember on every turn.
"""

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
    "Add one column per option and one attribute per row. Prefer at most 3 "
    "columns and keep cells short. After the table, use at most 1-3 short "
    "bullets and give a clear recommendation if the user asked which to choose. "
    "Use proper GFM only: every row starts and ends with |; never wrap the table "
    "in a code fence; never use HTML in cells."
)


def is_comparison_question(text: str) -> bool:
    """True when the user is asking for an X vs Y / feature comparison."""
    cleaned = text.strip()
    if not cleaned:
        return False
    return bool(_COMPARISON_TURN.search(cleaned))


INTENT_FORMAT_HINT = (
    "Use standard Markdown for ordinary chat. Recall owns its special UI blocks; "
    "do not invent app-specific fences just to decorate an answer. In normal "
    "facts, explanations, recommendations, tips, and how-tos, do NOT emit "
    "```tip, ```note, ```warning, ```steps, ```details, ```comparison, ```kv, "
    "or ```answer unless another task-specific instruction explicitly requires "
    "that exact block.\n"
    "\n"
    "General chat:\n"
    "  - Lead with the answer. Use short paragraphs for simple questions.\n"
    "  - Use bullets for unordered facts/options and numbered lists for ordered "
    "steps, rankings, roadmaps, or procedures.\n"
    "  - Use ## headings only when the answer truly has multiple sections. A "
    "short answer should usually have no heading.\n"
    "  - For a single topic, prefer a short explanation plus a few bullets over "
    "a wall of prose or a synthetic key/value card.\n"
    "\n"
    "How-to / troubleshooting / roadmap:\n"
    "  - Use standard numbered Markdown steps. Use headings only for real phases. "
    "Never turn a guide, roadmap, checklist, or tip list into a pipe table.\n"
    "\n" + MATH_INTENT_HINT + "\n"
    "Coding:\n"
    "  - Give a brief approach when useful, then use a normal language-tagged "
    "code fence (```python, ```typescript, etc.), followed by concise notes.\n"
    "\n"
    "Decision / compare:\n"
    "  - ONLY for a true X vs Y / feature comparison, use a Markdown pipe table "
    "with Feature/Aspect as the first column and one column per option. Prefer "
    "2-3 columns total when possible.\n"
    "  - If there is only one tiny difference to explain, use prose or bullets "
    "instead of forcing a table."
)

RESPONSE_FORMAT_HINT = (
    "Default response protocol: standard Markdown, optimized for a phone.\n"
    "- Lead with the answer; do not preface it with filler.\n"
    "- Prefer bullets for unordered facts/options and numbered lists for ordered "
    "steps or rankings.\n"
    "- Keep paragraphs to 1-2 sentences when possible. Use ## headings only when "
    "they organize genuinely different sections.\n"
    "- Do not use decorative custom fences (tip/note/warning/steps/details/kv/etc.) "
    "unless a task-specific instruction explicitly requires one.\n"
    "- Use pipe tables ONLY for true comparisons (X vs Y / feature grids), never "
    "for tips, how-tos, roadmaps, checklists, or single-topic advice.\n"
    "- When a comparison table is appropriate, put it first; keep cells short; "
    "use proper GFM; never put tables inside code fences or HTML inside cells.\n"
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

# NOTE: response style (short/balanced/detailed) drives brevity through the
# prompt via STYLE_HINTS above — it no longer caps output tokens. A single high
# ceiling (settings.max_output_tokens) is the safety backstop; the daily token
# quota is the real per-user cost guardrail.
