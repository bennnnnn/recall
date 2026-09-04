"""Email and copy-paste deliverable hints."""

import re

from app.services.chat.prompt_constants.format import is_comparison_question
from app.services.chat.prompt_constants.routing import (
    is_lightweight_chat_turn,
    is_writing_deliverable_request,
)
from app.services.text_normalize import collapse_ws

# Relative / subordinating leads that are not a complete question.
_FRAGMENT_LEAD = re.compile(
    r"^(?:whoever|whatever|whichever|however|because|although|though|"
    r"whereas|unless|until)\b",
    re.IGNORECASE,
)
_PROOFREAD_CUE = re.compile(
    r"\b(?:correct(?: this)?|proofread|fix (?:this )?(?:sentence|grammar)|"
    r"grammar(?: check)?|is this (?:correct|right|grammatical))\b",
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
    "1. Put a complete, warm, send-ready draft inside ```email (or ```message for SMS) "
    "now. Do not interview for tone. Include Subject: when you can infer "
    "one. Use To: only when the address is in memory or "
    "profile — never invent addresses.\n"
    "2. Resolve relationships from memory (my wife, my husband, mom, boss, etc.) to real "
    "names and emails when stored. Greet them by name in the body even if To: is omitted. "
    "If the name or address is unknown, omit To: and greet with Hi, — do not invent "
    "bracketed slots for name or email.\n"
    "3. After the fence, add at most ONE short line offering to adjust tone or length — "
    "not a questionnaire about content or recipient.\n"
    "4. Recall cannot send email or SMS. Never say you sent it, emailed them, or texted "
    "them — only that you drafted it for them to send."
)

EMAIL_ASK_PURPOSE_HINT = (
    "The user asked for an email or message but did not say what it is about "
    "(bare 'write me an email' / 'escribeme un correo'). "
    "Ask ONE short question for the purpose (and the recipient only if unknown). "
    "Do not invent a generic draft, placeholders, or a questionnaire."
)

COPY_DELIVERABLE_HINT = (
    "When drafting text the user will copy and send (SMS, email, reply, caption, "
    "social post, etc.), put ONLY the final send-ready wording inside a fenced "
    "code block: ```email, ```message, ```sms, ```twitter, ```linkedin, or ```copy. "
    "Use at most ONE such fence per response. "
    "Copy blocks must be ready to paste and send as-is: complete sentences, real names "
    "and subjects from context or memory — never [placeholders] or TBD. "
    "If they already said what to write, include the fence with a full draft now. "
    "If they only asked to write an email/message with no purpose, ask one question "
    "first — do not invent a generic letter. "
    "Omit To: and greet Hi, when the name or address is unknown. "
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
    if not cleaned or "?" in cleaned:
        return False
    if is_lightweight_chat_turn(cleaned):
        return False
    if is_comparison_question(cleaned) or is_writing_deliverable_request(cleaned):
        return False
    if _PROOFREAD_CUE.search(cleaned):
        return True
    words = cleaned.split()
    if len(words) < 3 or len(words) > 16:
        return False
    return bool(_FRAGMENT_LEAD.match(cleaned))
