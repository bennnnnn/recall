"""Keyword intent for routing chat turns to the My Job tool.

Kept deliberately tight: career *talk* ("I got a job offer", "job
satisfaction") must not trigger a job-board search.
"""

from __future__ import annotations

import re

_JOB_INTENT = re.compile(
    r"\b("
    r"find (me )?(a |some )?(new )?(jobs?|work|roles?|openings?|positions?)"
    r"|search (for )?(jobs?|roles?|openings?|positions?)"
    r"|look(ing)? for (jobs?|roles?|openings?|positions?|work)"
    r"|job (search|matches|listings|openings)"
    r"|my (job )?matches"
    r"|new (job )?matches"
    r"|jobs? (for me|near me|in my area)"
    r"|any (new )?(jobs?|openings?|positions?) (for me|out there)"
    r")",
    re.IGNORECASE,
)


def wants_job_search(text: str) -> bool:
    """True when the user is asking to find or review job openings."""
    return bool(_JOB_INTENT.search(text))
