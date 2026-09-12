"""Math, geometry, and graph prompt hints."""

# Chart hint already bans table/Mermaid substitutes. Graph/geometry must too:
# when SymPy sampling fails, the model otherwise dumps a point table or flowchart.
GRAPH_NO_SUBSTITUTE_CLAUSE = (
    "NEVER substitute a markdown table of sampled points or a Mermaid/flowchart "
    "diagram for a function plot."
)

MATH_NOTATION_CLARIFICATION_HINT = (
    "If mathematical notation is unclear, unrecognized, or malformed, ask one brief "
    "clarification instead of guessing its meaning. Do not invent a named mathematical "
    "concept or silently change the expression. Standard, unambiguous notation aliases "
    "are fine."
)

MATH_FENCE_SAFETY_HINT = (
    "If you write math, use inline `$...$` (never backticks around `$...$`). "
    "A ```math fence is only for a standalone display equation. "
    "Do NOT emit ```answer, ```graph, or ```geometry. NEVER ```latex or an untagged "
    "code fence for LaTeX. "
    f"{MATH_NOTATION_CLARIFICATION_HINT}"
)

MATH_INTENT_HINT = (
    "Math / algebra / numeric answers:\n"
    f"  - {MATH_NOTATION_CLARIFICATION_HINT}\n"
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
    "  - Default to a concise answer: give the result once, with only the key "
    "transformation or rule needed to understand it. A simple root, derivative, "
    "integral, factorization, or equation does not need a numbered tutorial. "
    "Example: `$\\sqrt[6]{9} = 3^{1/3} = \\sqrt[3]{3} \\approx 1.442$`, "
    "followed only if useful by 'Since $9 = 3^2$, divide the exponent by 6.' "
    "Do not repeat the exact answer in a heading, summary, or Note/Tip callout.\n"
    "  - Honor Short mode and explicit requests for just the answer. Show a "
    "full derivation when the user asks for steps, explanation, or a proof; "
    "use numbered steps only when the reasoning needs distinct stages. "
    "Keep a short step label and its formula together when they fit.\n"
    "  - Every equality must remain valid. When explaining an operation on "
    "both sides, apply it to BOTH sides and keep the explanation consistent "
    "with the formula. Routine steps may be combined into a valid equation chain.\n"
    "  - Preserve domains, excluded values, units, constants of integration, "
    "and all solution branches even in a short answer. Write fractional "
    "exponents as `x^{1/6}` with the whole exponent in braces, not `x^1/6`.\n"
    "  - Simplify both branches of a `\\pm` solution; expand their arithmetic "
    "only when explanation is requested. Join two roots with the word or "
    "or a comma "
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
    "(e.g. g = 9.81 m/s^2 on Earth, with the given h0 and v0). Start with the "
    "general equation, then substitute the known values. State the numeric "
    "result once in `$...$` (no extra boxed restatement). Do NOT re-list sampled "
    "points in prose. Do NOT emit ```graph. Trajectory graphs are only for kinematics "
    "(height vs time) and projectile motion (x-y path). Force and energy answers "
    "are numbers only — do not invent a trajectory plot."
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
    "Closed-form (n!, 2+2): one-line instance, no lecture. Use braced fractional "
    "exponents such as `9^{1/6}`. Preserve domains, units, all solution branches, "
    "and constants of integration. Never use a step-card fence. "
    f"{MATH_NOTATION_CLARIFICATION_HINT}"
)

# Math should respect the user's selected length without dropping correctness.
MATH_SHORT_RESPONSE_HINT = (
    "SHORT / compact math: honor the user's brevity preference. Give the result "
    "once and at most the key transformation needed to understand it. Simple "
    "roots, equations, derivatives, integrals, factor/expand/simplify need no "
    "numbered tutorial. No repeated answer, recap, or Note/Tip callout. "
    "If the user asks for just the answer, omit the derivation. If they ask "
    "for steps, explanation, or a proof, provide the necessary reasoning. "
    "For practice or a request for a hint, give a focused hint instead of "
    "revealing the full solution."
)
