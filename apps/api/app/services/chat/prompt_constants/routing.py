"""Turn classifiers used to pick prompt hints and context load."""

import re

from app.services import time_context as time_context_service
from app.services.chat.prompt_constants.locale_cues import (
    has_any_personal_locale_cue,
    has_locale_cue,
    is_bare_locale_cue,
    starts_with_locale_cue,
)
from app.services.text_normalize import collapse_ws

# Patterns assume input was passed through ``collapse_ws`` (single spaces only).
_BROAD_SELF_QUESTION = re.compile(
    r"^(?:"
    r"who am i\??"
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


_LIGHTWEIGHT_TURN = re.compile(
    r"^(?:"
    r"hi|hello|hey|hiya|yo|sup"
    r"|thanks|thank you|thx|ty"
    r"|ok|okay|k|cool|nice|great|perfect|awesome"
    r"|got it|sounds good|makes sense|understood"
    r"|yes|no|yep|nope|sure|bye|goodbye|cya|see ya"
    r"|lol|lmao|haha|hehe"
    r")(?:[!?.…, ]+(?:thanks|thank you|thx))?[!?.… ]*$",
    re.IGNORECASE,
)

# Accepting an offer — not a greeting. "no" / "thanks" / "hi" stay off this list.
_SHORT_CONFIRMATION = re.compile(
    r"^(?:"
    r"yes|yep|yeah|yup|yea|y|"
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


def prior_looks_like_offer(prior_assistant: str | None) -> bool:
    """True when the last assistant turn offered to do something."""
    if not prior_assistant:
        return False
    cleaned = collapse_ws(prior_assistant)
    if not cleaned:
        return False
    tail = cleaned[-400:].lower()
    if any(phrase in tail for phrase in _OFFER_PHRASES):
        return True
    return "?" in cleaned[-200:]


def is_lightweight_chat_turn(
    text: str,
    *,
    active_vocab_turn: bool = False,
    prior_assistant: str | None = None,
) -> bool:
    """Ultra-brief social turns (hi / thanks / ok) — short reply style only.

    Memory / status theater is gated separately by ``needs_rich_context`` so we
    do not grow this allowlist for every casual phrase ("how is ur day", etc.).
    A short yes/go after an offer is follow-through, not a greeting.
    """
    if active_vocab_turn:
        return False
    cleaned = collapse_ws(text)
    if not cleaned:
        return True
    looks_light = (len(cleaned) <= 2 and cleaned.isalpha()) or (
        len(cleaned) <= 24 and bool(_LIGHTWEIGHT_TURN.match(cleaned))
    )
    if not looks_light:
        return False
    if is_short_confirmation(cleaned) and prior_looks_like_offer(prior_assistant):
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
    r"earlier (?:you|we)|from (?:my|our) (?:last|previous)"
    r")\b|"
    r"\b(?:about me|tell me about (?:me|myself))\b|"
    r"\bmy\s+(?:"
    r"name|email|preference|preferences|diet|routine|schedule|"
    r"calendar|wife|husband|kids?|dog|cat|job|work|boss|team|"
    r"project|projects|todo|todos|list|lists|reminder|reminders|"
    r"allerg(?:y|ies)|favorite|usual|memory|memories|"
    r"vocab(?:ulary)?|words?|learning"
    r")\b"
    r")",
    re.IGNORECASE,
)

# Progress / "what did I learn" — not dictionary lookups like "another word for".
_LEARNING_PROGRESS_CUE = re.compile(
    r"(?:"
    r"\bvocab(?:ulary)?\b|"
    r"\b(?:what|which) words?\b|"
    r"\bwords? (?:did|have) i\b|"
    r"\b(?:learn(?:ed|ing)?|studied|practiced|mastered) today\b|"
    r"\btoday'?s (?:words?|vocab(?:ulary)?|lesson|quiz)\b|"
    r"\bmy (?:vocab(?:ulary)?|words|learning)\b|"
    r"\blearning (?:class|progress|path|topic)s?\b|"
    r"\bhow many words\b|"
    r"\bwords? (?:i|have i) (?:learn|learned|studied|mastered)\b"
    r")",
    re.IGNORECASE,
)


def is_learning_progress_question(text: str) -> bool:
    """True when the user is asking about their Recall Learning words/progress."""
    cleaned = collapse_ws(text)
    if not cleaned:
        return False
    return bool(_LEARNING_PROGRESS_CUE.search(cleaned))


def needs_rich_context(
    text: str,
    *,
    active_vocab_turn: bool = False,
    day_planning: bool = False,
    day_reflection: bool = False,
) -> bool:
    """True when this turn should load personal context (memory/todos/projects).

    Systemic default: casual chat is slim. Opt in via personal/retrieval cues,
    day-planning, or vocab turns — not via an ever-growing greeting list.
    Callers may OR in calendar/email/todo classifiers from ``turn_prep.mode``.
    """
    if active_vocab_turn or day_planning or day_reflection:
        return True
    if is_lightweight_chat_turn(text, active_vocab_turn=active_vocab_turn):
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
    if is_learning_progress_question(cleaned):
        return True
    if has_any_personal_locale_cue(cleaned):
        return True
    return bool(_PERSONAL_CONTEXT_CUE.search(cleaned))


# Advice / recommendation — load memory only (not Calendar/Gmail/Learning).
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

CONFIRM_FOLLOW_THROUGH_HINT = (
    "The user accepted your last offer with a short yes/go/sure. "
    "Carry out that offer now. Do not treat this as a greeting or a one-word ack."
)

_EMAIL_WRITING = re.compile(
    r"\b(?:"
    r"send (?:me )?(?:an? )?email|"
    r"email (?:to|my)|"
    r"write (?:me )?(?:an? )?email|"
    r"draft (?:an? )?email|"
    r"compose (?:an? )?email"
    r")\b",
    re.IGNORECASE,
)

_MESSAGE_WRITING = re.compile(
    r"\b(?:"
    r"send (?:me )?(?:a )?(?:text|message)|"
    r"(?:write|draft|compose) (?:me )?(?:an? )?(?:text|message|sms|reply)|"
    r"(?:text|message|reply) (?:to|for|my)|"
    r"reply (?:to|saying|that says)"
    r")\b",
    re.IGNORECASE,
)

_SOCIAL_WRITING = re.compile(
    r"\b(?:write|draft|compose|create|rewrite)\s+"
    r"(?:me\s+)?(?:(?:an?|the|my|one)\s+)?"
    r"(?:(?:(?:very\s+)?(?:short|long|brief|concise|detailed|formal|informal|"
    r"professional|personal|promotional|funny|casual)|"
    r"\d+(?:[- ](?:word|character)))\s+){0,2}"
    r"(?:linkedin (?:post|note)|instagram caption|social(?: media)? post|"
    r"twitter post|x post|tweet|caption|dating (?:app )?bio)\b",
    re.IGNORECASE,
)

_DIRECT_REQUEST_INTRO = (
    r"(?:(?:(?:can|could|would|will) you|please|por favor|s'il vous plaît|"
    r"bitte|per favore|lütfen|maaloo)[,\s]+)*"
    r"(?:(?:help me(?: to)?|i (?:want|need)(?: you)? to)[,\s]+)?"
)

_TRANSLATION_WRITING = re.compile(
    r"^(?:" + _DIRECT_REQUEST_INTRO + r"(?:"
    r"(?:translate|traduc(?:e|ir)|traduis|traduire|[uü]bersetze|traduci|"
    r"traduz(?:a|ir)?|cevir|çevir|hiiki)\b|"
    r"(?:переведи|ተርጉም)\b|"
    r"translation\s*:))",
    re.IGNORECASE,
)

_UNSPACED_TRANSLATION_COMMAND = re.compile(
    r"^(?:"
    r"(?:请|請)?(?:翻译|翻譯)(?:"
    r"(?:一下)?(?:这句话|這句話|这个句子|這個句子|这段文字|這段文字|"
    r"这篇文章|這篇文章|这封邮件|這封郵件|以下内容|以下內容|下面内容|下面內容|"
    r"上述内容|上述內容)(?=$|[.!?\u3002\uFF01\uFF1F]|"
    r"(?:成|为|為)(?:英文|英语|英語|中文|汉语|漢語|日文|日语|日語|韩文|韓文|"
    r"韩语|韓語|法文|法语|法語|德文|德语|德語|西班牙文|西班牙语|西班牙語|"
    r"俄文|俄语|俄語|阿拉伯文|阿拉伯语|阿拉伯語)"
    r"(?=$|[.!?\u3002\uFF01\uFF1F]|[:\uFF1A\"'“\u2018「『])|"
    r"[:\uFF1A\"'“\u2018「『])|"
    r"一下(?=$|[.!?\u3002\uFF01\uFF1F])|"
    r"(?:成|为|為)(?:英文|英语|英語|中文|汉语|漢語|日文|日语|日語|韩文|韓文|"
    r"韩语|韓語|法文|法语|法語|德文|德语|德語|西班牙文|西班牙语|西班牙語|"
    r"俄文|俄语|俄語|阿拉伯文|阿拉伯语|阿拉伯語)"
    r"(?=$|[.!?\u3002\uFF01\uFF1F]|[:\uFF1A\"'“\u2018「『])|"
    r"[:\uFF1A\"'“\u2018「『]|\s+(?=[\"'“\u2018「『A-Za-z0-9])|(?=[A-Za-z0-9]))|"
    r"(?:翻訳してください|訳してください)(?=$|[\s.!?:\u3002\uFF01\uFF1F\uFF1A])|"
    r"(?:翻訳して|訳して)\s+ください(?=$|[\s.!?:\u3002\uFF01\uFF1F\uFF1A])|"
    r"(?:翻訳して|訳して)(?=$|[.!?:\u3002\uFF01\uFF1F\uFF1A])|"
    r"(?:번역)\s*(?:좀\s*)?"
    r"(?:해\s*(?:주세요|줘)|하세요|(?:을\s*)?부탁(?:드립니다|드려요|해요|해\s*(?:주세요|줘))?)"
    r"(?=$|[\s.!?:\u3002\uFF01\uFF1F\uFF1A])|"
    r"(?:번역해)(?=$|[.!?:\u3002\uFF01\uFF1F\uFF1A])"
    r")",
    re.IGNORECASE,
)

_PROSE_WRITING = re.compile(
    r"\b(?:write|draft|compose|rewrite|create)(?: me)?\s+"
    r"(?:(?:an?|one|the)\s+)?"
    r"(?:(?:(?:very\s+)?(?:short|long|brief|concise|detailed|formal|informal|"
    r"professional|personal|persuasive|creative|academic)|"
    r"\d+(?:[- ](?:word|paragraph|page))?)\s+){0,3}"
    r"(?:paragraph|essay|article|story|poem|letter|statement|announcement|"
    r"description|script|outline)\b",
    re.IGNORECASE,
)

_EDIT_WRITING = re.compile(
    r"(?:^" + _DIRECT_REQUEST_INTRO + r"(?:"
    r"(?:correct(?: this)?|proofread|rewrite (?:this|it)|"
    r"fix (?:this )?(?:sentence|grammar)|"
    r"grammar check|check (?:this )?(?:sentence|grammar))\b|"
    r"\bis this (?:sentence )?(?:correct|right|grammatical)\b))",
    re.IGNORECASE,
)

_WRITING_SEQUENCE_PREFIX = re.compile(r"^(?:then|now|also|next)[,\s]+", re.IGNORECASE)

_DIRECT_REQUEST_PREFIX = re.compile(r"^" + _DIRECT_REQUEST_INTRO, re.IGNORECASE)

_WRITING_HOWTO = re.compile(
    r"^(?:how (?:do|can|should|would) i|how to)\b",
    re.IGNORECASE,
)


def _normalize_writing_followup(text: str) -> str:
    return _WRITING_SEQUENCE_PREFIX.sub("", text.strip(), count=1)


def _starts_direct_writing_request(text: str) -> bool:
    candidate = _normalize_writing_followup(text)
    if (
        _TRANSLATION_WRITING.search(candidate)
        or _UNSPACED_TRANSLATION_COMMAND.search(candidate)
        or _EDIT_WRITING.search(candidate)
        or starts_with_locale_cue(candidate, "writing")
    ):
        return True
    prefix = _DIRECT_REQUEST_PREFIX.match(candidate)
    prefix_end = prefix.end() if prefix else 0
    return any(
        (match := pattern.search(candidate)) is not None and match.start() <= prefix_end
        for pattern in (_EMAIL_WRITING, _MESSAGE_WRITING, _SOCIAL_WRITING, _PROSE_WRITING)
    )


def _has_later_closing_single_quote(text: str, index: int, quote: str) -> bool:
    """Check for a later quote terminator, ignoring contraction apostrophes."""
    for later in range(index + 1, len(text)):
        if text[later] != quote:
            continue
        if 0 < later < len(text) - 1:
            if text[later - 1].isalnum() and text[later + 1].isalnum():
                continue
        before = text[later - 1] if later > 0 else ""
        after = text[later + 1] if later + 1 < len(text) else ""
        if not after or before in ".!?" or after in ".!?;:,":
            return True
    return False


def _is_strong_single_quote_closer(text: str, index: int) -> bool:
    before = text[index - 1] if index > 0 else ""
    after = text[index + 1] if index + 1 < len(text) else ""
    return not after or before in ".!?" or after in ".!?;:,"


def _next_sentence_tail(text: str) -> str | None:
    """Return text after the next plausible sentence boundary."""
    quote_closers = {
        '"': '"',
        "'": "'",
        "“": "”",
        "\u2018": "\u2019",
        "「": "」",
        "『": "』",
    }
    closing_quote: str | None = None
    require_strong_single_quote_closer = False
    delimiter_stack: list[str] = []
    boundary_end: int | None = None
    for index, char in enumerate(text):
        if closing_quote is not None:
            if char in ".!?" and index + 1 < len(text):
                quote_end = index + 1
                if text[quote_end] == closing_quote:
                    quote_end += 1
                    if not delimiter_stack and (
                        quote_end == len(text) or text[quote_end].isspace()
                    ):
                        tail = text[quote_end:].strip()
                        if tail and _starts_direct_writing_request(tail):
                            return tail
            if char == closing_quote:
                if char in {"'", "\u2019"} and 0 < index < len(text) - 1:
                    if text[index - 1].isalnum() and text[index + 1].isalnum():
                        continue
                    if require_strong_single_quote_closer and not _is_strong_single_quote_closer(
                        text, index
                    ):
                        continue
                closing_quote = None
                require_strong_single_quote_closer = False
            continue
        if char in quote_closers:
            # Apostrophes following a word are contractions or possessives,
            # never the opening delimiter for a new single-quoted span.
            if char == "'" and index > 0 and text[index - 1].isalnum():
                continue
            closing_quote = quote_closers[char]
            require_strong_single_quote_closer = char in {"'", "\u2018"} and (
                _has_later_closing_single_quote(text, index, closing_quote)
            )
            continue
        if char in "([{":
            delimiter_stack.append({"(": ")", "[": "]", "{": "}"}[char])
            continue
        if delimiter_stack and char == delimiter_stack[-1]:
            delimiter_stack.pop()
            continue
        if delimiter_stack:
            continue
        if char not in ".!?":
            continue
        next_index = index + 1
        while next_index < len(text) and text[next_index] in ".!?":
            next_index += 1
        if next_index < len(text) and not text[next_index].isspace():
            continue
        if char == ".":
            prefix = text[:next_index].lower()
            abbreviation = re.search(
                r"(?:\b(?:mr|mrs|ms|dr|prof|sr|jr|st|vs|etc)\.|(?:\b[a-z]\.){2,})$",
                prefix,
            )
            if abbreviation:
                is_etc_sequence = prefix.endswith("etc.") and _WRITING_SEQUENCE_PREFIX.match(
                    text[next_index:].lstrip()
                )
                if not is_etc_sequence:
                    continue
        boundary_end = next_index
        break
    if boundary_end is None:
        return None
    tail = text[boundary_end:].strip()
    return tail or None


def _after_initial_writing_howto(text: str) -> str | None:
    """Drop a leading how-to sentence, but retain later text."""
    if not _WRITING_HOWTO.search(text):
        return text
    return _next_sentence_tail(text)


def _find_direct_writing_followup(text: str) -> str | None:
    """Find the first sentence after a how-to that starts a writing command."""
    candidate: str | None = text
    while candidate:
        if _starts_direct_writing_request(candidate):
            return _normalize_writing_followup(candidate)
        candidate = _next_sentence_tail(candidate)
    return None


def writing_request_kind(text: str) -> str | None:
    """Return the writing shape the response contract should preserve."""
    cleaned = collapse_ws(text)
    if not cleaned:
        return None
    # Questions about how to produce or manage a writing artifact are advice,
    # not requests for Recall to draft it. A later sentence can still contain
    # an explicit deliverable request and must keep its output contract.
    had_initial_howto = bool(_WRITING_HOWTO.search(cleaned))
    writing_candidate = _after_initial_writing_howto(cleaned)
    if writing_candidate is None:
        return None
    cleaned = writing_candidate
    if had_initial_howto:
        direct_followup = _find_direct_writing_followup(cleaned)
        if direct_followup is None:
            return None
        cleaned = direct_followup
    # Translation leads before quoted-source classifiers: `Translate "write
    # me an email" into Spanish` is a translation, not a request to draft an
    # email. An actual email deliverable such as "write an email in Spanish"
    # has no translation verb and still routes to email below.
    if _TRANSLATION_WRITING.search(cleaned) or _UNSPACED_TRANSLATION_COMMAND.search(cleaned):
        return "translation"
    if _EDIT_WRITING.search(cleaned):
        return "edit"
    shape_matches: list[tuple[int, int, str]] = []
    for priority, (kind, pattern) in enumerate(
        (
            ("email", _EMAIL_WRITING),
            ("message", _MESSAGE_WRITING),
            ("social", _SOCIAL_WRITING),
            ("prose", _PROSE_WRITING),
        )
    ):
        if match := pattern.search(cleaned):
            shape_matches.append((match.start(), priority, kind))
    if starts_with_locale_cue(cleaned, "writing"):
        shape_matches.append((0, 0, "email"))
    if shape_matches:
        return min(shape_matches)[2]
    return None


def is_writing_deliverable_request(text: str) -> bool:
    """True for drafts, translations, prose writing, and writing edits."""
    return writing_request_kind(text) is not None


def is_email_or_message_request(text: str) -> bool:
    """True only when recipient/profile context can improve a direct draft."""
    return writing_request_kind(text) in {"email", "message"}


_WRITING_PURPOSE_MARKERS = (
    " about ",
    " regarding ",
    " saying ",
    " that says ",
    " to say ",
    " letting ",
    " because ",
    " asking ",
    " subject",
    " i will ",
    " i'll ",
    " i'm ",
    " i am ",
    " pto",
    " running late",
    " be late",
    " follow-up",
    " follow up",
    " apology",
    " thank",
    " requesting ",
    " request for ",
    " inviting ",
    " invite ",
    " announcing ",
    " announce ",
    " comparing ",
    " covering ",
    " explaining ",
    " promoting ",
    " celebrating ",
    " sharing ",
    " birthday",
    " congratulat",
    " vacation",
    " time off",
    " meeting",
    " reschedul",
    " cancell",
    " checking in",
    " check-in",
    " update",
    " news",
)


def is_underspecified_writing_request(text: str) -> bool:
    """True for a bare sendable draft ask, not a supplied writing task."""
    kind = writing_request_kind(text)
    if kind not in {"email", "message", "social"}:
        return False
    cleaned = f" {collapse_ws(text).lower()} "
    if '"' in cleaned or "\u201c" in cleaned:
        return False
    # Localized writing cues are stored as complete bare requests. Any text
    # beyond the cue is user-supplied purpose/content and should be drafted.
    if has_locale_cue(text, "writing"):
        return is_bare_locale_cue(text, "writing")
    return not any(marker in cleaned for marker in _WRITING_PURPOSE_MARKERS)
