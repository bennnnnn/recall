"""Turn classifiers used to pick prompt hints and context load."""

import re

from app.modules.chat.prompt_constants.locale_cues import (
    has_any_personal_locale_cue,
    has_locale_cue,
)
from app.modules.chat.prompt_constants.teaching import lesson_step
from app.modules.chat.prompt_constants.writing_kind import is_email_or_message_request
from app.services import time_context as time_context_service
from app.services.text_normalize import collapse_ws

# Patterns assume input was passed through ``collapse_ws`` (single spaces only).
_BROAD_SELF_QUESTION = re.compile(
    r"^(?:"
    r"who am i\??"
    r"|what am i\??"
    r"|tell me about me\??"
    r"|what do you know about me\??"
    r"|describe me\??"
    r"|what(?:'re| are) i like\??"
    r")[.!?]*$",
    re.IGNORECASE,
)


def is_broad_self_question(text: str) -> bool:
    """Broad identity questions — name only, no personal context dump."""
    cleaned = collapse_ws(text)
    if not cleaned or time_context_service.is_location_question(cleaned):
        return False
    return bool(_BROAD_SELF_QUESTION.match(cleaned))


# Social turns stand alone; replies answer whatever the assistant just said.
_SOCIAL_WORDS = (
    r"hi|hello|hey|hiya|yo|sup"
    r"|thanks|thank you|thx|ty"
    r"|bye|goodbye|cya|see ya"
    r"|lol|lmao|haha|hehe"
)
_REPLY_WORDS = (
    r"ok|okay|k|cool|nice|great|perfect|awesome"
    r"|got it|sounds good|makes sense|understood"
    r"|yes|no|go|yep|nope|sure"
)
_THANKS_TAIL = r"(?:[!?.…, ]+(?:thanks|thank you|thx))?[!?.… ]*$"
_LIGHTWEIGHT_TURN = re.compile(
    rf"^(?:{_SOCIAL_WORDS}|{_REPLY_WORDS}){_THANKS_TAIL}",
    re.IGNORECASE,
)
_SHORT_REPLY = re.compile(rf"^(?:{_REPLY_WORDS}){_THANKS_TAIL}", re.IGNORECASE)

# Accepting an offer — not a greeting. "no" / "thanks" / "hi" stay off this list.
_SHORT_CONFIRMATION = re.compile(
    r"^(?:"
    r"yes|yep|yeah|yup|yea|"
    r"sure(?: thing)?|"
    r"ok(?:ay)?|k|"
    r"go(?: ahead)?|"
    r"do it|please|proceed|"
    r"yes please|ok go"
    r")[!?.… ]*$",
    re.IGNORECASE,
)

# Phrase scan on the prior assistant tail (no regex over the body).
_OFFER_PHRASES = (
    "want me to",
    "shall i",
    "should i",
    "i can check",
    "i can look",
    "i can search",
    "i can draft",
    "i can write",
    "i can make",
    "i can draw",
    "i can show",
    "i can send",
    "i can find",
    "i can help",
    "i can do that",
    "i could",
    "happy to",
    "let me know",
    "if you'd like",
    "if you would like",
    "if you want",
)


def is_short_confirmation(text: str) -> bool:
    """True for yes / go / sure — not hi, thanks, or no."""
    cleaned = collapse_ws(text)
    if not cleaned:
        return False
    return bool(_SHORT_CONFIRMATION.match(cleaned))


def is_short_reply(text: str) -> bool:
    """True for yes / no / got it / understood — an answer to the last assistant turn.

    Unlike hi / thanks / bye, its meaning depends on what the assistant just
    said, so the turn needs the recent window ("Understood?" → "no").
    """
    cleaned = collapse_ws(text)
    if not cleaned:
        return False
    if is_short_confirmation(cleaned):
        return True
    return len(cleaned) <= 24 and bool(_SHORT_REPLY.match(cleaned))


def prior_looks_like_offer(prior_assistant: str | None) -> bool:
    """True when the last assistant turn offered to do something or asked a question."""
    if not prior_assistant:
        return False
    cleaned = collapse_ws(prior_assistant)
    if not cleaned:
        return False
    tail = cleaned[-400:].lower()
    if any(phrase in tail for phrase in _OFFER_PHRASES):
        return True
    if "?" in cleaned[-200:]:
        return True
    # A lesson step ends on a check question, even when its options trail it.
    return lesson_step(prior_assistant) is not None


