"""Several problems in one message, each with its own setup and its own question.

"A car goes 100 m in 5 s; find its speed. A train goes 300 m in 10 s; find its speed." is
two problems. ``request_clauses`` reads a statement as more of the question before it and
"find its speed" as pointing back, so the train joined the car's question: one request no
subject could read, and the model wrote both answers unverified.

``problem_clauses`` reads the message's shape instead. A problem opens with a statement
that introduces a body of its own, afresh ("A train …", "An object …", "Another car …",
"Car B …"), and states quantities; a question about it follows. A statement about a body
already named ("The driver then brakes at 4 m/s²", "It bounces to 5 m") continues the
problem before it, and so does a new body's setup that steps on in its time ("A moment
later …"), changes it ("A 6 Ω resistor is added in series") or names what it named ("hung
from the spring"), and a question about the bodies together ("Which is faster?", "the total
momentum", "the new normal force"): "A car goes 100 m in 5 s. A train goes 300 m in 10 s.
Which is faster?" is one question about both. The first problem's opening statement comes
before its question too, or its question carries its own quantities.

Only text is read here. ``intents.plan_turn`` keeps the problems apart only when a subject
solves each one; otherwise the message is planned as before.
"""

from __future__ import annotations

import re
from dataclasses import replace

from app.modules.chat.turn_prep.clauses import (
    MAX_CLAUSES,
    STOP_WORDS,
    TASK_PATTERN,
    Clause,
    Cut,
    RequestSplit,
    candidate_segments,
    is_request,
    points_back,
    request_body,
    topic_words,
)

# A body introduced afresh: "a", "an" or "another" before a word or a number ("A 2 kg
# block"; never "A = 5 m²" or "A and B are events"), or a lettered label ("Car B").
_NEW_BODY = re.compile(
    r"^(?:(?i:an?|another)\s+(?P<next>[^\W_][\w'-]*)|(?P<label>[A-Z][a-z]+) [A-Z]\b)"
)
_QUANTITY = re.compile(r"\d")
# A question about the bodies together, or about what changed: it weighs them against each
# other, names several, or asks for a total, a new value or a meeting. It is about all of
# them, not a problem of its own.
_ABOUT_ALL = re.compile(
    r"\b(?:they|them|their|theirs|these|those|each|both|either|neither|former|latter|"
    r"the other|the same|same for|compar(?:e|ed|es|ing|ison)|which|whose|than|"
    r"total|combined|together|altogether|sum|difference|new|equivalent|overall|relative|"
    r"catch(?:es|ing)? up|overtak\w*|meets?|collid\w*|collision)\b",
    re.IGNORECASE,
)
# A statement that goes on with the problem before it: a step in its time ("A moment
# later", "then"), or a change to its setup ("added in series", "on top of the first box").
_CONTINUES = re.compile(
    r"\b(?:later|then|afterwards?|meanwhile|after that|at the same time|same|first|previous|"
    r"earlier|original|added|in series|in parallel)\b",
    re.IGNORECASE,
)
_THE_NAMED = re.compile(r"\bthe ([^\W\d_][\w'-]*)(?: ([^\W\d_][\w'-]*))?", re.IGNORECASE)
# "A car goes 100 m in 5 s, find its speed": a question joined to its setup by a comma.
_JOINED_ASK = re.compile(rf", (?=(?:{TASK_PATTERN}|what|what's|how)\b)", re.IGNORECASE)
# A sentence that ends on a quantity whose unit is a capital ("… a force of 10 N. Find …",
# "… 4 Ω. Find …"): ``request_clauses`` cuts after a capital only for a new request.
_QUANTITY_END = re.compile(r"(?<=\d)(?P<unit> ?[^\W\d_][\w/²³°]{0,5})\. (?=[A-Z])")


def opens_problem(text: str) -> bool:
    """A statement that introduces a body of its own and states its quantities."""
    found = _NEW_BODY.match(text.strip())
    if found is None or not _QUANTITY.search(text) or points_back(text):
        return False
    word = found.group("label") or found.group("next")
    return word.lower() not in STOP_WORDS


def continues_problem(setup: str, earlier: str) -> bool:
    """Whether a new body's setup goes on with the problem before it: a step in its time or
    a change to it (``_CONTINUES``), or "the spring", "the solution": a thing the message
    already named."""
    if _CONTINUES.search(setup):
        return True
    named = topic_words(earlier)
    return any(
        word.lower() in named
        for found in _THE_NAMED.finditer(setup)
        for word in found.groups()
        if word is not None
    )


def about_all(text: str) -> bool:
    """A question about every body stated so far ("which is faster?", "compare them")."""
    return _ABOUT_ALL.search(text) is not None


