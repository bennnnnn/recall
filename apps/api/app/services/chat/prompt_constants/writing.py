"""Email and copy-paste deliverable hints."""

import re

from app.services.chat.prompt_constants.format import is_comparison_question
from app.services.chat.prompt_constants.routing import (
    is_lightweight_chat_turn,
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
    "3. Return one draft by default. If the user explicitly asks for multiple versions, "
    "return exactly that many clearly labelled draft fences. Otherwise, after the fence, "
    "add at most ONE short line offering to adjust tone or length — not a questionnaire.\n"
    "4. Recall cannot send email or SMS. Never say you sent it, emailed them, or texted "
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
    "Use ```twitter for X/Twitter, ```linkedin for LinkedIn, and ```social for other "
    "platforms or generic captions. Put only publish-ready wording inside the fence. "
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
    "When drafting text the user will copy and send (SMS, email, reply, caption, "
    "social post, etc.), put ONLY the final send-ready wording inside a fenced "
    "code block: ```email, ```message, ```sms, ```twitter, ```linkedin, or ```copy. "
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
    "Never use ```copy or ```text for explanations, notes, advice, comparisons, or "
    "math/numeric final answers — those belong in plain markdown with `$...$` "
    "(pipe tables for X vs Y; bullets otherwise). Recall attaches verified math "
    "answers; do not emit ```answer / ```graph / ```geometry. "
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