# Emoji, flags and their joiners. "hi 👋" is the same greeting as "hi".
# Skin tones (U+1F3FB-1F3FF) sit inside U+1F300-1FAFF. Escapes, not literal
# characters, so the pattern reads the same to the regex engine and to scanners.
_EMOJI = re.compile(
    r"[\U0001f1e6-\U0001f1ff\U0001f300-\U0001faff\u2600-\u27bf\u2b00-\u2bff\ufe0f\u200d]+"
)


def is_lightweight_chat_turn(
    text: str,
    *,
    prior_assistant: str | None = None,
) -> bool:
    """Ultra-brief social turns (hi / thanks / ok) — short reply style only.

    Memory / status theater is gated separately by ``needs_rich_context`` so we
    do not grow this allowlist for every casual phrase ("how is ur day", etc.).
    A short yes / no / got it after a question or an offer is an answer
    (follow-through, or "no" to "Understood?"), not a greeting.
    """
    cleaned = collapse_ws(text)
    if not cleaned:
        return True
    # "👍" alone is an acknowledgement; "hi 👋" is "hi".
    cleaned = collapse_ws(_EMOJI.sub(" ", cleaned))
    if not cleaned:
        return True
    # Only real greetings (hi, ok, go). A short fragment stays with the
    # thread so the solver can keep the open problem.
    looks_light = len(cleaned) <= 24 and bool(_LIGHTWEIGHT_TURN.match(cleaned))
    if not looks_light:
        return False
    if is_short_reply(cleaned) and prior_looks_like_offer(prior_assistant):
        return False
    return True


# Opt-in cues for loading memory / todos / projects.
# Default is fast (no personal context) — do not grow a greeting allowlist.
_PERSONAL_CONTEXT_CUE = re.compile(
    r"(?:"
    r"\b(?:"
    r"remember|recall|you (?:know|remember)|what do you know|"
    r"don'?t forget|keep in mind|"
    r"we (?:talked|discussed|decided)|last time|"
    r"earlier (?:you|we)|from (?:my|our) (?:last|previous)|"
    r"what was that thing|that thing we (?:talked|discussed|mentioned)"
    r")\b|"
    r"\b(?:about me|tell me about (?:me|myself))\b|"
    r"\bmy\s+(?:"
    r"name|email|preference|preferences|diet|routine|schedule|"
    r"calendar|wife|husband|kids?|dog|cat|job|work|boss|team|"
    r"project|projects|todo|todos|list|lists|reminder|reminders|"
    r"allerg(?:y|ies)|favorite|usual|memory|memories"
    r")\b"
    r")",
    re.IGNORECASE,
)

# Continuity asks that should still search earlier chats on a slim turn.
# Phrase scan (not a regex) so a longer question cannot blow up matching.
_EARLIER_CONVERSATION_PHRASES = (
    "did we",
    "didn't we",
    "didnt we",
    "we pick",
    "we chose",
    "we picked",
    "we decided",
    "we said",
    "we talked",
    "we were talking",
    "last year",
    "last month",
    "last week",
    "last time",
    "what did i say",
    "what did i tell",
    "what did i choose",
    "what did we talk",
    "what did we decide",
    "didn't i mention",
    "didnt i mention",
    "didn't i tell",
    "didnt i tell",
    "didn't i say",
    "didnt i say",
    "did i mention",
    "what were we talking",
    "what were we discussing",
    "which one did i",
    "which one did we",
    "where we left off",
    "pick up from where",
    "continue where we",
    "you know the thing",
    "the thing i told you",
    "what was my idea",
    "what was that idea",
    "i told you about",
    "as i said",
    "like i said",
    "talking about yesterday",
)


def _phrase_at_word_boundary(text: str, phrase: str) -> bool:
    """True when ``phrase`` occurs with a non-letter on each side."""
    start = 0
    while True:
        found = text.find(phrase, start)
        if found < 0:
            return False
        before = found == 0 or not text[found - 1].isalnum()
        end = found + len(phrase)
        after = end == len(text) or not text[end].isalnum()
        if before and after:
            return True
        start = found + 1


def recalls_earlier_conversation(text: str) -> bool:
    """True when the user is asking about something said in an earlier chat."""
    cleaned = collapse_ws(text).lower()
    if not cleaned:
        return False
    return any(
        _phrase_at_word_boundary(cleaned, phrase) for phrase in _EARLIER_CONVERSATION_PHRASES
    )


