"""Email and copy-paste deliverable hints."""

import re

from app.modules.chat.prompt_constants.format import is_comparison_question
from app.modules.chat.prompt_constants.routing import is_lightweight_chat_turn
from app.modules.chat.prompt_constants.writing_kind import (
    _DIRECT_REQUEST_INTRO,
    is_writing_deliverable_request,
    writing_request_kind,
)
from app.services.text_normalize import collapse_ws

# Relative / subordinating leads that are not a complete question.
_FRAGMENT_LEAD = re.compile(
    r"^(?:whoever|whatever|whichever|however|because|although|though|"
    r"whereas|unless|until)\b",
    re.IGNORECASE,
)
WRITING_LINE_HINT = (
    "The user sent a sentence fragment or asked for a writing edit. Complete "
    "their sentence — you are finishing the line, not answering as an assistant. "
    "Do not say you are an AI, that you do not make decisions, or ask what they "
    "meant. Lead with the completed sentence, then at most 3 short bullets "
    "(what's wrong, why, one alternative). Do not invent a topic essay, table, "
    "or bit about the words."
)

NON_DRAFT_TURN_HINT = (
    "This turn is not an explicit writing request. Reply conversationally in normal Markdown; "
    "do not create an email, message, SMS, social-post, or copy fence. A personal update, goal, "
    "employer/company mention, or career-change statement is context to understand and respond "
    "to—not an implicit request to draft outreach. Only draft when the user explicitly asks you "
    "to write, draft, compose, email, message, text, reply, or rewrite something."
)

EMAIL_DRAFT_HINT = (
    "Email and message drafting (purpose is already in the ask):\n"
    "When the user wants an email, text, or message written and they said what it "
    "is about — including 'write an email saying I will be late' / 'email my boss "
    "about PTO':\n"
    "1. Put a complete, send-ready draft inside ```email (or ```message for SMS) "
    "now. Match the requested tone; otherwise infer a natural tone from the relationship "
    "and purpose. Do not interview for tone. Include Subject: when you can infer one. "
    "Use To: only when the address was explicitly supplied or is in memory/profile — "
    "never invent addresses.\n"
    "2. Resolve relationships from memory (my wife, my husband, mom, boss, etc.) to real "
    "names and emails when stored. Greet them by name in the body even if To: is omitted. "
    "If the name or address is unknown, omit To: and greet with Hi, — do not invent "
    "bracketed slots for name or email.\n"
    "3. Return one draft by default (except as in 4). If the user explicitly asks for "
    "multiple versions, return exactly that many clearly labelled draft fences. Otherwise, "
    "after the fence, add at most ONE short line offering to adjust tone or length — not a "
    "questionnaire.\n"
    "4. A reply answers the message or email the user pasted or quoted. When that message "
    "asks them something (an invitation, a favour, a meeting, a yes/no question) and they did "
    "not say their answer, do not ask them and do not answer for them: give two short drafts, "
    "**Yes:** and **No:**, each a bold label on its own line followed by its own fence.\n"
    "5. Recall cannot send email or SMS. Never say you sent it, emailed them, or texted "
    "them — only that you drafted it for them to send."
)

EMAIL_ASK_PURPOSE_HINT = (
    "The user asked for an email, message, or social post but did not say what it is about "
    "(bare 'write me an email' / 'escribeme un correo' / 'message to my friend' / "
    "'write a LinkedIn post'). "
    "Ask exactly ONE short question: what should it say? A generic relationship such as "
    "friend, boss, or mom is enough recipient context. Do not ask separately for a name, "
    "tone, phone number, or email address. Do not create a draft fence yet."
)

SOCIAL_DRAFT_HINT = (
    "Social/caption writing:\n"
    "If the user supplied a topic, write the finished post now—do not interview for tone. "
    "Use ```twitter for X/Twitter, ```linkedin for LinkedIn, ```facebook for Facebook, "
    "```instagram for Instagram, and ```social for other platforms or generic captions. "
    "Never tag the fence as a programming language. "
    "Put only publish-ready wording inside the fence. "
    "Do not invent engagement statistics, hashtags, or emoji unless requested or natural "
    "for the user's own style. Return one version by default; if they explicitly request "
    "multiple versions, return exactly that many clearly labelled fences."
)

