"""Whether a draft request already says what the draft is for.

"Write me an email" says nothing yet, so the reply asks one question;
"email my boss about PTO" has its purpose and is drafted now.
"""

from app.modules.chat.prompt_constants.locale_cues import has_locale_cue, is_bare_locale_cue
from app.modules.chat.prompt_constants.writing_kind import PASTED_TEXT, writing_request_kind
from app.services.text_normalize import collapse_ws

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
    # The kind of email or message is its purpose.
    " resignation",
    " resign",
    " quit",
    " complaint",
    " complain",
    " reminder",
    " remind",
    " invitation",
    " welcome",
    " introduc",
    " farewell",
    " goodbye",
    " condolence",
    " sympathy",
    " refund",
    " inquiry",
    " enquiry",
    " recommendation",
    " reference",
    " sick",
    " sorry",
    " wishing",
    " get well",
    " good luck",
    " congrats",
    " happy ",
    " anniversary",
    " graduation",
    " wedding",
    " opening",
    " launch",
    " sale",
    " hiring",
    " job",
)

# What a post or caption shows: "a caption for a beach sunset photo".
_SOCIAL_SUBJECT_MARKERS = (" for a ", " for an ", " for the ", " for our ", " of a ", " of my ")


def is_underspecified_writing_request(text: str) -> bool:
    """True for a bare sendable draft ask, not a supplied writing task."""
    kind = writing_request_kind(text)
    if kind not in {"email", "message", "social"}:
        return False
    cleaned = f" {collapse_ws(text).lower()} "
    if '"' in cleaned or "\u201c" in cleaned or PASTED_TEXT.search(text):
        return False
    if kind == "social" and any(marker in cleaned for marker in _SOCIAL_SUBJECT_MARKERS):
        return False
    # Localized writing cues are stored as complete bare requests. Any text
    # beyond the cue is user-supplied purpose/content and should be drafted.
    if has_locale_cue(text, "writing"):
        return is_bare_locale_cue(text, "writing")
    return not any(marker in cleaned for marker in _WRITING_PURPOSE_MARKERS)