def needs_rich_context(
    text: str,
    *,
    day_planning: bool = False,
    day_reflection: bool = False,
) -> bool:
    """True when this turn should load personal context (memory/todos).

    Systemic default: casual chat is slim. Opt in via personal/retrieval cues
    or day-planning — not via an ever-growing greeting list.
    Callers may OR in calendar/email/todo classifiers from ``turn_prep.mode``.
    """
    if day_planning or day_reflection:
        return True
    if is_lightweight_chat_turn(text):
        return False
    cleaned = collapse_ws(text)
    if not cleaned:
        return False
    if is_broad_self_question(cleaned):
        return True
    # Direct drafts can benefit from names/relationships in memory. Generic
    # prose, proofreading, and translation should stay on the snappy slim
    # path rather than loading the user's private context without a reason.
    if is_email_or_message_request(cleaned):
        return True
    if has_any_personal_locale_cue(cleaned):
        return True
    return bool(_PERSONAL_CONTEXT_CUE.search(cleaned))


# Advice / recommendation — load memory only (not Calendar/Gmail).
# Require a life-domain word so "what should I return" / "recommend a library"
# stay slim. Day-planning is classified separately and supersedes this path.
# Ordinary phrasing ("I need dinner", "plan a workout") must match too — not
# only "recommend" / "what should I".
_ADVICE_INTENT = re.compile(
    r"\b("
    r"recommend(?:ation)?s?|suggest(?:ion)?s?|"
    r"any ideas|ideas for|help me (?:choose|pick|decide)|"
    r"what should i|where should i|what(?:'s| is) for|"
    r"(?:can|could|should|may) i (?:eat|drink|wear|try|do|have)|"
    r"what to (?:eat|cook|wear|watch|get|buy|order|drink)|"
    r"pick (?:a |an )|"
    r"i(?:'m| am) (?:hungry|starving)"
    r")\b",
    re.IGNORECASE,
)
_ADVICE_DOMAIN = re.compile(
    r"\b("
    r"drink|coffee|tea|"
    r"eat|eating|cook|cooking|dinner|lunch|breakfast|brunch|"
    r"food|restaurant|recipe|meal|hungry|starving|snack|"
    r"wear|outfit|clothes|clothing|"
    r"movie|film|show|series|watch|"
    r"listen|playlist|song|music|"
    r"workout|exercise|gym|"
    r"gift|present"
    r")\b",
    re.IGNORECASE,
)
_ADVICE_STANDALONE = re.compile(
    r"\b("
    r"what(?:'s| is) for (?:dinner|lunch|breakfast|brunch)|"
    r"(?:dinner|lunch|breakfast) ideas|"
    r"i(?:'m| am) (?:hungry|starving)"
    r")\b",
    re.IGNORECASE,
)
_ADVICE_PROGRAMMING = re.compile(
    r"("
    r"\brecommend (?:a |an )?(?:\w+ )?library\b|"
    r"\bwhat should i return\b|"
    r"\b(function|typescript|javascript|codebase|npm |pip install|"
    r"api endpoint|react native)\b"
    r")",
    re.IGNORECASE,
)

# Need/plan path. Omit show/watch so "I need to show you this" stays slim.
# Do not use a bare "for me" cue — it pairs with any later/earlier domain word
# ("summarize this movie review for me").
_ADVICE_NEED_PLAN = re.compile(
    r"\b("
    r"i need|i want|"
    r"need (?:a |an |some )|"
    r"want (?:a |an )|"
    r"plan (?:a |an |my )|"
    r"help me plan|"
    r"(?:make|create|build|design) (?:me |my )|"
    r"quick dinner|easy dinner|"
    r"dinner tonight|lunch tonight|breakfast tonight"
    r")\b",
    re.IGNORECASE,
)
_ADVICE_NEED_DOMAIN = re.compile(
    r"\b("
    r"eat|eating|cook|cooking|dinner|lunch|breakfast|brunch|"
    r"food|restaurant|recipe|meal|hungry|starving|snack|"
    r"wear|outfit|clothes|clothing|"
    r"movie|film|series|"
    r"playlist|song|music|"
    r"workout|exercise|gym|"
    r"gift|present"
    r")\b",
    re.IGNORECASE,
)
# Domain must sit in the same short clause as the need/plan cue.
_ADVICE_NEED_LOOKBEHIND = 12
_ADVICE_NEED_LOOKAHEAD = 48
_ADVICE_NEED_NEGATION_TAILS = (
    "don't ",
    "dont ",
    "do not ",
    "doesn't ",
    "doesnt ",
    "never ",
    "won't ",
    "wont ",
    "can't ",
    "cant ",
    "cannot ",
)