TRANSLATION_FORMAT_HINT = (
    "Translation:\n"
    "Return the translation directly, preserving meaning, tone, paragraph boundaries, "
    "names, punctuation, and intentional line breaks. Do not add a heading, quotation "
    "marks, explanation, transliteration, or Original/Translation labels unless requested. "
    "Use plain Markdown by default. If the user explicitly says the translation is a "
    "message/post they will send, put only the translated send-ready text in the matching "
    "```message or ```social fence. If source text or target language is genuinely missing, "
    "ask one short question. A side-by-side table is only for an explicit side-by-side ask."
)

REWRITE_HINT = (
    "Rewriting the user's own text for tone or length:\n"
    "Return the rewritten version, ready to paste, in one fence: ```email for an email, "
    "```message for a text or chat message, otherwise ```copy. Keep their meaning and every "
    "name, date, number, and commitment. No explanation before it and at most one short line "
    "after it. Several versions only when the user asked for them."
)


def draft_revision_hint(fence: str) -> str:
    """The contract for a follow-up that changes the draft in the previous reply."""
    return (
        f"This turn changes the draft in your previous reply (```{fence}). Apply only the "
        "requested change (tone, length, wording, a point added or removed, or the language) "
        "and keep every name, date, number, and commitment the user did not change. Return the "
        f"whole revised draft in one ```{fence} fence, not a list of edits or a diff. No "
        "explanation before it and at most one short line after it. Several versions only "
        "when the user asked for them."
    )


# The send-ready fences a reply drafts, as the mobile fence registry names them.
_DRAFT_FENCE = re.compile(
    r"^```(email|message|sms|reply|copy|twitter|tweet|x|linkedin|facebook|fb|instagram|"
    r"insta|ig|tiktok|threads|caption|social)[ \t]*$",
    re.IGNORECASE | re.MULTILINE,
)
# A short follow-up that changes a draft: "make it more polite", "shorter",
# "add that I'll be back tomorrow", "another version", "translate it to Spanish".
_DRAFT_REVISION = re.compile(
    r"^" + _DIRECT_REQUEST_INTRO + r"(?:"
    r"(?:make|keep|get) (?:it|this|that)\b|"
    r"(?:(?:a )?(?:bit|little|lot|much|way) )?(?:more|less) [a-z]+|"
    r"(?:shorter|longer|simpler|clearer|friendlier|warmer|softer|nicer|politer|"
    r"formal|informal|casual|polite|professional)\b|"
    r"(?:add|remove|drop|include|mention|change|replace|say|use|put|swap|cut|delete|"
    r"take out|leave out|tone (?:it |this )?(?:down|up)|sign|end|start|open)\b|"
    r"(?:rewrite|redo|rephrase|reword|shorten|lengthen|polish|soften|simplify|"
    r"try again|again)\b|"
    r"(?:another|a different|a new|different|other) (?:version|one|draft|option|way)|"
    r"(?:give|write|show|send) (?:me )?(?:another|a different|a new|one more|more|other) "
    r"(?:versions?|ones?|drafts?|options?)|"
    r"translate (?:it|this|that)\b|"
    r"(?:in|into) [a-z]+$|"
    r"with(?:out)? (?:any |the |an? )?(?:emojis?|hashtags?|subject|greeting|signature)"
    r")",
    re.IGNORECASE,
)
_REVISION_MAX_WORDS = 30


def draft_revision_fence(
    text: str | None, prior_messages: list[tuple[str, str]] | None
) -> str | None:
    """The fence of the previous reply's draft when this line only changes that draft.

    A new draft request ("write a message to my mom") is its own deliverable.
    """
    if not text or not prior_messages:
        return None
    cleaned = collapse_ws(text)
    if not cleaned or len(cleaned.split()) > _REVISION_MAX_WORDS:
        return None
    if writing_request_kind(cleaned) in {"email", "message", "social", "prose"}:
        return None
    if _DRAFT_REVISION.search(cleaned) is None:
        return None
    previous = next(
        (content for role, content in reversed(prior_messages) if role == "assistant"), None
    )
    if not previous:
        return None
    fences = _DRAFT_FENCE.findall(previous)
    return fences[-1].lower() if fences else None


