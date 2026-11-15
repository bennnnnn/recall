"""Where a lesson stands: the lesson the last reply taught, or the outline it asked from.

A teach-me reply is either Lesson N (title, sections, a practice quiz) or, for a
whole subject, an outline that ends asking where to start. The next turn goes
on from either one.
"""

from __future__ import annotations

from app.modules.chat.prompt_constants.teaching import _LESSON_OPENING, _LESSON_SHAPE


def lesson_continue_hint(number: int, *, after_gap: bool = False) -> str:
    """The turn after a lesson: grade the practice if answered, then the next lesson.

    ``after_gap``: the lesson was a day or more ago, so the next one opens by
    recalling it (retrieval before new material).
    """
    nxt = number + 1
    recap = (
        f"\nLESSON {number} WAS OVER A DAY AGO. Unless the latest message answers its practice "
        "question, the reply must start, before the new lesson's title, with `**Quick "
        f"recap**`: two short lines on Lesson {number}'s key idea, then one warm-up ```quiz "
        f'on it (label "Warm-up"). Only then `### Lesson {nxt}: ...` (the warm-up is not a '
        f"lesson, so the number is {nxt}) on what Lesson {number}'s preview promised."
        if after_gap
        else ""
    )
    return (
        f"A lesson is in progress. The learner has ALREADY SEEN Lesson {number}, which ended "
        "with a practice ```quiz (they can check it in the app) and a preview of the next "
        f"lesson. Do not repeat Lesson {number}. Read the latest message first:\n"
        '- An answer to the practice question: if right, start with "Correct! 🎉" and say why '
        'in one sentence; if wrong or partial, start with "Not quite", fix that one '
        "misunderstanding in 1-3 sentences with a fresh tiny example, and do not ask them to "
        f"try again. Then teach Lesson {nxt}; never ask whether to go on or try another first.\n"
        f"- 'next', 'ok', 'got it', 'continue' or similar: teach Lesson {nxt}.\n"
        "- A yes or a pick answering another offer the reply ended on (a reminder, a drawing, "
        "a harder one): do what it offered, not the next lesson.\n"
        "- Confusion ('I don't get it', 'why?', 'another example'): stay on the same idea, "
        f"explain it a different way with a new analogy and example under the same "
        f"`### Lesson {number}: ...` title, and end with a fresh ```quiz.\n"
        "- A question about the lesson: answer it first, then continue.\n"
        "- A question about an idea the practice needs ('what are isotopes?'): teach it in a "
        "few lines, then say the practice above is still theirs to try. Never work the practice "
        "out in the text, and never show its card again.\n"
        "- Accidental or unclear input: do not grade it; give the practice answer in one "
        f"sentence and teach Lesson {nxt}.\n"
        "- A request to skip, stop, change topic, get everything at once, a summary or a "
        "cheat sheet: do that instead of the next lesson.\n"
        f"Lesson {nxt} covers what the preview promised, without a greeting or an outline, "
        "in the same shape (the app's ```quiz, ```array and ```steps cards included), its "
        "practice a new question on what it taught:\n" + _LESSON_SHAPE + recap
    )


# Beside a message after a lesson that the turn's read says neither answers its card nor asks
# to go on: "yes" to "Want me to set a reminder to review this tomorrow?" got Lesson 2 (review,
# 2026-11-14), the system prompt's steps reading every short reply as "next".
LESSON_ASIDE_NOTE = (
    "This message neither answers the lesson's practice card nor asks for the next lesson: it "
    "accepts another offer your last reply made, picks among choices it offered, or asks "
    "something of its own. Do that now, and teach no new lesson unless it asks for one."
)


# Beside a message the turn's read calls an answer to a lesson's last reply: its card's
# answer, or "ok next" (``decided_turn``), as the first lesson's contract is beside a teach-me.
# With the steps only in the system prompt, "is it 35?" after Lesson 1 came back "Yes! Want to
# try one more, or should we move on to ions?" and the chat left the lesson (the owner's chat,
# 2026-11-14). ``lesson_shape`` holds the next lesson's card to it. A new question after the
# card is no answer: it gets no contract, and is answered as any question is.
LESSON_NEXT_OPENING = "The last reply taught Lesson "


def lesson_next_contract(number: int) -> str:
    """What the reply holds when the message answers Lesson ``number``'s card or goes on."""
    nxt = number + 1
    return (
        f"{LESSON_NEXT_OPENING}{number}, ending on its practice card, which the learner can "
        f"check in the app. Teach Lesson {nxt} now: the title `### Lesson {nxt}: <topic>`, its "
        "few sections (for a concept the idea, how it works and one worked example, never a "
        "section per term unless it teaches a language's words), an unnumbered `### Your "
        "turn` heading holding one new ```quiz card, and one sentence previewing the next "
        "lesson. Open with one or two sentences grading the latest message only when it gives "
        'an answer to the card ("Correct! 🎉", or "Not quite" and the fix); a message that '
        "only says to go on ('next', 'ok', 'continue') gets no grade and no word about the "
        "card or about what it said. Never ask whether to go on, and never end on a question."
    )


OUTLINE_PICK_HINT = (
    "Your previous reply outlined a subject the user wants to learn and asked where to "
    "start. Read the latest message:\n"
    "- A number, a topic, 'start', their level or their goal: teach Lesson 1 on the topic it "
    "picks (the first topic for 'start' or a beginner, the first one they don't know for a "
    "level, the one that leads to their goal) without repeating the outline, in this "
    "shape:\n" + _LESSON_OPENING + _LESSON_SHAPE + "\n"
    "- Anything else (another question, a change of mind): answer that instead."
)


def lesson_turn_hint(
    lesson: int | None, *, outline_pick: bool, after_gap: bool = False
) -> str | None:
    """How this turn goes on: the next lesson, Lesson 1 from the outline, or neither."""
    if lesson:
        return lesson_continue_hint(lesson, after_gap=after_gap)
    return OUTLINE_PICK_HINT if outline_pick else None