def _sentences(segments: list[tuple[str, Cut]]) -> list[tuple[str, Cut]]:
    """Each segment cut at a sentence that ends on a quantity (``_QUANTITY_END``)."""
    out: list[tuple[str, Cut]] = []
    for raw, cut in segments:
        start = 0
        for found in _QUANTITY_END.finditer(raw):
            out.append((raw[start : found.start("unit")] + found.group("unit"), cut))
            start, cut = found.end(), Cut.SENTENCE
        out.append((raw[start:], cut))
    return out


def _with_joined_asks(segments: list[tuple[str, Cut]]) -> list[tuple[str, Cut]]:
    """Each problem's statement cut from a question joined to it by a comma, when two or
    more statements open problems: one alone is the message's only problem."""
    segments = _sentences(segments)
    out: list[tuple[str, Cut]] = []
    for raw, cut in segments:
        found = _JOINED_ASK.search(raw)
        ask = raw[found.end() :] if found else ""
        if (
            found is None
            or not opens_problem(raw[: found.start()])
            or not is_request(ask, Cut.COMMA)
        ):
            out.append((raw, cut))
            continue
        out.extend(((raw[: found.start()], cut), (ask, Cut.COMMA)))
    return out if sum(opens_problem(raw) for raw, _ in out) >= 2 else segments


def _said(context: list[str], clauses: list[Clause]) -> str:
    """The message before a new problem: its statements and questions so far."""
    return " ".join([*context, *(f"{clause.setup} {clause.text}" for clause in clauses)])


def _folded(last: Clause, raw: str, topics: frozenset[str]) -> Clause:
    return Clause(f"{last.text} {raw}", last.cut, last.topics | topics, last.setup)


def _opened(clause: Clause, setup: str) -> Clause:
    return replace(clause, topics=clause.topics | topic_words(setup), setup=setup)


def problem_clauses(text: str) -> RequestSplit | None:
    """The message's questions, one problem's after another's, each problem's first question
    with the statements that set it up (``Clause.setup``); None unless the message holds two
    or more problems by its shape (the module docstring)."""
    # No follow-up check: a problem that states its own quantities leans on nothing before
    # it ("Find the speed of a car that goes 100 m in 5 s" is no "that" from the chat).
    segments = candidate_segments(text)
    context: list[str] = []
    clauses: list[Clause] = []
    stated: list[str] = []
    stated_cut = Cut.SENTENCE
    for raw, cut in _with_joined_asks(segments):
        topics = topic_words(request_body(raw))
        if not clauses:
            if is_request(raw, Cut.START):
                clauses.append(Clause(raw, Cut.START, topics))
            else:
                context.append(raw)
        elif stated:
            if not is_request(raw, cut):
                stated.append(raw)
                continue
            # A question about every body, a setup that goes on with the problem before, or
            # a request of another kind ("Also, …"): no new problem. "Find the current"
            # names nothing of its own; its setup does.
            setup = " ".join(stated)
            if (
                about_all(raw)
                or cut == Cut.STRONG
                or continues_problem(setup, _said(context, clauses))
            ):
                return None
            clauses.append(_opened(Clause(raw, stated_cut, topics), setup))
            stated = []
        elif opens_problem(raw) and not is_request(raw, cut):
            stated, stated_cut = [raw], cut
        elif is_request(raw, cut) and topics and not points_back(raw):
            clauses.append(Clause(raw, cut, topics))
        else:
            clauses[-1] = _folded(clauses[-1], raw, topics)
    # A statement no question follows belongs to no problem of its own: a doubt, so none.
    if stated or not any(clause.setup for clause in clauses) or len(clauses) > MAX_CLAUSES:
        return None
    return _first_problem(context, clauses)


def _first_problem(context: list[str], clauses: list[Clause]) -> RequestSplit | None:
    """The first problem's setup: the statements before its question from the first that
    opens a body (or else the first with a quantity); what comes before it stays the
    message's context. A first problem with no quantity at all is no problem."""
    start = next((i for i, raw in enumerate(context) if opens_problem(raw)), None)
    if start is None:
        start = next((i for i, raw in enumerate(context) if _QUANTITY.search(raw)), None)
    if start is not None:
        clauses[0] = _opened(clauses[0], " ".join(context[start:]))
        context = context[:start]
    second = next(index for index, clause in enumerate(clauses) if index and clause.setup)
    first = " ".join(f"{clause.setup} {clause.text}" for clause in clauses[:second])
    if not _QUANTITY.search(first):
        return None
    return RequestSplit(" ".join(context), tuple(clauses))
