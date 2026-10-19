"""How a turn relates to the conversation: an opener, a correction, a request to go on.

- "good morning!" or "how are you?" asks for nothing, so it gets the compact prompt and no
  photo offer. The lightweight path stays the exact greetings (``routing.py`` forbids
  growing that list), and "good morning, what's the capital of Peru?" is a question.
- "no, I said I'm vegetarian" corrects what the last reply assumed: ``CORRECTION_HINT``.
- "continue" picks up where the last reply stopped: ``CONTINUE_HINT``, on the turns
  ``continuation_subject.is_resume_request`` names.

Patterns read text passed through ``collapse_ws`` (one space) and lowercased.
"""

import re

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
