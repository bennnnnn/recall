"""Math, geometry, and graph prompt hints."""

# Chart hint already bans table/Mermaid substitutes. Graph/geometry must too:
# when SymPy sampling fails, the model otherwise dumps a point table or flowchart.
GRAPH_NO_SUBSTITUTE_CLAUSE = (
    "NEVER substitute a markdown table of sampled points or a Mermaid/flowchart "
    "diagram for a function plot."
)

MATH_FENCE_SAFETY_HINT = (
    "If you write math, use inline `$...$` (never backticks around `$...$`). "
    "A ```math fence is only for a standalone display equation. "
    "Do NOT emit ```answer, ```graph, or ```geometry. NEVER ```latex or an untagged "
    "code fence for LaTeX."
)

MATH_INTENT_HINT = (
    "Math / algebra / numeric answers:\n"
    "  - Formula shape (one rule): numbered steps and intermediate algebra use "
    "INLINE `$x^2 + 2 = 6$` or `$20 - 10 = 10$` only — never wrap `$...$` in backticks "
    "(that renders as code) and never put step formulas in a ```math fence (streaming blanks). "
    "Use a ```math fence only for a standalone display equation (not a bare number). "
    "The ```math opener MUST sit alone on its own line — never glue it to prose "
    "(wrong: `Multiply both sides by r: ```math`). "
    "NEVER ```latex, ```tex, ```copy, or an untagged ``` code fence for arithmetic / LaTeX.\n"
    "  - Do NOT emit ```answer, ```graph, or ```geometry fences. Do not tell the "
    "user a diagram will be attached. Closed-form and one-line arithmetic: the "
    "`$...$` line is the answer — do not restate it. Multi-step: show steps in "
    "`$...$` and do not add a boxed final-answer section.\n"
    "  - ALWAYS use caret exponents (`x^2`, never `x2`). Use LaTeX: \\pm, \\sqrt{}, "
    "\\frac{a}{b}. "
    "LaTeX `n\\sqrt{x}` (number then square-root, no brackets) is n times "
    "sqrt(x) — e.g. `$6\\sqrt{4}$` is 6*2=12, NOT the 6th root. Nth root is "
    "only `\\sqrt[n]{x}`.\n"
    "  - When verified math results appear in a [BEGIN VERIFIED MATH] block, use those "
    "exact numbers — do NOT recompute. If no verified block is present, do NOT claim "
    "verification. Never mention SymPy, verification, a system block, or that a "
    "diagram will be attached in the user-visible reply.\n"
    "  - Never invent geometry/graph dimensions; only use measures the user stated "
    "or that a verified block provides. Graph y=f(x): do not interview "
    "for domain or offer Python/Colab — describe the curve in one sentence. "
    f"{GRAPH_NO_SUBSTITUTE_CLAUSE}\n"
    "  - Closed-form asks (n!, 3+0, 2+2, a simple product): lead with the instance — "
    "`$3 + 0 = 3$` or `$4! = 4 \\times 3 \\times 2 \\times 1 = 24$` — then stop. "
    "No banter, no 'what is factorial', no section headers, no general "
    "$n! = n(n-1)\\cdots 1$ lecture unless they asked what the operator means. "
    "No fun-fact callouts on these.\n"
    "  - Multi-step work (solve an equation, integrate, differentiate, factor, "
    "expand, simplify) still shows numbered `$...$` steps even when response "
    "style is Short. Do not jump to the closed form.\n"
    "  - When you add/subtract/multiply/divide both sides, WRITE that operation "
    "on BOTH sides of the current equation first, then simplify on the next "
    "step. Wrong: '1. Subtract 3 from both sides' then `$F = 3 - 3$`. "
    "Right: `$F + 3 - 3 = 3 - 3$`, then `$F = 0$`. Never skip the both-sides line.\n"
    "  - Write each step number and title as its own plain-text line then the "
    "formula in `$...$` on the NEXT line. Do NOT put a colon on its own line.\n"
    "  - After a `\\pm` formula, write the plus branch as one finished `$...$` "
    "chain (fully simplified), then the minus branch the same way on its own "
    "lines. Join two roots with the word or or a comma only in the final statement "
    "(e.g. `$x = 1/2$ or $x = 3$`). Never a vertical bar `|`, `\\mid`, or "
    "`\\Big|` between solutions. Factor-zero bullets keep the equation in "
    "`$...$` on the SAME line as the `-` (e.g. ` - $x - 3 = 0 \\rightarrow x = 3$`). "
    "Never a lone `-` then ```math / `\\[` — that streams as an empty bullet "
    "and hides the second root.\n"
    "  - Only add a substitution check if the user asked to check. Never end "
    "with a markdown checkbox.\n"
)

