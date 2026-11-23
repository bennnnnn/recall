"""Which writing deliverable a turn is asking for.

Email, message, social, prose, translation, and edit. Turn routing asks this
only to decide whether a draft should load profile context.
"""

import re

from app.core.readings import kept_per_turn
from app.modules.turn_reading.writing_locales import DraftTails, locale_draft_kind, opening_at
from app.services.text_match import after_spaces
from app.services.text_normalize import collapse_ws

# The words that name what an email or message is for may stand between the
# verb and the noun: "write a resignation email", "a follow-up email".
_DRAFT_PURPOSE_WORDS = r"(?:[a-z]+(?:-[a-z]+)? ){0,2}"
# Who it goes to may stand between "send" and the draft: "send my boss an email".
_SEND_TO = r"(?:(?:me|him|her|them|us) |(?:my |our )?[a-z'-]+ (?=an? ))?"

_EMAIL_WRITING = re.compile(
    r"\b(?:"
    r"send " + _SEND_TO + r"(?:an? )?email|"
    r"email (?:to|my)|"
    r"(?:write|draft|compose) (?:me )?(?:an? |the )?" + _DRAFT_PURPOSE_WORDS + r"e-?mail|"
    r"(?:reply|respond|answer)(?: back)?(?: to)? (?:this|that|the|her|his|their|my|an?) e-?mail"
    r")\b",
    re.IGNORECASE,
)

_MESSAGE_WRITING = re.compile(
    r"\b(?:"
    r"send " + _SEND_TO + r"(?:a )?" + _DRAFT_PURPOSE_WORDS + r"(?:text|message)|"
    r"(?:write|draft|compose) (?:me )?(?:an? )?"
    + _DRAFT_PURPOSE_WORDS
    + r"(?:text|message|sms|reply)|"
    r"(?:text|message|reply) (?:to|for|my)|"
    r"reply (?:to|saying|that says)|"
    r"(?:answer|respond to)(?: back)? (?:this|that|the|her|his|their|my) "
    r"(?:message|text|dm|sms|whatsapp)|"
    r"respond to (?:this|that|it|her|him|them)\b"
    r")\b",
    re.IGNORECASE,
)

# "Tell my landlord the heater is broken", "let my team know we moved to 3pm":
# Recall cannot pass it on, so it is a message to send. "Should I tell my boss
# I'm pregnant?" asks for advice: the line has to start with the request.
_TELL_RECIPIENT = re.compile(
    r"^(?:(?:(?:can|could|would|will) you|please)[,\s]+)*"
    r"(?:tell my [a-z'-]+(?: [a-z'-]+)? (?:that \w|(?:the|my|our|his|her|their|i|i'm|i'll|"
    r"i've|we|we're|we'll|it|it's|he|she|they|there)\b)|"
    r"let my [a-z'-]+(?: [a-z'-]+)? know\b)",
    re.IGNORECASE,
)

# "How should I reply to 'we need to talk'?" asks for the reply itself when it
# quotes or pastes the message; "how do I reply to emails faster" is advice.
_REPLY_HOWTO = re.compile(
    r"^how (?:should|do|can|would) i (?:reply|respond|answer)(?: back)?(?: to)?\b"
    r"(?=.*(?:[\"\u201c\u2018]|\s'|:\s*\S))",
    re.IGNORECASE,
)

_SOCIAL_WRITING = re.compile(
    r"\b(?:write|draft|compose|create|rewrite|make)\s+"
    r"(?:me\s+)?(?:(?:an?|the|my|one)\s+)?"
    r"(?:(?:(?:very\s+)?(?:short|long|brief|concise|detailed|formal|informal|"
    r"professional|personal|promotional|funny|casual)|"
    r"\d+(?:[- ](?:word|character)))\s+){0,2}"
    r"(?:linkedin (?:(?:update)\s+)?(?:post|note)|"
    r"facebook (?:(?:update)\s+)?(?:post|status)|fb post|"
    r"instagram (?:caption|post|story)|tiktok (?:caption|post)|threads post|"
    r"social(?: media)? post|"
    r"twitter post|x post|tweet|caption|dating (?:app )?bio|"
    # "write a post for facebook", "a status on fb"
    r"(?:post|status|update|caption) (?:for|on) "
    r"(?:facebook|fb|instagram|insta|ig|linkedin|twitter|x|threads|tiktok|social media))\b",
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
    r"(?:paragraph|essay|article|story|poem|cover\s+letter|letter|statement|"
    r"announcement|description|script|outline|r[eé]sum[eé]s?|cv|biograph(?:y|ies)|"
    r"bio)\b|"
    # The user's own record: "write my resume", "make a CV for a nurse", "polish my cover letter".
    r"\b(?:write|draft|compose|rewrite|create|make|build|prepare|redo|polish|improve)"
    r"(?: me| up)?\s+(?:(?:an?|one|the|my)\s+)?(?:(?:new|short|professional|simple|basic|"
    r"good|better|strong)\s+)?(?:cover\s+letter|r[eé]sum[eé]|cv)\b",
    re.IGNORECASE,
)

