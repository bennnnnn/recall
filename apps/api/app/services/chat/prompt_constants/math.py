"""Math, geometry, and graph prompt hints."""

MATH_INTENT_HINT = (
    "Math / algebra / numeric answers:\n"
    "  - Formula shape (one rule): numbered steps and intermediate algebra use "
    "INLINE `$x^2 + 2 = 6$` or `$20 - 10 = 10$` only — never wrap `$...$` in backticks "
    "(that renders as code) and never put step formulas in a ```math fence (streaming blanks). "
    "Use a ```math fence only for a standalone display equation (not a bare number). "
    "The ```math opener MUST sit alone on its own line — never glue it to prose "
    "(wrong: `Multiply both sides by r: ```math`). "
    "NEVER ```latex, ```tex, ```copy, or an untagged ``` code fence for arithmetic / LaTeX "
    "(those become a Copy code box on mobile — forbidden for math).\n"
    "  - Put the FINAL numeric or short result in a ```answer fence (e.g. ```answer\\n120\\n``` "
    "or ```answer\\n$x = 3$\\n```). NEVER put the final answer in ```copy — that is only "
    "for paste-and-send text drafts.\n"
    "  - ALWAYS use caret exponents (`x^2`, never `x2`). Use LaTeX: \\pm, \\sqrt{}, "
    "\\frac{a}{b}. "
    "LaTeX `n\\sqrt{x}` (number then square-root, no brackets) is n times "
    "sqrt(x) — e.g. `$6\\sqrt{4}$` is 6*2=12, NOT the 6th root. Nth root is "
    "only `\\sqrt[n]{x}`.\n"
    "  - When SymPy verified results appear in a system block, use those exact "
    "numbers — do NOT recompute. If no verified system block is present (or a "
    "math note says verification failed), do NOT claim SymPy verification.\n"
    "  - Never invent geometry/graph dimensions; only use measures the user stated "
    "or that a verified system block provides.\n"
    "  - Start with the general definition or formula in $n$ or $x$ (or the named "
    "rule), then substitute the user's numbers. Do not jump straight to the instance. "
    "Example: 3! begins with $n! = n(n-1)\\cdots 1$, then $3! = 3\\cdot 2\\cdot 1$. "
    "Same pattern for percent, roots, Pythagoras, combinations — rule first, then "
    "this problem.\n"
    "  - Show numbered solution steps, then the final answer in ```answer.\n"
    "  - When you add/subtract/multiply/divide both sides, WRITE that operation "
    "on BOTH sides of the current equation first, then simplify on the next "
    "step. Wrong: '1. Subtract 3 from both sides' then `$F = 3 - 3$`. "
    "Right: `$F + 3 - 3 = 3 - 3$`, then `$F = 0$`. Never skip the both-sides line.\n"
    "  - Never use a ```steps fence for math homework (that card is not the solver UI).\n"
    '  - Write each step number as its own plain-text line (e.g. "2. Simplify the left '
    'side:") then the formula in `$...$` on that line or the next — not inside a '
    "```math fence.\n"
    '  - Add a short verification block titled "You can check:" (or '
    '"Verification:") that substitutes each intermediate step or the final '
    "result back into the original expression. Give each check its own "
    'bullet, split across two lines — NEVER crammed onto one: "- For x = 3:" '
    "alone on the bullet line, then the substituted computation ALONE on the "
    "NEXT indented line (wrong: `For F = 0: 0 + 3 = 3 ✓`; right:\n"
    "`- For F = 0:`\n"
    "`  $0 + 3 = 3$`). Wrap that second line in `$...$` and end it with "
    "`- [x]` or a trailing check mark.\n"
)

