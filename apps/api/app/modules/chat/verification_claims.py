"""The model's own claims that a result was verified, taken out of a reply.

Only the server's card says a result was checked; prose that says so on a turn the
server did not verify would fake the check mark.

A claim is one thing, however it is worded and dressed: a clause that says a result was
verified by a checker, in either order ("verified with SymPy", "I double-checked this with
the solver", "The server verified this result", "SymPy-verified"), a result said to be
verified with no checker ("The result has been verified."), a check mark or brackets on the
verb ("✅ Verified.", "(verified)"), or a "Verified" label ("✓ Verified: x = 42",
"- **Verified answer:** …"), under any list marker, quote or emphasis. Each line is cut into
clauses at sentence and clause punctuation; a clause that is a claim goes with its
punctuation, a colon's value stays, and a label keeps its noun ("**Answer:**"). A question
stays ("Is this verified?"), and so does every other use of the words: "verify that x = 2
satisfies it", "Once your email is verified", "✅ Checked in online", "✅ Confirmed: the
museum is open on Mondays".
"""

from __future__ import annotations

import re

from app.services.answer_fence import map_outside_fences

_CHECK_MARKS = "✅✔☑✓"  # ✅ ✔ ☑ ✓
_CLAIM_VERB = r"(?:verified|checked|confirmed|validated|(?:double|cross)[- ]?checked)"
# The verbs a bare label or a pronoun claim uses: "✅ Confirmed:" and "That's confirmed"
# are everyday status lines.
_STRONG_VERB = r"(?:verified|validated|(?:double|cross)[- ]?checked)"
# What checks a result, however a model names the server's solvers.
_SOLVER = (
    r"(?:sym\s*py|rdkit|pubchem|"
    r"(?:the|a|our|my|recall['\u2019]s)\s+(?:(?:symbolic|math|maths|algebra)\s+)*"
    r"(?:solver|engine|checker)|"
    r"symbolic\s+(?:math|maths|algebra)|(?:a|the)\s+computer\s+algebra\s+system|(?:a|the)\s+cas|"
    r"the\s+server)"
)
# Right after the verb only: "checked the weather with the app" is the user's errand.
_CHECKER = rf"(?:{_SOLVER}|the\s+app|recall)"
_BY = r"(?:with|by|using|via|in|through)"
_EMPHASIS = r"(?:\*\*|__|\*|_)"

# ✅ Verified with SymPy. / ✓ Checked, ending its sentence or line: "✅ Checked in online" stays.
_MARK_CLAIM = re.compile(
    rf"[ \t]*[{_CHECK_MARKS}]️?[ \t]*{_EMPHASIS}?[ \t]*{_CLAIM_VERB}\b(?:[ \t]+(?:"
    rf"{_BY}[ \t]+{_CHECKER}|(?:with|using|via)[ \t]+[A-Za-z][\w.-]*))?"
    rf"[ \t]*{_EMPHASIS}?[ \t]*(?:[.!]{_EMPHASIS}?(?=\s|$)|(?=[ \t]*(?:\n|$)))",
    re.IGNORECASE,
)
# (verified) / (verified with SymPy) / [checked]
_PAREN_CLAIM = re.compile(
    rf"[ \t]*[(\[][ \t]*[{_CHECK_MARKS}]?️?[ \t]*{_CLAIM_VERB}"
    r"(?:[ \t]+(?:with|by|using|via|in)[ \t]+[^)\]\n]{1,40})?[ \t]*[)\]]",
    re.IGNORECASE,
)
# "x = 42, verified with SymPy" / "x = 42 as confirmed by the solver": the clause keeps its value.
_TAIL_CLAIM = re.compile(
    rf"(?:[ \t]*[,\u2014\u2013][ \t]*|[ \t]+-[ \t]+|[ \t]+(?=as[ \t]))(?:as[ \t]+|and[ \t]+)?"
    rf"{_CLAIM_VERB}[ \t]+{_BY}[ \t]+{_CHECKER}\b[ \t]*{_EMPHASIS}?$",
    re.IGNORECASE,
)

