"""Keyword intent for routing chat turns to the My Job tool.

Kept deliberately tight: career *talk* ("I got a job offer", "job
satisfaction") must not trigger a job-board search.
"""

from __future__ import annotations

import re

_FIND_JOB_INTENT = re.compile(
    r"\b(find|show|search|look(?:ing)?)\b.{0,100}"
    r"\b(jobs?|roles?|openings?|positions?|work)\b",
    re.IGNORECASE,
)
_MY_JOB_INTENT = re.compile(
    r"\b("
    r"job (search|matches|listings|openings)"
    r"|my (job )?matches"
    r"|new (job )?matches"
    r"|jobs? (for me|near me|in my area)"
    r"|any (new )?(jobs?|openings?|positions?) (for me|out there)"
    r")\b",
    re.IGNORECASE,
)
_CHANGE_JOB_INTENT = re.compile(
    r"\b(change|update|set|switch|add|remove|replace|edit|pause|resume|make|prefer|use)\b"
    r".{0,120}\b("
    r"my job|job search|target roles?|job types?|experience(?: level)?|"
    r"work mode|salary|location|hybrid|remote|on[ -]?site|sponsorship|"
    r"excluded companies|delivery|frequency"
    r")\b",
    re.IGNORECASE,
)
_CHECK_JOB_INTENT = re.compile(
    r"\b(check|analy[sz]e|compare|evaluate|review)\b.{0,100}"
    r"\b(job|role|opening|posting|position|fit|match)\b",
    re.IGNORECASE,
)
_FIT_JOB_INTENT = re.compile(
    r"\b(?:would|will|could|do|am|is)?\s*(?:i|this|that)?\s*(?:be|a)?\s*"
    r"(?:good|strong|right)?\s*fit\b.{0,80}\b(for me|my background|this role|this job)\b",
    re.IGNORECASE,
)
_PREFERENCE_VALUE_INTENT = re.compile(
    r"\b(only|prefer|want|need|switch(?:ing)? to|make it)\b.{0,60}"
    r"\b(remote|hybrid|on[ -]?site|internship|entry(?: level)?|mid(?: level)?|"
    r"senior|sponsorship|jobs?|roles?)\b",
    re.IGNORECASE,
)


def wants_job_search(text: str) -> bool:
    """True when the user is asking to find or review job openings."""
    return bool(
        _FIND_JOB_INTENT.search(text)
        or _MY_JOB_INTENT.search(text)
        or _CHANGE_JOB_INTENT.search(text)
        or _CHECK_JOB_INTENT.search(text)
        or _FIT_JOB_INTENT.search(text)
        or _PREFERENCE_VALUE_INTENT.search(text)
    )