_PERSONAL_RECORD = re.compile(
    r"\b(?:cover\s+letters?|r[eé]sum[eé]s?|cvs?|biograph(?:y|ies)|bios?)\b",
    re.IGNORECASE,
)

PERSONAL_RECORD_HINT = (
    "Cover letter, résumé, or short biography:\n"
    "Use only facts the user stated in this conversation or that are already in "
    "memory or their profile. Do not invent a name, a city they live in, an "
    "employer, a job title, a skill, a tool, or a year of experience. A city "
    "they asked about is not where they live, and a job they asked you to find "
    "is not a job they have held. If their name or their experience is missing, "
    "ask one short question and do not draft the biography yet."
)


def personal_record_hint(text: str) -> str | None:
    """A cover letter or résumé, or None for other prose."""
    if _PERSONAL_RECORD.search(text) is None:
        return None
    return PERSONAL_RECORD_HINT


PROSE_WRITING_HINT = (
    "Requested prose form overrides the general response style:\n"
    "- 'One paragraph' means exactly one uninterrupted paragraph: no heading or bullets.\n"
    "- Essay/article/story/letter means normal paragraphs; use headings only if requested "
    "or if distinct sections are necessary. Do not turn prose into a tips list.\n"
    "- Poem, script, address, and line-by-line text must preserve intended line breaks. "
    "Use Markdown hard breaks (two trailing spaces) or blank lines so mobile rendering "
    "does not join separate lines.\n"
    "- Outline markers (numbers, letters, or roman numerals) must match what the user asked for.\n"
    "Do not use a copy fence unless the user explicitly wants paste-and-send wording."
)

COPY_DELIVERABLE_HINT = (
    "When the user asked for an email, SMS, reply, caption, or social post they will "
    "copy and send — not an article, paragraph, essay, letter, or translation unless "
    "they said they will paste-send it — put ONLY the final send-ready wording inside "
    "a fenced code block: ```email, ```message, ```sms, ```twitter, ```linkedin, "
    "```facebook, ```instagram, or "
    "```copy. "
    "Use one such fence by default. Use multiple only when the user explicitly requested "
    "multiple alternatives, and return exactly the requested count. "
    "Copy blocks must be ready to paste and send as-is: complete sentences, real names "
    "and subjects from context or memory. Never invent [placeholders] or TBD, but preserve "
    "placeholders when the user explicitly asks for a reusable template. "
    "If they already said what to write, include the fence with a full draft now. "
    "If they only asked to write an email/message with no purpose, ask one question "
    "first — do not invent a generic letter. "
    "For email/message drafts, omit To: and greet Hi, when the name or address is unknown. "
    "Never claim you sent the message — drafts are for the user to send. "
    "Never use ```copy or ```text for explanations, notes, advice, comparisons, "
    "articles, paragraphs, essays, or math/numeric final answers — those belong in "
    "plain markdown with `$...$` "
    "(pipe tables for X vs Y; bullets otherwise). Do not emit ```answer / "
    "```graph / ```geometry. "
    "For emails include To:/Subject: lines when known; omit To if unknown rather than "
    "guessing an address."
)


def is_bare_writing_line(text: str) -> bool:
    """True for a pasted fragment or an explicit proofread ask — not a question."""
    cleaned = collapse_ws(text)
    if not cleaned:
        return False
    # "Is this sentence correct?" is a question syntactically but an explicit
    # writing edit semantically. Detect it before excluding ordinary questions.
    if writing_request_kind(cleaned) == "edit":
        return True
    if "?" in cleaned:
        return False
    if is_lightweight_chat_turn(cleaned):
        return False
    if is_comparison_question(cleaned) or is_writing_deliverable_request(cleaned):
        return False
    words = cleaned.split()
    if len(words) < 3 or len(words) > 16:
        return False
    return bool(_FRAGMENT_LEAD.match(cleaned))
