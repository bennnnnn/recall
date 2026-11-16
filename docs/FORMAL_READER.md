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

Corrected grading (a unit in the question's own script, "35 м/с", is read by its number),
second run:

| Set | Questions | App's solver reads | Today, Free (Qwen 3.7 Flash) | Formal, Free | Today, paid (smart-chat) | Formal, paid |
|---|---|---|---|---|---|---|
| English holdout | 89 | 89 | 89 (100%) | 89 (100%) | 89 (100%) | 89 (100%) |
| English reworded | 45 | 35 | 44 (98%) | 45 (100%) | 45 (100%) | 45 (100%) |
| Spanish | 30 | 0 | 27 (90%) | 30 (100%) | 30 (100%) | 30 (100%) |
| French | 30 | 0 | 26 (87%) | 29 (97%) | 30 (100%) | 30 (100%) |
| Amharic | 30 | 0 | 24 (80%) | 28 (93%) | 29 (97%) | 29 (97%) |
| Russian | 30 | 0 | 26 (87%) | 30 (100%) | 30 (100%) | 30 (100%) |
| **Translated, all** | **120** | **0** | **103 (86%)** | **117 (98%)** | **119 (99%)** | **119 (99%)** |

The setup was written by smart-chat. The first run (before the grading fix) gave the same
picture for Free: 101 (84%) today and 118 (98%) with the server's answer.

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

## Disagreements: who was right (owner's condition, 2026-11-16)

On the turns the app's solver did not answer (English rewordings and the four translations),
the server's answer (setup by smart-chat, its own answer agreeing) against the reply model's,
over two runs:

| Reply model | Same answer | Rounding only (both right) | Differ | Server right | Reply right |
|---|---|---|---|---|---|
| Qwen 3.7 Flash (Free) | 198 | 5 | 36 | **36** | 0 |
| smart-chat (paid) | 235 | 4 | 0 | – | – |

The 36 are the model's own slips: a projectile's range (28.6, 31.7, 32.4 or 54.7 m for
31.04 m), a time of flight (2.56 s for 2.638 s), a braking time (4.5 s for 4 s), a tension
(6,900 N for 6,786 N), a slide of 229.5 m for 22.94 m. A reply in Cyrillic units ("35 м/с")
is the same answer: the first run's grading counted 14 such replies as different, and they
are counted as the same here.

So the server is right in every disagreement, and finalize overwrites (below).

**Arabic and Hindi** (the kept experiment's questions, 40 each, `formal_corpus/translated/`,
one run): Free's replies go from 72% to 85% right in Arabic and 60% to 85% in Hindi, paid's
from 92% to 95% and 88% to 98%. Where the setup's own answer agreed with the server's, they
differed from the reply 20 times (15 Free, 5 paid), and the server was right all 20. The one
question the reply got right and the server wrong (a lens, in Hindi) was a setup whose own
answer disagreed with the server's: that is why finalize requires them to agree.

## In the app (physics, `formal_reader_enabled`, on)

- **When:** a physics turn (the turn's read says physics) that no solver answered and the
  server did not write itself (`ctx.verified_subject` and `ctx.instant_reply` both None).
  A turn a solver answered never asks.
- **Beside the reply:** the setup read (`physics_setup` lane, smart-chat) and the solve
  start with the reply (`chat/formal_turn.py`); the reply streams as before.
- **At finalize** (`formal_answer` pass), waiting at most `formal_wait_seconds` (2 s), and
  only for an answer whose setup's own answer agreed with the server's:
  - the reply's final value is the server's, or a rounding of it: the reply stands;
  - another value: its Answer becomes the server's card;
  - a value the readers cannot find (an Answer heading in another language): the server's
    card under the reply, both shown.

  Either way a line in the reply's language (9 app languages) says where the value comes
  from ("Worked out from the values in the question: 31.07 m."), and the card is marked
  `verified: false`: the server did the arithmetic, the reading is the model's.
- **Wait and cost** (130 turns, smart-chat): median 0.99 s, p90 1.5 s, max 3.6 s for the
  setup read; $0.18 per 1,000 turns. It runs beside a streamed reply that usually takes
  longer, so finalize rarely waits; the wait it does take is logged (`formal answer: reply
  …, waited … s`).
- **The adapter:** `SubjectAdapter.formal` (`SubjectFormal`, guarded), so chat reaches it
  through the registry; maths and chemistry answer None until they have a reader.

## One model reader

This replaces the MODEL_READER experiment (`docs/MODEL_READER.md`): a model read into one
of the catalog's laws, run only in shadow. Its code is removed (`modules/model_reader/`,
`physics/model_read.py`, `chemistry/model_read.py`, the chat shadow and its trace fields and
settings, `law_binding/model_read.py` but for `excluded`, now in `law_binding/words.py`).

What stays:
- its 600 translated questions (Amharic, Arabic, Spanish, French, Hindi; 40 each of maths,
  physics and chemistry a language), now `formal_corpus/translated/`: `formal_eval.py`
  measures physics on them (the `-reader` sets) and maths and chemistry will be measured on
  them next; `test_formal_corpus.py` holds every id to a corpus entry;
- the catalog readers, the fast path: a question they read is solved with no model call,
  and the formal reader is never asked. They get no new wording rules;
- maths' own typed read (`math/tools/llm_extract.py`), the next to go, when maths has a
  formal reader (after the graph-drawing work merges).

## Not doing

- No wording lists, in any language: a miss is fixed in the engine or the prompt for every
  question at once (a constant in the table, a unit pint reads), never with a phrase.
- No number a student sees comes from the model's arithmetic when the server's disagrees.
