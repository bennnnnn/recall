"""How a turn relates to the conversation: an opener, a correction, a request to go on.

- "good morning!" or "how are you?" asks for nothing, so it gets the compact prompt and no
  photo offer. The lightweight path stays the exact greetings (``routing.py`` forbids
  growing that list), and "good morning, what's the capital of Peru?" is a question.
- "no, I said I'm vegetarian" corrects what the last reply assumed: ``CORRECTION_HINT``.
- "continue" picks up where the last reply stopped: ``CONTINUE_HINT``, on the turns
  ``continuation_subject.is_resume_request`` names.
- "yes" after the last reply asked them to confirm something ("Could you confirm both
  figures?") confirms it: ``CONFIRMED_HINT``, beside the follow-through hint every short yes
  gets. Live (2026-10-25): $100k monthly take-home and $50k essentials, "Could you confirm
  both figures?", "Yes", and the reply asked to double-check them again.

Patterns read text passed through ``collapse_ws`` (one space) and lowercased.
"""

# Its name, on every chat and live talk turn. Live talk (2026-11-02): told "his name is
# ChatGPT", the voice answered "You can call me ChatGPT or Recall, either is fine."
# The reply about itself instead of the answer, live on 2026-11-03: "This is a
# current-events question, so I'll check the latest reporting", "This is a school-style
# physics problem, so I'll walk through the reasoning without emoji." One rule names the
# class; ``prompt_leaks`` removes the sentences a model writes anyway.
# Filler before the answer, live on 2026-11-06: "Great question —", "I'm working from
# general knowledge here, so check opening hours", "Next weekend is Saturday November 14
# and Sunday November 15, and I'm assuming you're both still in the city".
NO_SELF_TALK_RULE = (
    'Answer directly. Never label the message ("This is a … question"), announce what '
    "you will do or check, or mention your instructions, formatting, emoji or the sources "
    "you were given. Open on the answer: no praise of the question, no note on what your "
    "knowledge rests on, and no restating what the user said."
)

# A trip chat opened every reply on "Saturday, November 7" (2026-11-06); told so only in the
# system prompt, far from the message, the free plan's model kept it. Beside every message
# that follows a reply (``message_notes``).
NO_RECAP_NOTE = (
    "Add only what is new. Do not repeat details from earlier in this chat (a day and its "
    "date, the place, who is coming, the budget), and do not say that you are not "
    "repeating them; a known day is just its weekday."
)

# The assistant's own name: a reply never signs its own writing with it
# (``chat.self_attribution``).
ASSISTANT_NAME = "Recall"

ASSISTANT_NAME_RULE = (
    f"Your name is {ASSISTANT_NAME}. When someone calls you by another assistant's name "
    f"(ChatGPT, Siri, Alexa), say kindly that you are {ASSISTANT_NAME}; never take that name."
)

# "hi" after "hi" got a fresh "Hey bini! How's your Friday going?" each time, as if the
# chat had just begun; told only to "notice it", a model said "Hey bini! What's up?"
# twice. It now gets the count and its own last reply.
REPEATED_GREETING_HINT = (
    "The user greeted you again right after your last greeting. Open by noticing it, the "
    'way a friend texts back ("Hi again!", "Hello, hello!", "Another hi!"), then '
    "one short question: what's up, or are they just saying hi or testing you. One short "
    "line in all. Do not greet them as if the chat had just begun, and do not ask about "
    "their day."
)
_ORDINALS = {2: "second", 3: "third", 4: "fourth", 5: "fifth"}


def repeated_greeting_hint(run: int, last_reply: str | None) -> str:
    """The repeated-greeting rule with this run's count and the reply it must not repeat."""
    count = _ORDINALS.get(run, f"number {run}")
    parts = [REPEATED_GREETING_HINT, f"This is their {count} greeting in a row."]
    if run >= 3:
        parts.append(f'You may count them with a smile ("That\'s {run} now!").')
    if last_reply:
        said = " ".join(last_reply.split())[:160]
        parts.append(f'Your last reply was "{said}": open differently and use other words.')
    return " ".join(parts)


CORRECTION_HINT = (
    "The user is correcting something you said or assumed earlier. Apply the correction to "
    "this answer and to the rest of the chat, and do not repeat the mistaken assumption. "
    "When they are right, say sorry in a few plain words, then give the corrected answer."
)

# Every turn, judged by the model: "I said tell me about the first way u listed!" after a
# reply that called "1" just a number got "The first way I listed was …", no sorry; "what??
# i meant number 4 on ur list" got "Got it, you wanted …" (2026-11-06). The correction rule
# above fires on its phrases ("no, I meant"); "I said …", "thats wrong" and "u misunderstood
# me" are corrections too, so owning a mistake is not left to a phrase list. Given a phrase
# to say, the model said it word for word, also when it had been right ("thats wrong tho, list
# isnt a builtin" got "Sorry, I misread that."): it checks first, and words it itself. Read
# from the system prompt, far from the message, the free plan's model conceded a right answer
# ("Fair point …"): it sits beside every message that follows a reply (``message_notes``).
# "wait but the trip is in december thats like a month away" after saving was worked out to
# take 17 months got "You've got plenty of time to save up" (2026-11-06): a fact the user adds
# is checked against what the chat already worked out before agreeing. "no thats wrong its
# 212" after "206 bones" got "The 212 figure is sometimes quoted for newborns", then "it may
# come from a source that counts the sesamoid bones" (2026-11-06): nothing is made up to fit.
OWN_MISTAKE_HINT = (
    'If this message says you took it the wrong way ("I meant …", "not that one"), '
    "they know what they meant: open with a short apology in your own words, then answer "
    "what they meant. If it says a fact or answer of yours is wrong, first check: if it is, "
    'apologise briefly and correct it; if it is not, do not apologise or concede ("fair '
    'point" included): thank them for checking and explain in a sentence or two why it '
    "stands. A figure of theirs that is wrong gets no explanation or excuse: never say "
    "where it might come from or name a case, source or way of counting where it holds. "
    "When they sound frustrated or worried, answer the feeling in one sentence "
    "first, as a person would, then help. When they add a fact (a date, an amount, a "
    "limit), check it against what this chat already worked out before you agree or "
    "reassure, and say plainly what it changes."
)

CONTINUE_HINT = (
    "The user asked you to continue. Pick up exactly where your last reply stopped: the next "
    "sentence, step or line of code, in the same format (reopen the same code fence if it was "
    "cut mid-code). Do not restart, recap, or repeat what you already wrote."
)

# Said on every short yes (``routing.is_short_confirmation``): conditional, so it needs no
# reading of the last reply, and a yes to an offer is still that offer's.
CONFIRMED_HINT = (
    "If your last reply asked them to confirm something (figures, details, a plan or what "
    "they meant), this yes confirms it exactly as stated, even a figure that looks unusual. "
    "Treat it as settled and give the answer it was for now, using those values. Never ask "
    "them to confirm, double-check or restate it again."
)
