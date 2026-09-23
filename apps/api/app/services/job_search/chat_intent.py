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
_JOB_FOLLOW_UP = re.compile(
    r"^\s*(?:yes[,.!]?\s*)?(?:please\s+)?(?:"
    r"search(?:\s+(?:now|again|for))?|find|look(?:\s+again)?|go ahead|do it|start)"
    r"(?:\s+(?:me\s+)?)?(?:\d{1,2}|one|two|three|four|five|six|seven|eight|nine|"
    r"ten|eleven|twelve|thirteen|fourteen|fifteen)?(?:\s+(?:jobs?|roles?|matches))?"
    r"[.!]?\s*$",
    re.IGNORECASE,
)
_JOB_CONTEXT = re.compile(
    r"\b(my job|job search|job matches|job openings|target roles?|work mode|"
    r"experience level|start searching|searching for roles?|saved preferences)\b",
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


def wants_job_search_turn(messages: list[dict[str, object]]) -> bool:
    """Recognize terse My Job follow-ups using only recent conversation context.

    A message such as ``search 2`` is intentionally ambiguous on its own. It is
    a My Job action only when the immediately preceding exchange was about My
    Job, which prevents ordinary numbered web searches from being rerouted.
    """
    user_text = ""
    current_index = -1
    for index in range(len(messages) - 1, -1, -1):
        message = messages[index]
        if message.get("role") != "user":
            continue
        content = message.get("content")
        if isinstance(content, str):
            user_text = content.strip()
            current_index = index
            break
    if wants_job_search(user_text):
        return True
    if not user_text or not _JOB_FOLLOW_UP.fullmatch(user_text):
        return False
    recent = messages[max(0, current_index - 4) : current_index]
    return any(
        isinstance(message.get("content"), str)
        and bool(_JOB_CONTEXT.search(str(message["content"])))
        for message in recent
        if message.get("role") in {"user", "assistant"}
    )
