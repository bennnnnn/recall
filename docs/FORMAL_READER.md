# Formal reader: the model writes the question down as maths, the server computes

Owner (2026-11-16): "Don't try to solve the problem by having different wordings. We need a
system that understands different wordings. A checked answer need not be verified as long as
it is correct. A list of different wordings in all the languages is bad."

## The idea

Models rarely misread a STEM question. They slip on the arithmetic, the algebra or the units.
So the work is split by what each side does well:

1. **The model reads.** Any wording, any language. It writes the question down as maths
   (`services/formal/problem.py`): each given value with its unit and the question's own
   words for it, the unknowns with their units, the equations of the science that join
   them, the target and the unit asked. It names no catalog law and matches no phrase. It
   also gives its own final answer.
2. **The server computes and checks** (`services/formal/solve.py`, in the SymPy pool):
   - every given's words are in the question and say its number (a count in words, "dos
     resistencias", up to twelve);
   - a constant the question does not state is a standard one (`formal/constants.py`);
   - an equation is plain arithmetic in the setup's symbols, walked as a tree
     (`law_binding/expression.parse`), never executed, and writes no value of its own
     (only factors like 2 or 1/2);
   - both sides of every equation are the same kind of quantity (pint), and a sine's
     argument has no unit;
   - SymPy solves the system; a value the physics rules out (a negative time) is set
     aside; the solution satisfies every equation when put back;
   - the answer is in the unit the question asked for.
3. **Agreement.** The server's answer and the model's own are compared (1%). In every
   measurement below, a setup whose answer agreed with the model's was never wrong.

The physics reader is `modules/physics/formal_read.py`. Maths and chemistry would bring
their own prompt over the same engine.

## Measured (2026-11-16, OpenRouter, `app/tests/behavior/formal_eval.py`)

Questions: the physics holdout (written after the fixes, never tuned on), 45 of them
reworded the way students type (`formal_corpus/physics_reworded.json`: text-message style,
values reordered, an irrelevant aside) and 30 of them translated into Spanish, French,
Amharic and Russian (`formal_corpus/physics_translated.json`). The measure is a correct
final number (1%, any unit of the same kind), not a verified one.

- **today**: the app's own solver when it answers, else the reply model alone.
- **formal**: today's solver when it answers; else the server's answer to the model's
  setup when it agrees with the model's own; else the reply model alone.

| Set | Questions | App's solver reads | Today, Free (Qwen 3.7 Flash) | Formal, Free | Today, paid (smart-chat) | Formal, paid |
|---|---|---|---|---|---|---|
| English holdout | 89 | 89 | 89 (100%) | 89 (100%) | 89 (100%) | 89 (100%) |
| English reworded | 45 | 35 | 45 (100%) | 45 (100%) | 45 (100%) | 45 (100%) |
| Spanish | 30 | 0 | 26 (87%) | 30 (100%) | 30 (100%) | 30 (100%) |
| French | 30 | 0 | 25 (83%) | 30 (100%) | 30 (100%) | 30 (100%) |
| Amharic | 30 | 0 | 26 (87%) | 29 (97%) | 29 (97%) | 29 (97%) |
| Russian | 30 | 0 | 24 (80%) | 29 (97%) | 20 (67%) | 30 (100%) |
| **Translated, all** | **120** | **0** | **101 (84%)** | **118 (98%)** | **109 (91%)** | **119 (99%)** |

The setup was written by smart-chat; with GPT-6 Luna writing it, the translated sets reach
114 (95%) for Free and 116 (97%) for paid.

- **Safety:** across both setup writers and every set, 430 setups agreed with the model's
  own answer, and none of them was wrong.
- **Reach:** a setup was solved and agreed for 89–93% of the translated questions and
  71–80% of the reworded ones, with no word rule; refusals fall back to today's path.
- **English:** the solver reads the holdout whole and 35 of 45 rewordings; the model alone
  answered the other ten correctly, so English shows no gain on these sets.
- **Escalation** (the stronger model writes the setup again on a disagreement) changed
  nothing measurable; it is not worth its call.

Refusals, by count over both writers and all sets: `no setup` (the model left out the
target), a symbol no equation gives the kind of, `no real solution`, units of an equation, a
constant outside the table (`n_air`, a spring's `k` taken for Coulomb's), a quote the
question does not hold, a unit pint does not read.

## What it would take to use it

- **Where:** a STEM turn the app's solver did not answer, which today goes to the model
  alone. That covers every non-English question.
- **How, without slowing the reply:** the setup is read beside the reply, as the figure
  read is. At finalize, the server's answer is compared with the reply's final number. On
  a disagreement where the setup's own answer agrees with the server, the reply gets the
  corrected answer card, the way a solved physics answer already corrects a model's
  other value (`physics/fence.py`, `correction_line`).
- **Cost:** one structured call (about 1.5–3 s, beside the reply) on those turns.
- **Next subjects:** maths needs no units and reuses the engine as is; chemistry needs
  formulas and molar masses as givens (the engine reads them from the chemistry tables).

## Not doing

- No wording lists, in any language: a miss is fixed in the engine or the prompt for every
  question at once (a constant in the table, a unit pint reads), never with a phrase.
- No number a student sees comes from the model's arithmetic when the server's disagrees.