_EDIT_WRITING = re.compile(
    r"(?:^" + _DIRECT_REQUEST_INTRO + r"(?:"
    r"(?:correct(?: this)?|proofread|rewrite (?:this|it)|"
    r"fix (?:the |my |this )?(?:sentence|grammar|spelling|typos?)|"
    r"correct (?:the |my )?(?:grammar|spelling)|"
    r"grammar check|check (?:the |my |this )?(?:sentence|grammar|spelling))\b|"
    r"\bis this (?:sentence )?(?:correct|right|grammatical)\b))",
    re.IGNORECASE,
)

# A change of tone or length to text the user pasted: "make this more polite:
# ...". The result is wording they will paste and send, so it is a copy block,
# not a corrected sentence with notes.
_TONES = (
    r"(?:professional|polite|formal|informal|casual|friendly|friendlier|nice|nicer|kind|"
    r"kinder|warm|warmer|soft|softer|firm|firmer|gentle|gentler|respectful|confident|"
    r"assertive|apologetic|grateful|positive|persuasive|diplomatic|natural|human|clear|"
    r"clearer|simple|simpler|concise|short|shorter|long|longer|better|smooth|smoother|"
    r"funny|funnier|fun|cute|romantic|sweet|sweeter|serious|enthusiastic|excited|happy|"
    r"cheerful|empathetic|sincere)"
)
_REWRITE_WRITING = re.compile(
    r"^" + _DIRECT_REQUEST_INTRO + r"(?:"
    r"(?:make|rewrite|rephrase|reword|turn|change|edit|write) "
    r"(?P<object>this|it|that|my (?:message|text|email|post|reply|caption)|"
    r"the (?:message|text|email|post|reply|caption))"
    r"(?: to)?(?: (?:sound|look|read|be))? (?:(?:a )?(?:bit|little|lot|much|way) )?"
    r"(?:more |less |too )?" + _TONES + r"|"
    r"(?:rephrase|reword|paraphrase|polish|shorten|simplify|soften|tone down) "
    r"(?P<short_object>this|it|that|my|the)\b"
    r")",
    re.IGNORECASE,
)
# A message or email pasted after a colon, on its own lines, or in quotes is
# what a reply answers or a rewrite changes.
PASTED_TEXT = re.compile(r":\s*\S+(?:\s+\S+){2,}|\n\s*\S|[\"\u201c]")


def _is_rewrite(cleaned: str, written: str) -> bool:
    """A tone or length change to text in this message, or to a named message.

    "Make it shorter" with nothing pasted refers to the previous reply, which
    the follow-up contract handles; it is not new text to paste and send.
    ``written`` keeps the line breaks a pasted message starts on.
    """
    match = _REWRITE_WRITING.search(cleaned)
    if match is None:
        return False
    target = (match.group("object") or match.group("short_object") or "").lower()
    if target in {"this", "it", "that", "the", "my"}:
        return PASTED_TEXT.search(written) is not None
    return True


# "Then", "now": a later sentence that goes on with the request.
_WRITING_SEQUENCE = re.compile(r"(?:then|now|also|next)[,\s]+", re.IGNORECASE)

_WRITING_HOWTO = re.compile(
    r"^(?:how (?:do|can|should|would) i|how to)\b",
    re.IGNORECASE,
)

# The checks a sentence after a how-to opens on, read from its start in the message.
_TRANSLATION_AT = opening_at(_TRANSLATION_WRITING)
_UNSPACED_TRANSLATION_AT = opening_at(_UNSPACED_TRANSLATION_COMMAND)
_EDIT_AT = opening_at(_EDIT_WRITING)
_DIRECT_REQUEST_AT = re.compile(_DIRECT_REQUEST_INTRO, re.IGNORECASE)
_DRAFT_PATTERNS = (_EMAIL_WRITING, _MESSAGE_WRITING, _SOCIAL_WRITING, _PROSE_WRITING)
# Where a word starts or ends: each of ``_DRAFT_PATTERNS`` opens on one (``\b``).
_WORD_EDGE = re.compile(r"\b")