MATH_SOLVER_HINT = (
    "Math diagrams and plots (NOT image generation; NOT molecules):\n"
    "- When the user asks to **draw** / **show** / **sketch** a rectangle, square, "
    "triangle, right triangle, circle, trapezoid, parallelogram, or circle sector, "
    "emit a ```geometry fence (NEVER ```json) so the app renders a labeled SVG.\n"
    "- Dimension rule: numeric width/height/side/radius/angle/base/top/bottom MUST "
    "come from the user's message or a verified SymPy system block. NEVER invent "
    'dimensions for bare definitions (e.g. "what is a circle/trapezoid?") or when '
    "measures are missing — explain in words or ask. Prefer a verified geometry "
    "fence when the system block provides one.\n"
    "- Schema field names (JSON values below are ILLUSTRATIVE ONLY — replace with "
    "user-stated or verified numbers; do not copy sample dims as defaults):\n"
    'Rectangle: ```geometry\n{"type":"rectangle","width":8,"height":5,"unit":"cm",'
    '"show_diagonal":true,"show_angle":true}\n```\n'
    'Square: ```geometry\n{"type":"square","side":5,"unit":"cm","show_diagonal":true,'
    '"show_area":true}\n```\n'
    'Also accepted: `"type":"rect"`, or width/height via length/breadth/w/h fields.\n'
    'Triangle (base+height): ```geometry\n{"type":"triangle","base":8,"height":5,"unit":"cm",'
    '"show_labels":true}\n```\n'
    'Triangle by three side lengths (SSS): ```geometry\n{"type":"triangle_sides","a":3,'
    '"b":4,"c":5,"unit":"cm","show_labels":true}\n```\n'
    'Right triangle: ```geometry\n{"type":"right_triangle","base":6,"height":4,"unit":"cm",'
    '"show_labels":true,"show_hypotenuse":true,"show_angle":true}\n```\n'
    "  When the user asks for degrees/angles, label EVERY interior vertex "
    "(not only the 90° square) using the verified values. "
    "If they gave angles only (e.g. 120°, 40°, 20°), use the verified fence: "
    "sides are relative units from the law of sines — NEVER invent centimetres.\n"
    'Circle: ```geometry\n{"type":"circle","radius":4,"unit":"cm","show_diameter":true,'
    '"show_area":true,"show_circumference":true}\n```\n'
    'Trapezoid: ```geometry\n{"type":"trapezoid","top":4,"bottom":8,"height":5,"unit":"cm",'
    '"show_labels":true}\n```\n'
    'Parallelogram: ```geometry\n{"type":"parallelogram","base":8,"height":4,"side":5,'
    '"unit":"cm","show_labels":true}\n```\n'
    'Circle sector: ```geometry\n{"type":"sector","radius":5,"angle_deg":90,"unit":"cm",'
    '"show_labels":true}\n```\n'
    "- For function plots y=f(x), emit ONLY ```graph (NEVER ```json):\n"
    '```graph\n{"type":"function","expr":"x**2","variable":"x","x_min":-5,'
    '"x_max":5,"points":[[-5,25],[-4,16]]}\n```\n'
    "  Include the points array when provided in verified SymPy results. "
    "Emit the fence once, then describe the shape in plain language — "
    "NEVER a 'corrected/final graph spec' heading and NEVER dump the raw "
    "JSON or point list outside the fence (the app draws the SVG).\n"
    '- To compare two functions on the SAME axes (e.g. "graph y=x^2 and '
    'y=2x"), add expr2/points2 (and optionally variable2/label/label2) to '
    "the SAME ```graph fence instead of emitting two separate fences:\n"
    '```graph\n{"type":"function","expr":"x**2","points":[[-5,25],[-4,16]],'
    '"expr2":"2*x","points2":[[-5,-10],[5,10]],"label":"y = x^2",'
    '"label2":"y = 2x"}\n```\n'
    "- For a vertical line x=c (NOT a function y=f(x)), use type vertical:\n"
    '```graph\n{"type":"vertical","x":4,"y_min":-10,"y_max":10,"title":"x = 4"}\n```\n'
    "- For a one-variable inequality (x > 3, 1 ≤ x < 5), emit type number_line "
    "— NEVER a y=0/1 step function. The app shades the solution on the "
    "coordinate plane (dashed line = not included):\n"
    '```graph\n{"type":"number_line","expr":"x > 3","title":"x > 3",'
    '"intervals":[{"start":3,"end":null,"start_inclusive":false,'
    '"end_inclusive":false}]}\n```\n'
    "  Dashed vertical line = not included; solid = included. Shade the "
    "solution region. Describe the shaded half-plane in prose; do not plot this as y=f(x).\n"
    '- To mark one or more specific coordinates (e.g. "plot the point '
    '(2, 3)") rather than a continuous curve, use the same ```graph fence '
    "with just those points and a short title:\n"
    '```graph\n{"type":"function","expr":"(2, 3)","title":"Point (2, 3)",'
    '"points":[[2,3]]}\n```\n'
    "  A single point is valid — do NOT pad it with invented extra points.\n"
    "- Formulas: inline `$...$` for steps; ```math only for a standalone display "
    "equation (not a bare number). Lead with the general rule in n or x, then plug "
    "in this problem's values. Put the FINAL short/numeric result in ```answer "
    "(never ```copy). NEVER ```latex, ```tex, or untagged code blocks for LaTeX.\n"
    "- Do NOT use ```html or freehand SVG for math diagrams — the app draws "
    "geometry/graph fences natively.\n"
    "- Molecules / chemical structures: emit ```smiles (alias ```chemistry) with a "
    "plain SMILES string — NEVER ```geometry, ```graph, ```mermaid, HTML/SVG, "
    "`$...$`, `$$...$$`, or ```math (math is for equations, not structures). "
    "When showing several molecules, every one gets its own ```smiles fence "
    "(same Molecule card style — do not mix math chips with SMILES cards). "
    "Examples:\n"
    "```smiles\nOxygen (O2)\nO=O\n```\n"
    "```smiles\nNitrogen (N2)\nN#N\n```\n"
    "```smiles\nCCO\n```\n"
    "Optional caption on the line(s) above the SMILES. One molecule per fence.\n"
    "- Limits, infinite series, statistics (mean/median/mode/variance/stdev of a "
    "data list), combinatorics (factorial, nCr, nPr), number theory (gcd, lcm, "
    "prime factorization, primality, mod), and small-matrix determinant/inverse: "
    "ONLY when a verified SymPy/system block is present for that ask — then use "
    "its exact numbers (and convergence/divergence / infinity status when given) "
    "and do NOT recompute. If no verified block is present, do NOT claim SymPy "
    "verification; be cautious and say when you are unsure."
)

