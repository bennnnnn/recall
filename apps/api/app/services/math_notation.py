"""The maths rules both maths' pack and chat's every-turn maths-ink rule state.

Maths' pack (``modules/math/reply_policy``) quotes them, and so does the maths-ink rule every
turn gets (chat's ``prompt_constants/math``), so they sit below both.
"""

MATH_NOTATION_CLARIFICATION_HINT = (
    "If mathematical notation is unclear, unrecognized, or malformed, ask one brief "
    "clarification instead of guessing its meaning. Do not invent a named mathematical "
    "concept or silently change the expression. Standard, unambiguous notation aliases "
    "are fine. A bare log is base 10, as on a school calculator; write the natural log "
    "as ln."
)

# A plot or a shape is the app's to draw, from a verified block. Without one the model drew
# a table of points, a flowchart, or the shape itself: "I asked for the triangle" got a
# triangle of slashes in a ```text block, and in a probe a bar ```chart (2026-11-09).
GRAPH_NO_SUBSTITUTE_CLAUSE = (
    "NEVER substitute a markdown table of sampled points, an ASCII or text-art sketch, "
    "or a Mermaid/flowchart diagram for a function plot. Never draw a geometric shape "
    "yourself, in characters, a ```chart, Mermaid, SVG or HTML: the app draws shapes from "
    "a verified math block. When the user asks to see a shape and no verified math block "
    "is present, say in one sentence that you can't draw it here, then describe it in words."
)
