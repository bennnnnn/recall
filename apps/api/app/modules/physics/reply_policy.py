"""Physics prompt hints. A physics turn must not be told it is doing math."""

PHYSICS_INTENT_HINT = (
    "Physics answers:\n"
    "  - This is a physics problem. Do not describe the work as math, algebra, "
    "or solving equations.\n"
    "  - When verified results appear in a [BEGIN VERIFIED PHYSICS] block, use "
    "those exact numbers and units. Do not recompute. If no verified block is "
    "present, do not claim verification.\n"
    "  - Never mention a system block, SymPy, or that a diagram will be attached.\n"
    "  - For a concrete calculation, use Given, Find, Formula, Substitution, "
    "then Answer, in that order. One equation per line, in inline `$...$`.\n"
    "  - Do NOT emit ```answer, ```graph, ```simulation, or ```geometry.\n"
    "  - A trajectory is only for kinematics, projectile motion, or spring and "
    "pendulum motion. Every other answer is a number with units.\n"
    "  - If no verified block is present, still put the result under Answer "
    "in inline `$...$` with units. Never end on that heading, and do not call "
    "the result verified. If there is no unique result, say what is missing "
    "instead of a blank Answer.\n"
    "  - Never join several transformations into one math row."
)

PHYSICS_SHORT_HINT = (
    "Physics in SHORT mode: give the result once, with units, in inline `$...$`. "
    "Do not describe the work as math. When a [BEGIN VERIFIED PHYSICS] block is "
    "present, use those exact numbers and do not recompute. Do NOT emit "
    "```answer, ```graph, ```simulation, or ```geometry. Never mention a system "
    "block or that a diagram will be attached. If no verified block is present, "
    "do not claim verification."
)

PHYSICS_REPLY_POLICY = (
    "Physics reply policy for this request: For a concrete calculation, use "
    "Given, Find, Formula, Substitution, then the final Answer. Put each value "
    "or equation on its own short line. One reasoning state per row; do not "
    "chain several equals signs. Name the governing formula before "
    "substituting. Do not add a math lesson, tutorial bullets, or Note/Tip "
    "cards, and do not repeat the result. Copy verified numbers and units; do "
    "not recompute them. Honor SHORT by giving less, and DETAILED by showing "
    "the working. For a hint or practice, give a focused hint without the full "
    "solution unless the user asked for it. The Answer line must state the "
    "result. Never end on the heading."
)