# "Dr.", "etc.", "e.g.": a period that ends no sentence. Its longest form ("prof." and the
# letter before it) is the last six characters; a run of initials ("u.s.a.") reads two.
_ABBREVIATION = re.compile(r"(?:\b(?:mr|mrs|ms|dr|prof|sr|jr|st|vs|etc)\.|(?:\b[a-z]\.){2,})$")
_ABBREVIATION_REACH = 8

_QUOTE_CLOSERS = {
    '"': '"',
    "'": "'",
    "“": "”",
    "\u2018": "\u2019",
    "「": "」",
    "『": "』",
}


class _Rest:
    """A message read sentence by sentence after a how-to (CX-1). ``text`` is a
    ``collapse_ws`` result, and each sentence is read from where it starts in it.

    Asked of every sentence's rest, "does it start a draft?" and "does this quote close
    later?" each read on to the message's end: a 32k message of short sentences took 3.7 s
    (``writing_request_kind`` may run on the event loop). Here each is read once for the
    whole message and kept, and no rest is copied out of it.
    """

    def __init__(self, text: str) -> None:
        self.text = text
        self.drafts = DraftTails(text)
        self._last_closer: dict[str, int] = {}

    def closes_later(self, index: int, quote: str) -> bool:
        """Whether a closer of ``quote`` comes after ``index``. Whether a quote closes
        depends only on its neighbours, so the message's last closer answers for every
        index."""
        if quote not in self._last_closer:
            self._last_closer[quote] = _last_closing_single_quote(self.text, quote)
        return self._last_closer[quote] > index


def _request_start(text: str, start: int) -> int:
    """Where the request in the sentence at ``start`` opens: after "then", "now", ..."""
    sequence = _WRITING_SEQUENCE.match(text, start)
    return sequence.end() if sequence else start


def _starts_direct_writing_request(rest: _Rest, start: int) -> bool:
    text = rest.text
    at = _request_start(text, start)
    if (
        _TRANSLATION_AT.match(text, at)
        or _UNSPACED_TRANSLATION_AT.match(text, at)
        or _EDIT_AT.match(text, at)
        or rest.drafts.kind(at) is not None
    ):
        return True
    intro = _DIRECT_REQUEST_AT.match(text, at)
    intro_end = intro.end() if intro else at
    # A draft that opens at or before the request's opening words end: tried only there,
    # never searched for through the rest of the message.
    edges = [edge.start() for edge in _WORD_EDGE.finditer(text, at, intro_end + 1)]
    return any(
        pattern.match(text, edge) is not None
        for pattern in _DRAFT_PATTERNS
        for edge in edges
        if edge <= intro_end
    )


def _last_closing_single_quote(text: str, quote: str) -> int:
    """Where the last of ``quote`` that closes a single-quoted span is, or -1.

    An apostrophe between two letters (a contraction) never closes one, and a closer is
    the end of the text or a strong one (``_is_strong_single_quote_closer``)."""
    later = text.rfind(quote)
    while later > 0:
        contraction = (
            later < len(text) - 1 and text[later - 1].isalnum() and text[later + 1].isalnum()
        )
        if not contraction and _is_strong_single_quote_closer(text, later):
            return later
        later = text.rfind(quote, 0, later)
    return -1


def _is_strong_single_quote_closer(text: str, index: int) -> bool:
    before = text[index - 1] if index > 0 else ""
    after = text[index + 1] if index + 1 < len(text) else ""
    return not after or before in ".!?" or after in ".!?;:,"


def _ends_no_sentence(text: str, start: int, end: int) -> bool:
    """The period before ``end`` closes an abbreviation ("Dr.", "e.g."), not the sentence
    that began at ``start``, unless it is "etc." and the next sentence goes on ("then").

    Only the last characters are read and lowercased: lowercasing a letter never shortens
    the text, and changes no neighbour the pattern reads (only Σ's form depends on them,
    and both forms are letters)."""
    before = text[max(start, end - _ABBREVIATION_REACH) : end].lower()
    if not _ABBREVIATION.search(before):
        return False
    return not (before.endswith("etc.") and _WRITING_SEQUENCE.match(text, after_spaces(text, end)))