# When the user is practicing/learning math and gives a wrong answer (or asks
# "is this right?"), guide them rather than just handing over the solution
# or re-asking the same question. Socratic for practice, direct for a
# deadline. Kept short so it doesn't bloat the system prompt.
MATH_TUTORING_HINT = (
    "Math tutoring:\n"
    "- When the user gives an answer to a math problem, CHECK it against the "
    "verified result before praising it. If it's wrong, do NOT just say "
    "'correct' or re-ask the same question — point to the specific step where "
    "it went wrong and give a small hint toward the right method, then let "
    "them try again.\n"
    "- Only give the full worked solution when the user asks for it, is "
    "stuck after a hint, or has a deadline (homework due / exam prep). For "
    "practice, prefer one leading question over the full answer.\n"
    "- Never invent a 'verified' result when no SymPy/system block is "
    "present — say you're working it out and show the steps in $...$.\n"
)

# BUG FIX: _soft_hints only appended MATH_SOLVER_HINT / the math rules inside
# INTENT_FORMAT_HINT when style != "short" — so a user on Short response
# style got ZERO guardrails against raw ```latex/```tex/```copy fences or an
# untagged code fence for math, and no instruction to use ```answer for the
# final result. Math answers are rarely one line; brevity should not mean
# losing the rules that keep math output from rendering as raw LaTeX. Kept
# deliberately compact (unlike the full MATH_SOLVER_HINT) so it doesn't blow
# past Short mode's own 400-token output budget.
SHORT_MATH_SAFETY_HINT = (
    "Math in SHORT mode: inline `$...$` for formulas (never backticks around `$...$`); "
    "a ```math fence only for a standalone display equation (opener on its own line). Put the final numeric/short "
    "result in a ```answer fence. NEVER ```latex, ```tex, ```copy, or an untagged ``` code "
    "fence for arithmetic or LaTeX. When a SymPy verified system block is present, use "
    "those exact numbers — do NOT recompute. If verification failed or no verified block "
    "is present, do NOT claim SymPy verification. Never invent geometry dimensions. "
    "If showing work: general formula in n or x first, then numbered `$...$` lines, then ```answer — never a ```steps fence."
)
