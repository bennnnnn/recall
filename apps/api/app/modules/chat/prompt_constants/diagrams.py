"""Mermaid diagram cues and hints: flowcharts, sequence diagrams and named kinds."""

import re

from app.services.diagram_kinds import names_diagram_kind

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


_DRAW_CUE = re.compile(
    r"\b(?:draw|sketch|show|make|create|render|generate|build|design|map\s+out)\b",
    re.IGNORECASE,
)
_HOW_DO_I = re.compile(r"\bhow\s+(?:to|(?:do|can|should)\s+(?:i|you|we))\b", re.IGNORECASE)

DIAGRAM_KIND_HINT = (
    "This turn names a diagram Recall draws from a ```mermaid fence. Lead with that "
    "fence — never an image, HTML/SVG, ASCII art, or a list in its place, and no joke "
    "setup. At most one short sentence, then the fence. Use the Mermaid type that fits "
    "what they named:\n"
    "- decision tree, org chart, family tree, process map: flowchart TD; a question is a "
    "diamond Q{Need speed?} with labelled edges Q -->|Yes| A[Go]\n"
    "- state machine or state diagram: stateDiagram-v2 with [*] --> Red and "
    "Red --> Green : timer\n"
    "- mind map or concept map: mindmap, then root((Topic)) with each child indented two "
    "spaces more than its parent; plain words only, no brackets or parentheses\n"
    "- ER diagram: erDiagram with MEMBER ||--o{ LOAN : borrows\n"
    "- class diagram: classDiagram; Gantt chart: gantt; user journey: journey\n"
    'In a flowchart, quote a label that needs parentheses: A["Grind beans (medium)"].'
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
    if is_sequence_diagram_question(cleaned) or is_diagram_kind_question(cleaned):
        return True
    if _FLOWCHART_CUE.search(cleaned):
        return True
    return bool(_MERMAID_WORD.search(cleaned) and _MERMAID_RENDER_CUE.search(cleaned))


def is_diagram_kind_question(text: str) -> bool:
    """True for "draw a state machine", "make a mind map": a named diagram to draw.
    "What is a decision tree?" and "how do I make a mind map?" are not."""
    return (
        names_diagram_kind(text)
        and _DRAW_CUE.search(text) is not None
        and _HOW_DO_I.search(text) is None
    )


def mermaid_format_hint(text: str) -> str | None:
    """The hint for a requested Mermaid diagram, most specific first."""
    if is_sequence_diagram_question(text):
        return SEQUENCE_FORMAT_HINT
    if is_diagram_kind_question(text):
        return DIAGRAM_KIND_HINT
    if is_mermaid_question(text):
        return MERMAID_FORMAT_HINT
    return None
