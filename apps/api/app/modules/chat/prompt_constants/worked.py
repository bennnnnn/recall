"""The ```worked block: a calculation no solver checked, written as parts the app lays out.

Told the worked layout in words, the model followed it on one turn and not the next: a
displacement came back as bold inline "**Given:** …", no Answer heading and no card
(2026-11-01). The block's records are read and laid out by the server
(``chat.worked_solution``, ``chat.worked_render``) with the renderer of every verified
reply, so a reply the model works out itself looks the same as a checked one.
"""

from __future__ import annotations

WORKED_BLOCK_CONTRACT = (
    "Worked calculation: this question asks for a value and no server check stands behind "
    "it, so the app lays your working out itself, the same way as every checked answer "
    "(Given, Required, Solution, the formula under its name, Substitution, Answer). Start your reply with one ```worked "
    "block holding the whole solution, and write no working outside it: no heading, no "
    "sentence before it, no Given, Formula, Step or Answer lines of your own, also when the "
    "sum is short. Nothing after the block restates the answer either: its card already "
    "shows each value, so add no closing sentence repeating them. Only a message that asks for no value at all (an explanation, a "
    "definition, a choice between options, a reminder) is answered as usual, with no "
    "block. A graph, chart or diagram it asks for comes after the block. "
    'Inside the block, one record per line, its fields split by " | ", maths in LaTeX '
    "without $, units as plain text (m/s, km/h, kg, °C), and words in the language of "
    "your reply:\n"
    "given: symbol | value | unit | what it is | the value in the unit the formula needs, "
    "only when that differs (LaTeX with its unit)\n"
    "required: symbol | what is asked\n"
    'formula: the name of the law or rule, which heads the formula ("Average speed" '
    "reads Average speed formula) | the formula\n"
    "solve_for: symbol | the formula rearranged for it\n"
    "step: an equation | the move that reached it (for an equation solved one move at a "
    "time, with no formula)\n"
    "substitution: the values put into the formula, one state per line, the last one the "
    "value with its unit\n"
    "answer: symbol | value | unit | a direction or a label of a few words (east, to 3 "
    "s.f.), only if the answer needs one; an explanation or a comparison goes in one "
    "sentence after the block, never in the answer\n"
    "A question in parts, or two questions in one message (each a part, also when they "
    "use one formula), has a `part` record for each part. Write every given first, all "
    "of them before anything else: a given every part uses as `given:`, and a given only "
    "one part uses with that part's letter, `given (a): t | 1 | s | time`, so two values "
    "of one symbol never meet. Then one `required` per part, in order; then for each part "
    "`part: a | what it finds`, its formula, substitution and answer, and never a given "
    "after a `part` line. Before the "
    "answer record, check the result: put it back into the formula and redo each "
    "multiplication and division. For example:\n"
    "```worked\n"
    "given: d | 3 | km | distance | 3000\\,\\mathrm{m}\n"
    "given: t | 15 | min | time | 900\\,\\mathrm{s}\n"
    "required: v | average speed\n"
    "formula: Average speed | v = \\frac{d}{t}\n"
    "substitution: v = \\frac{3000}{900}\n"
    "substitution: v = 3.33\\,\\mathrm{m/s}\n"
    "answer: v | 3.33 | m/s\n"
    "```"
)

# Live (2026-11-02): "My answers: 1) 1 mol 2) 110 g 3) 4.5 x 10^23 molecules 4) 2 mol. Did I
# get them right?" got the worked contract, and the model opened "I can't see the answers you
# wrote", worked all four problems again and named one slip in passing. A message that only
# states results to check gets this instead (``chat.worked_turn``).
RESULT_CHECK_CONTRACT = (
    "The user's last message states their own results (to the problems earlier in this "
    "chat, or to the one it names) and asks whether they are right. The results are in "
    "that message: read them from it, and never say you cannot see them. Go through them in "
    "the problems' order, one line each and each verdict once: the right value with the one "
    "sum that gives it (its ratio, unit and power of ten included), then their result and "
    "whether it matches; when it does not, the slip in a few words. For example: "
    '"1) 36 g ÷ 18.0 g/mol = 2.0 mol. Yours: 2 mol, right." and "2) 12 N ÷ 3 kg = '
    '4 m/s². Yours: 36 m/s², not right: the force is divided by the mass, not multiplied." '
    "A result that differs from the right one only by rounding is right. No other working "
    "and no ```worked block. Close with one line on how they did. Open with the first line, "
    "not a heading or a title."
)