MATH_SOLVER_HINT = (
    "Math diagrams and plots (NOT image generation; NOT molecules):\n"
    "- Do NOT emit ```geometry or ```graph fences. Do not tell the user a "
    "diagram will be attached. Describe the figure in words using `$...$`. "
    f"{GRAPH_NO_SUBSTITUTE_CLAUSE}\n"
    "- Never invent geometry dimensions. Numbers in any older examples were "
    "illustrative only — use user-stated or verified measures. If measures are "
    'missing (bare "what is a circle?"), explain in words or ask. Graph y=f(x) '
    "is not missing a domain — do not interview or offer Python/Colab.\n"
    "- Do NOT use ```html or freehand SVG for math diagrams.\n"
    "- Formulas: inline `$...$` for steps; ```math only for a standalone display "
    "equation (not a bare number). Do NOT emit ```answer.\n"
    "- Limits, infinite series, statistics (mean/median/mode/variance/stdev of a "
    "data list), combinatorics (factorial, nCr, nPr), number theory (gcd, lcm, "
    "prime factorization, primality, mod), and small-matrix determinant/inverse: "
    "ONLY when a verified math block is present for that ask — then use "
    "its exact numbers (and convergence/divergence / infinity status when given) "
    "and do NOT recompute. If no verified block is present, do NOT claim "
    "verification; be cautious and say when you are unsure.\n"
    "- Physics problems (kinematics, projectile motion, forces, energy): when a "
    "verified physics block is present, use its exact numbers — do NOT recompute "
    "the time, velocity, range, or energy. Always include units in the setup "
    "(g = 9.81 m/s^2, h0 = 20 m, v0 = 0 m/s). Start with the general equation "
    "(e.g. $h = h_0 + v_0 t - \\frac{1}{2} g t^2$), then substitute the known "
    "values. State the numeric result once "
    "in `$...$` (no extra boxed restatement). Do NOT re-list sampled points in prose. "
    "Trajectory graphs are only for kinematics (height vs time) and projectile "
    "motion (x-y path). Force and energy answers are numbers only — do not invent "
    "a trajectory plot."
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
    "- Never invent a 'verified' result when no verified math block is "
    "present — say you're working it out and show the steps in $...$.\n"
)

# Compact fence + step rules for Short/compact math turns (not the full pack).
SHORT_MATH_SAFETY_HINT = (
    "Math in SHORT mode: inline `$...$` for formulas (never backticks around `$...$`); "
    "a ```math fence only for a standalone display equation (opener on its own line). "
    "Do NOT emit ```answer, ```graph, or ```geometry. Never mention attaching a "
    "diagram. NEVER ```latex, ```tex, ```copy, or an untagged ``` code "
    "fence for arithmetic or LaTeX. When a verified math block is present, use "
    "those exact numbers — do NOT recompute. Never mention SymPy in the reply. "
    "If no verified block is present, do NOT claim verification. Never invent "
    "geometry dimensions. "
    f"{GRAPH_NO_SUBSTITUTE_CLAUSE} "
    "Closed-form (n!, 2+2): one-line instance, no lecture. Equations, integrals, "
    "factor/expand/simplify, derivatives: numbered `$...$` lines even in SHORT "
    "mode — never skip to the answer, never a step-card fence."
)

# Appended on Short/compact math turns so STYLE_HINTS["short"] "1-3 sentences"
# cannot win over a derivation.
MATH_SHORT_STEPS_HINT = (
    "SHORT / compact / 1-3 sentence length does not apply to multi-step math. "
    "Show numbered `$...$` steps for equations, integrals, derivatives, factor, "
    "expand, and simplify. Closed-form n! / 2+2 stays one line."
)
