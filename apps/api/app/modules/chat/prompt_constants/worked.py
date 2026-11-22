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
    "without $, units as plain text (m/s, km/h, kg, °C), one symbol for each quantity in "
    "every record (a letter, with a subscript when it needs one: A, r, h_1, never a word "
    "such as area or radius), and words in the language of your reply. A maths field "
    "holds maths alone: no label before it (Simplify:, Check:), no words after it (where "
    "…, always true), never a $; a remark is a `say` record of its own:\n"
    "language: the code of the language you write this reply in (en, es, fr, pt, ru, tr, am "
    "or hi), the first record: every word of the block is in it, and the app writes the "
    "layout's headings in it\n"
    "given: symbol | value | unit (empty for a pure number) | what it is | the value in the "
    "unit the formula needs, only when that differs (LaTeX with its unit)\n"
    "required: symbol | what is asked\n"
    'formula: the name of the law or rule in words, which heads the formula ("Average speed" '
    "reads Average speed formula; a name that says what it is stays as it is: Ohm's law, "
    "Integrating factor method) | the formula\n"
    "solve_for: symbol | the formula rearranged for it\n"
    "step: an equation | the move that reached it, the equation first (for an equation "
    "solved one move at a time, with no formula)\n"
    "substitution: the values put into the formula, one state per line, the last one the "
    "value with its unit, never rounded; a value an earlier part found goes into a later "
    "part unrounded\n"
    "say: a sentence in words, never a formula: what a part asked in words says (what "
    "numbers mean, why something happens), or a remark the working needs; its maths only "
    "between $ and $\n"
    "answer: symbol | value | unit | a direction (east), only if the answer needs one; "
    "never what the value is (length, area, exact value): Required says that, and an "
    "explanation or a comparison goes in one sentence after the block, never in the answer. Each value has its own answer record; a vector answers "
    "with its components (`answer: \\vec{v} | -16\\hat{i} + 20\\hat{j} | m/s`) or with its "
    "size and direction (`answer: v | 25.6 | m/s | 51.3° north of west`). Its value is the working's last one as it stands, never "
    "rounded: the app rounds every card. A part asked as yes or no (Does it…? Is it…?) answers with the conclusion in "
    "words, never a number (`answer: | yes, all the ice melts | |`), its number in the "
    "working above it. A part asked in words (what a label means, why something happens) "
    "has its `say` lines and answers in one sentence of its own, its numbers in it "
    "(`answer: | Its speed rises by $5$ m/s every second | |`); every other part still has "
    "its own answer record\n"
    "A question in parts, or two questions in one message (each a part, also when they "
    "use one formula), has a `part` record for each part: the question's own parts, with "
    "its letters, never more. One question asking one thing, even several values of it "
    "(all three sides, both legs), has no `part` record; one asking several things in "
    "words (its area, then its inradius) has a part for each. Write every given first, all "
    "of them before anything else, each as `given:` whichever parts use it (a given is "
    "data, not a part); only a symbol two parts give different values has each value "
    "with its part's letter, `given (a): d | 100 | m | distance` and `given (b): d | 300 "
    "| m | distance`, so two values of one symbol never meet. Then one `required` per "
    "part, in order; then for each part "
    "`part: a | what it finds`, its formula, substitution and answer, and never a given "
    "after a `part` line. Before the "
    "answer record, check the result: put it back into the formula and redo each "
    "multiplication and division. For example:\n"
    "```worked\n"
    "language: en\n"
    "given: d | 3 | km | distance | 3000\\,\\mathrm{m}\n"
    "given: t | 15 | min | time | 900\\,\\mathrm{s}\n"
    "required: v | average speed\n"
    "formula: Average speed | v = \\frac{d}{t}\n"
    "substitution: v = \\frac{3000}{900}\n"
    "substitution: v = 3.33\\,\\mathrm{m/s}\n"
    "answer: v | 3.33 | m/s\n"
    "```"
)

# Said beside the contract when the question letters its parts (``worked_turn``): asked
# "a) The altitude. b) The lengths of both legs. c) The area", the model gave each leg a
# part of its own and the layout lettered four parts (a) to (d); asked "a) center b) radius c)
# tangent d) area", it wrote no part records and the tangent's working went under (b)
# (hard geometry round, 2026-11-21).
WORKED_PARTS_NOTE = "This question is in lettered parts"


def worked_parts_note(parts: tuple[str, ...]) -> str:
    """The note naming the question's parts, each by its letter and its own words."""
    listed = "; ".join(
        f"({chr(ord('a') + index)}) {' '.join(words.split()).rstrip(' .;')}"
        for index, words in enumerate(parts)
    )
    return (
        f"{WORKED_PARTS_NOTE}: {listed}. Write exactly {len(parts)} `part` records, one for "
        "each, with its letter, in this order (`part: a | what (a) finds`), after every "
        "given and every `required`. Under each part go its own formula, substitution and "
        "answer records only, nothing another part finds; a part asking for two values "
        "(both legs, BD and DC) has an answer record for each under that one part."
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