def _advice_need_plan_with_domain(cleaned: str) -> bool:
    """True when a need/plan cue and a life-domain word share a short span.

    Independent whole-message searches treated “summarize this movie review
    for me” and “I don't need a workout” as advice.
    """
    plan = _ADVICE_NEED_PLAN.search(cleaned)
    if plan is None:
        return False
    prefix = cleaned[: plan.start()].lower()
    if any(prefix.endswith(tail) for tail in _ADVICE_NEED_NEGATION_TAILS):
        return False
    start = max(0, plan.start() - _ADVICE_NEED_LOOKBEHIND)
    end = min(len(cleaned), plan.end() + _ADVICE_NEED_LOOKAHEAD)
    return bool(_ADVICE_NEED_DOMAIN.search(cleaned[start:end]))


_CAREER_PERSONAL = re.compile(
    r"\b(?:my career|my job|my work|career advice|job interview|interviews?|"
    r"resume|résumé|\bcv\b|promotion|workplace)\b",
    re.IGNORECASE,
)


# "What is my education" / "my second langauge" — a stored profile field, including
# the common misspelling. Not a general "who am I" summary.
_PROFILE_FACT_QUESTION = re.compile(
    r"(?:"
    r"\b(?:my|i am|i'm|im)\b(?:\s+\w+){0,6}\s+"
    r"(?:education|school|university|college|degree|grades?|languages?|langauges?)\b"
    r"|"
    r"\b(?:education|school|university|college|degree|grades?|languages?|langauges?)\b"
    r".{0,24}\b(?:mine|my|i|me)\b"
    r"|"
    r"\bwhere am i from\b"
    r"|"
    r"\bwhere do i live\b"
    r"|"
    r"\bwhat languages? do i\b"
    r")",
    re.IGNORECASE,
)
_PROFILE_PUSHBACK = re.compile(
    r"\b(?:(?:u|you) don'?t know|(?:u|you) should know)\b",
    re.IGNORECASE,
)
_TELL_ME = re.compile(r"^(?:(?:u|you) )?tell me[.!?]*$", re.IGNORECASE)
_LANGUAGE_SLOT = re.compile(
    r"^(?:the |my )?(first|second|native|other)(?: one| language| langauge)?[.!?]*$",
    re.IGNORECASE,
)
_LANGUAGE_TOPIC = re.compile(r"\b(?:language|langauge)s?\b", re.IGNORECASE)


_PROFILE_QUESTION_LEAD = re.compile(
    r"^(?:what|what'?s|which|where|do you (?:know|remember)|tell me|guess)\b",
    re.IGNORECASE,
)
# "My second language" is a profile ask; "write an email to the school saying
# my son is sick" or "rewrite my bio: I'm a teacher…" is a writing request.
_PROFILE_PHRASE_WORDS = 8
_PROFILE_QUESTION_WORDS = 14


def is_profile_fact_question(text: str) -> bool:
    """True when they ask for a detail their profile may already hold."""
    cleaned = collapse_ws(text)
    if not cleaned:
        return False
    words = len(cleaned.split())
    asks = _PROFILE_QUESTION_LEAD.match(cleaned) or cleaned.endswith("?")
    if words > _PROFILE_QUESTION_WORDS or (words > _PROFILE_PHRASE_WORDS and not asks):
        return False
    from app.modules.chat.prompt_constants.writing_kind import writing_request_kind

    if writing_request_kind(cleaned) is not None:
        return False
    return bool(_PROFILE_FACT_QUESTION.search(cleaned))


def is_profile_recall_pushback(text: str) -> bool:
    """True when they say you should already know, after a profile question."""
    cleaned = collapse_ws(text)
    if not cleaned or len(cleaned) > 48:
        return False
    return bool(_PROFILE_PUSHBACK.search(cleaned) or _TELL_ME.match(cleaned))


def _language_slot_followup(content: str, prior_user_texts: list[str]) -> str | None:
    """'Second' after a language question asks for that language, not a new topic."""
    match = _LANGUAGE_SLOT.match(collapse_ws(content))
    if match is None:
        return None
    slot = match.group(1).lower()
    if slot == "native":
        slot = "first"
    for text in reversed(prior_user_texts):
        if is_profile_recall_pushback(text):
            continue
        if not _LANGUAGE_TOPIC.search(text):
            break
        if slot == "other":
            slot = "first" if re.search(r"\bsecond\b", text, re.IGNORECASE) else "second"
        return f"what is my {slot} language"
    return None


def profile_question_to_answer(content: str, prior_user_texts: list[str]) -> str | None:
    """The profile question this turn is asking, including a later 'you tell me'."""
    if is_profile_fact_question(content):
        return content
    slotted = _language_slot_followup(content, prior_user_texts)
    if slotted:
        return slotted
    if not is_profile_recall_pushback(content):
        return None
    for text in reversed(prior_user_texts):
        if is_profile_fact_question(text):
            return text
        if is_profile_recall_pushback(text):
            continue
        break
    return None