# Where a clause ends: sentence or clause punctuation (and emphasis closing on it) before a
# space or the line's end. "4.5", "5:00" and "https://" do not end one.
_CLAUSE_END = re.compile(rf"(?<=\S)([.!?;:]{_EMPHASIS}?)(?=[ \t]|$)")
# A clause's lead: list marker, quote, emphasis and check mark, before its words.
_LEAD = re.compile(
    rf"^(?P<keep>[ \t>]*(?:(?:[-*+]|\d{{1,3}}[.)])[ \t]+)?)(?P<dress>[*_ \t{_CHECK_MARKS}\ufe0f]*)"
)
# The clause says a checker checked it, in either order.
_CHECKER_CLAIMS = (
    re.compile(
        rf"\b{_CLAIM_VERB}[ \t]+(?:{_BY}[ \t]+{_CHECKER}\b|"
        rf"(?:[\w'\u2019]+[ \t]+){{1,2}}{_BY}[ \t]+{_SOLVER}\b)",
        re.IGNORECASE,
    ),
    re.compile(
        rf"\b{_SOLVER}[ \t-]+(?:(?:has|have|also|just|then|now|again)[ \t]+){{0,3}}"
        r"(?:verified|confirmed|checked|validated|double[- ]checked|verifies|confirms|checks|"
        r"validates)\b",
        re.IGNORECASE,
    ),
)
_RESULT_NOUN = (
    r"(?:(?:the|this|that|these|those|my|our|each|both|all|every)[ \t]+(?:(?:final|whole)[ \t]+)?"
    r"(?:results?|answers?|solutions?|values?|roots?|calculations?|computations?|working|work|"
    r"steps?))"
)
_BEEN = (
    r"(?:['\u2019]s|[ \t]+(?:has|have|had|was|were|is|are))(?:[ \t]+been)?[ \t]+"
    r"(?:(?:all|both|now|also)[ \t]+)?"
)
_HOW = r"(?:[ \t]+(?:independently|again|too|as[ \t]+well|numerically|symbolically|algebraically))?"
# The whole clause says a result was verified, with no checker named.
_BARE_CLAIM = re.compile(
    rf"(?:{_RESULT_NOUN}{_BEEN}{_CLAIM_VERB}|(?:this|that|it|everything){_BEEN}{_STRONG_VERB}){_HOW}",
    re.IGNORECASE,
)
# The whole clause is the label: "Verified", "✓ Verified" (its value follows a colon).
_BARE_LABEL = re.compile(_STRONG_VERB, re.IGNORECASE)
# "Verified answer" as a label keeps its noun.
_NOUN_LABEL = re.compile(
    r"verified[ \t]+(?P<noun>answer|result|solution|value)(?P<plural>s?)", re.IGNORECASE
)
_SENTENCE_ENDS = (".", "!")


def _is_claim(words: str) -> bool:
    return (
        any(pattern.search(words) for pattern in _CHECKER_CLAIMS)
        or _BARE_CLAIM.fullmatch(words) is not None
        or _BARE_LABEL.fullmatch(words) is not None
    )


def _clause(text: str, end: str) -> str | None:
    """The clause without its claim; None when the whole clause is one."""
    text = _TAIL_CLAIM.sub("", text)
    lead = _LEAD.match(text)
    keep, dress = (lead.group("keep"), lead.group("dress")) if lead else ("", "")
    words = text[len(keep) + len(dress) :].rstrip(" \t*_")
    label = _NOUN_LABEL.fullmatch(words)
    if label is not None:
        noun = label.group("noun").capitalize() + label.group("plural")
        opened = "".join(char for char in dress if char in "*_")
        return f"{keep}{opened}{noun}{text[len(keep) + len(dress) + len(words) :]}"
    if end.startswith("?") or not _is_claim(words):
        return text
    return None


def _line_without_claims(line: str) -> str:
    line = _PAREN_CLAIM.sub("", _MARK_CLAIM.sub("", line))
    pieces = _CLAUSE_END.split(line)
    kept: list[list[str]] = []
    # After a claim that ended in a colon, its value takes the claim's place.
    space: str | None = None
    for index in range(0, len(pieces), 2):
        text = pieces[index]
        end = pieces[index + 1] if index + 1 < len(pieces) else ""
        if space is not None:
            text = space + text.lstrip(" \t")
            space = None
        clause = _clause(text, end)
        if clause is not None:
            kept.append([clause, end])
            continue
        lead = _LEAD.match(text)
        if not kept and lead is not None and lead.group("keep").strip():
            # The line's list marker or quote stays for what follows the claim.
            kept.append([lead.group("keep"), ""])
        if end.startswith(":"):
            space = "" if not kept else text[: len(text) - len(text.lstrip(" \t"))]
        elif kept and end.startswith(_SENTENCE_ENDS) and kept[-1][1].startswith(";"):
            # "No closed form; this was verified." ends where the claim ended.
            kept[-1][1] = end
    return "".join(clause + end for clause, end in kept)


def _claimless(prose: str) -> str:
    out = "\n".join(_line_without_claims(line) for line in prose.split("\n"))
    out = re.sub(r"[ \t]+\n", "\n", out)
    return re.sub(r"\n{3,}", "\n\n", out)


def strip_verification_claims(text: str) -> str:
    """Remove the model's own "verified" claims from prose (fences untouched).

    Only the server's card says a result was checked: on an unverified turn a claim fakes
    the check mark, and on a verified one the card says it (a claim beside a wrong value
    would contradict it).
    """
    lower = text.lower()
    if not any(word in lower for word in ("verif", "checked", "confirm", "validat")):
        return text
    return map_outside_fences(text, _claimless).strip()