def _next_sentence_start(rest: _Rest, start: int) -> int | None:
    """Where the text after the sentence that begins at ``start`` begins, or None."""
    text = rest.text
    closing_quote: str | None = None
    require_strong_single_quote_closer = False
    delimiter_stack: list[str] = []
    boundary_end: int | None = None
    for index in range(start, len(text)):
        char = text[index]
        if closing_quote is not None:
            if char in ".!?" and index + 1 < len(text):
                quote_end = index + 1
                if text[quote_end] == closing_quote:
                    quote_end += 1
                    if not delimiter_stack and (
                        quote_end == len(text) or text[quote_end].isspace()
                    ):
                        tail = after_spaces(text, quote_end)
                        if tail < len(text) and _starts_direct_writing_request(rest, tail):
                            return tail
            if char == closing_quote:
                if char in {"'", "\u2019"} and start < index < len(text) - 1:
                    if text[index - 1].isalnum() and text[index + 1].isalnum():
                        continue
                    if require_strong_single_quote_closer and not _is_strong_single_quote_closer(
                        text, index
                    ):
                        continue
                closing_quote = None
                require_strong_single_quote_closer = False
            continue
        if char in _QUOTE_CLOSERS:
            # Apostrophes following a word are contractions or possessives,
            # never the opening delimiter for a new single-quoted span.
            if char == "'" and index > start and text[index - 1].isalnum():
                continue
            closing_quote = _QUOTE_CLOSERS[char]
            require_strong_single_quote_closer = char in {"'", "\u2018"} and (
                rest.closes_later(index, closing_quote)
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
        if char == "." and _ends_no_sentence(text, start, next_index):
            continue
        boundary_end = next_index
        break
    if boundary_end is None:
        return None
    tail = after_spaces(text, boundary_end)
    return tail if tail < len(text) else None


def _find_direct_writing_followup(rest: _Rest, start: int) -> str | None:
    """Find the first sentence from ``start`` on that starts a writing command."""
    at: int | None = start
    while at is not None:
        if _starts_direct_writing_request(rest, at):
            return rest.text[_request_start(rest.text, at) :]
        at = _next_sentence_start(rest, at)
    return None


@kept_per_turn
def writing_request_kind(text: str) -> str | None:
    """Return the writing shape the response contract should preserve.

    Kept for the turn by its text: a dozen callers ask it of the turn's message, 12 reads of
    a 32 KB paste a turn (PERF-02, 2026-11-13). The text itself is the key, line breaks and
    all: a pasted message is read from where its lines start (``_is_rewrite``)."""
    cleaned = collapse_ws(text)
    if not cleaned:
        return None
    if _REPLY_HOWTO.search(cleaned):
        return "message"
    # Questions about how to produce or manage a writing artifact are advice,
    # not requests for Recall to draft it. A later sentence can still contain
    # an explicit deliverable request and must keep its output contract.
    if _WRITING_HOWTO.search(cleaned):
        rest = _Rest(cleaned)
        after_howto = _next_sentence_start(rest, 0)
        direct_followup = (
            None if after_howto is None else _find_direct_writing_followup(rest, after_howto)
        )
        if direct_followup is None:
            return None
        cleaned = direct_followup
    # Translation leads before quoted-source classifiers: `Translate "write
    # me an email" into Spanish` is a translation, not a request to draft an
    # email. An actual email deliverable such as "write an email in Spanish"
    # has no translation verb and still routes to email below.
    if _TRANSLATION_WRITING.search(cleaned) or _UNSPACED_TRANSLATION_COMMAND.search(cleaned):
        return "translation"
    # "Rewrite this to sound friendlier: ..." is a new tone, not a proofread.
    if _is_rewrite(cleaned, text):
        return "rewrite"
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
    if _TELL_RECIPIENT.match(cleaned):
        shape_matches.append((0, 1, "message"))
    # "Escribe un correo a mi jefe…", "patronuma bir e-posta yaz".
    locale_kind = locale_draft_kind(cleaned)
    if locale_kind is not None:
        shape_matches.append((0, -1, locale_kind))
    if shape_matches:
        return min(shape_matches)[2]
    return None


def is_writing_deliverable_request(text: str) -> bool:
    """True for drafts, translations, prose writing, and writing edits."""
    return writing_request_kind(text) is not None


def is_email_or_message_request(text: str) -> bool:
    """True only when recipient/profile context can improve a direct draft."""
    return writing_request_kind(text) in {"email", "message"}
