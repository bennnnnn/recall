"""My Job product boundary for chat.

The generic automation engine still exists internally, but My Job is now only
a dedicated job-search assistant configured in its own screen.
"""

from __future__ import annotations

AUTOMATIONS_HINT = (
    "Recall **My Job** is only for scheduled job searches. It is not a generic task or "
    "automation builder. If the user asks Recall to find matching jobs daily or weekly, "
    "explain briefly that they can open My Job to provide target roles, skills, location, "
    "experience level, desired number of matches, and delivery schedule. Do not emit an "
    "```automation fence and do not claim a search was created from chat. For unrelated "
    "recurring requests, use Schedule only when it is genuinely a dated reminder; otherwise "
    "answer normally without inventing a background automation."
)
