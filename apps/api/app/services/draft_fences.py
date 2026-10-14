"""The send-ready drafts a reply can hold: ```email, ```message, ```linkedin, …

Chat, reminders and settings ask the same question about the reply before a
turn. After a draft, "add that I'll be late tomorrow at 9", "less groveling"
or "put it in Amharic" edits the draft; it is not a reminder, a settings
change or a new topic.
"""

from __future__ import annotations

import re

# The draft fences the mobile fence registry draws as copy cards.
DRAFT_FENCE = re.compile(
    r"^```(email|message|sms|reply|copy|twitter|tweet|x|linkedin|facebook|fb|instagram|"
    r"insta|ig|tiktok|threads|caption|social)[ \t]*$",
    re.IGNORECASE | re.MULTILINE,
)


def has_draft(text: str | None) -> bool:
    """True when the reply holds a send-ready draft."""
    return bool(text and DRAFT_FENCE.search(text))
