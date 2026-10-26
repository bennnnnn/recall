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

import re
from collections.abc import Sequence

from app.modules.chat.prompt_constants.routing import EMOJI
from app.services.text_normalize import collapse_ws, straighten_apostrophes

_GREETING = (
    r"(?:hi|hello|hey|heya|hiya|howdy|yo|greetings|hola"
    r"|good (?:morning|afternoon|evening|night|day)|g?morning|evening|gm)"
    r"(?:,? (?:there|again|friend|buddy|pal|mate|everyone|all|y'all|you|recall))?"
)
_WELLBEING = (
    r"(?:how (?:are|r) (?:you|u|ya)(?: doing)?(?: today| this (?:morning|afternoon|evening))?"
    r"|how(?:'s| is) (?:it going|your day(?: going)?|everything|life|things)"
    r"|how (?:have you|you) been|how do you do|how are things"
    r"|(?:what's|whats|what is) up|wassup|sup"
    r"|(?:are )?you (?:ok|okay|good|alright)"
    r"|nice to meet you|long time no see|how was your (?:day|night|weekend))"
)
_SOCIAL_OPENER = re.compile(rf"{_GREETING}(?:[,!.…]* {_WELLBEING})?|{_WELLBEING}")
_OPENER_MAX_CHARS = 60
_OPENER_EDGES = " !?.,…~"


def _normalized(text: str) -> str:
    return collapse_ws(straighten_apostrophes(text)).lower()


def is_social_opener(text: str) -> bool:
    """True for a greeting or "how are you?" that asks for nothing else."""
    cleaned = collapse_ws(EMOJI.sub(" ", _normalized(text))).strip(_OPENER_EDGES)
    if not cleaned or len(cleaned) > _OPENER_MAX_CHARS:
        return False
    return _SOCIAL_OPENER.fullmatch(cleaned) is not None


def greeting_run(text: str, prior: Sequence[tuple[str, str]]) -> int:
    """How many greetings in a row ``text`` makes ("hi" after "hi" is 2); 0 when it is none."""
    if not is_social_opener(text):
        return 0
    run = 1
    for role, content in reversed(prior):
        if role != "user":
            continue
        if not is_social_opener(content):
            break
        run += 1
    return run


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


_LEAD = r"(?:(?:no|nope|nah|wait|sorry|oops|um+|uh+|hmm+)[,.!]* )+"
_CORRECTIONS = (
    # "no, I said I'm vegetarian", "wait, I meant the other one", "oops, I typed 2023"
    re.compile(
        rf"^{_LEAD}(?:i|we) (?:said|meant|mean|asked|wanted|wrote|typed|told you|mentioned"
        r"|was asking|was talking)\b"
    ),
    # "actually I meant Python 2"; "actually, can you also…" is a new request.
    re.compile(
        r"^actually,? (?:i|we) (?:said|meant|mean|asked|wanted|was asking|was talking"
        r"|didn't|did not)\b"
    ),
    re.compile(r"^correction[:,]"),
    re.compile(
        r"\b(?:that's|thats|that is|this is|it's|it is) not what (?:i|we) "
        r"(?:said|meant|asked|wanted|was asking)\b"
    ),
    re.compile(
        r"\byou (?:misunderstood|misread|misheard|got (?:it|that|me) wrong"
        r"|mixed (?:it|that|them) up)\b"
    ),
    re.compile(r"^(?:no[,.!]* )?i (?:didn't|did not|never) (?:say|mean|ask for|ask) that\b"),
    # "I already told you I'm vegetarian", "like I said, I don't eat meat"
    re.compile(r"\bi (?:already|just) (?:told you|said|mentioned)\b"),
    re.compile(
        r"^(?:like|as) i (?:said|told you|mentioned),? (?:i'm|i am|i don't|i do not|i can't"
        r"|i have|it's|it is|my)\b"
    ),
    # "that's wrong, it's 2024 not 2023": a dispute that states the fix.
    re.compile(
        r"^(?:no[,.!]* )?(?:that's|that is|this is|it's|you're|you are) (?:wrong|incorrect"
        r"|not right|not correct)(?: ?[,.!;:—-]+)? (?:it's|it is|it was|the answer is|i'm|i am"
        r"|i said|i meant|it should be|should be)\b"
    ),
)
# "I meant Python 2, not 3" states the contrast; "I said yes but I'm not sure" negates a verb.
_SAID_CONTRAST = re.compile(
    r"^(?:i|we) (?:meant|mean|said|asked for|wanted|was asking about) "
    r"(?P<right>[^.?!]{1,40}?),? not [^.?!,]{1,30}[.!]*$"
)
_NEGATING = frozenset(
    {"am", "i'm", "im", "is", "are", "was", "were", "do", "does", "did", "can", "could"}
    | {"will", "would", "should", "have", "has", "had", "but", "and", "or", "it's", "that's"}
)
# "no, I'm vegetarian" corrects; "no, I'm good" turns down an offer.
_NO_I_AM = re.compile(r"^no[,.!]* (?:i'm|i am) (?P<word>[a-z']+)")
_NOT_A_FACT = frozenset(
    {"not", "good", "fine", "ok", "okay", "alright", "all", "done", "sure", "kidding", "joking"}
    | {"just", "busy", "ready", "sorry", "afraid", "still", "so", "really", "going", "gonna"}
)
# "no, I said it was fine — thanks" closes the topic; it corrects nothing to apply.
_THANKS = re.compile(r"\b(?:thanks|thank you|thx|cheers|appreciate it)\b")
_SATISFIED = re.compile(r"\b(?:fine|ok|okay|good|great|perfect|alright|all good|no worries)\b")
_CORRECTION_MAX_CHARS = 240


def is_correction(text: str) -> bool:
    """True when the user corrects something the conversation assumed or got wrong."""
    cleaned = _normalized(text)
    if not cleaned or len(cleaned) > _CORRECTION_MAX_CHARS:
        return False
    if _THANKS.search(cleaned) and _SATISFIED.search(cleaned):
        return False
    if any(pattern.search(cleaned) for pattern in _CORRECTIONS):
        return True
    contrast = _SAID_CONTRAST.match(cleaned)
    if contrast is not None and contrast.group("right").split()[-1] not in _NEGATING:
        return True
    no_i_am = _NO_I_AM.match(cleaned)
    return no_i_am is not None and no_i_am.group("word") not in _NOT_A_FACT


CORRECTION_HINT = (
    "The user is correcting something you said or assumed earlier. Apply the correction to "
    "this answer and to the rest of the chat, and do not repeat the mistaken assumption. "
    "Acknowledge it in a few words at most, without a long apology, then give the corrected "
    "answer."
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