def is_career_personal_question(text: str) -> bool:
    """True when the ask is about their work, so a known job should shape the answer."""
    cleaned = collapse_ws(text)
    if not cleaned:
        return False
    return bool(_CAREER_PERSONAL.search(cleaned))


def is_personal_advice_question(text: str) -> bool:
    """True for recommendation / 'what should I eat' / 'plan a workout' turns.

    Does not imply full rich context. Callers load memory only.
    """
    cleaned = collapse_ws(text)
    if not cleaned:
        return False
    if _ADVICE_PROGRAMMING.search(cleaned):
        return False
    if has_locale_cue(cleaned, "advice"):
        return True
    if _ADVICE_STANDALONE.search(cleaned):
        return True
    if _advice_need_plan_with_domain(cleaned):
        return True
    return bool(_ADVICE_INTENT.search(cleaned) and _ADVICE_DOMAIN.search(cleaned))


LIGHTWEIGHT_REPLY_HINT = (
    "This is a short social turn (greeting / ack). Reply in one brief sentence. "
    "Do not dig into memory, lists, calendar, or projects unless the user asked."
)

PERSONAL_DISCLOSURE_HINT = (
    "The user is sharing personal context or a goal, not asking for a task. Your entire reply "
    "must be one or two natural sentences with no heading, list, steps, or action plan. "
    "Acknowledge the update and connect relevant known context only when useful. Do not browse, "
    "draft outreach, recommend next steps, or turn the statement into unsolicited advice. You "
    "may ask one brief follow-up question only if it would genuinely help. When the update "
    "contrasts a current situation with a future goal, explicitly preserve both in the "
    "acknowledgement (currently at X; considering Y) instead of mentioning only the goal."
)

_PERSONAL_DISCLOSURE_PREFIXES = (
    "i'm ",
    "i\u2019m ",
    "i am ",
    "i work ",
    "i currently ",
    "i have ",
    "i prefer ",
    "i like ",
    "i love ",
    "i dislike ",
    "i use ",
    "i live ",
    "i study ",
    "i learn ",
    "i got ",
    "i started ",
    "i moved ",
    "i finished ",
    "i decided ",
    "my ",
    "remember that ",
    "remember this ",
    "please remember ",
    "don't forget ",
    "do not forget ",
)
_PERSONAL_REQUEST_MARKERS = (
    " can you ",
    " could you ",
    " would you ",
    " will you ",
    " should i ",
    " help me ",
    " tell me ",
    " give me ",
    " find ",
    " search ",
    " look up ",
    " write ",
    " draft ",
    " compose ",
    " email ",
    " message ",
    " text ",
    " reply ",
    " rewrite ",
    " create ",
    " make ",
    " build ",
    " show ",
    " explain ",
    " plan ",
    " compare ",
    " recommend ",
    " advise ",
    " advice ",
    " what ",
    " how ",
    " why ",
    " when ",
    " where ",
    " which ",
    " who ",
    " latest ",
    " news ",
    " need ",
    " needs ",
    " looking for ",
)

_COLLECTIVE_DISCLOSURE = re.compile(
    r"^(?:"
    r"we\s+(?:work|live|study|learn|prefer|like|love|dislike|use|moved|started|finished|decided)\b|"
    r"we\s+are\s+(?:based|employed|living|working|studying|learning|moving)\b|"
    r"we(?:'|\u2019)re\s+(?:based|employed|living|working|studying|learning|moving)\b"
    r")",
    re.IGNORECASE,
)


def is_personal_disclosure_turn(text: str) -> bool:
    """True for a first-person fact/goal with no actual request attached."""
    cleaned = collapse_ws(text).casefold()
    if not cleaned or "?" in cleaned:
        return False
    if not cleaned.startswith(_PERSONAL_DISCLOSURE_PREFIXES) and not _COLLECTIVE_DISCLOSURE.match(
        cleaned
    ):
        return False
    request_text = re.sub(r"[^\w']+", " ", cleaned)
    padded = f" {request_text} "
    return not any(marker in padded for marker in _PERSONAL_REQUEST_MARKERS)


NEW_PROBLEM_HINT = (
    "The user asked for another problem like the previous one. Make up a NEW problem "
    "of the same kind, with a different scenario and different numbers (harder or "
    "easier if they said so), state it, then solve it. Do not repeat, restate, or "
    "re-answer the previous problem. This request outranks any rule against adding "
    "examples."
)

CONFIRM_FOLLOW_THROUGH_HINT = (
    "The user accepted your last offer with a short yes/go/sure. "
    "Carry out that offer now. Do not treat this as a greeting or a one-word ack."
)
