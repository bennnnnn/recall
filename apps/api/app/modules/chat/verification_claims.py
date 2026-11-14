"""The model's own claims that a result was verified, taken out of a reply.

Only the server's card says a result was checked; prose that says so on a turn the
server did not verify would fake the check mark.

A claim is the words that say a checker verified a result, in either order ("verified
with SymPy", "SymPy confirmed", "which the solver verified", "I ran it through SymPy and
got"), a check mark or brackets on the verb ("✅ Verified.", "(verified)"), or a "Verified"
label ("**Verified answer:**"). On a reply that holds maths, so do the words that say its
result was verified with no checker named ("The solution is verified:", "Both roots are
verified.", "x = 4. Verified.") and a check mark beside a value ("x = 42 ✓"). Only the claim
goes: a value in the same clause stays ("Recall's solver confirmed x = 42." keeps "x = 42.").
Everyday uses of the words stay, a checker that is no solver included: "The results were
confirmed.", "This has been verified.", "Your order was confirmed by the app.", "Validated:
the form accepts emails.", "Is this verified?", "verify that x = 2 satisfies it".
"""

from __future__ import annotations

import re

from app.services.answer_fence import map_outside_fences

_CHECK_MARKS = "✅✔☑✓"  # ✅ ✔ ☑ ✓
_EMPHASIS = r"(?:\*\*|__|\*|_)"
_CLAIM_VERB = r"(?:verified|checked|confirmed|validated|(?:double|cross)[- ]?checked)"
# What checks a result: the server's solvers, however a model names them. Never "the app":
# "Your order was confirmed by the app" is the user's errand.
_SOLVER = (
    r"(?:sym\s*py|rdkit|pubchem|recall['\u2019]s\s+(?:\w+\s+)?(?:solver|engine|checker)|"
    r"(?:the|a|our|my)\s+(?:(?:symbolic|math|maths|algebra)\s+)*(?:solver|engine|checker)|"
    r"symbolic\s+(?:math|maths|algebra)|(?:a|the)\s+computer\s+algebra\s+system|(?:a|the)\s+cas|"
    r"the\s+server)"
)
# A checker after the verb's "by": Recall itself too ("Checked by Recall").
_AGENT = rf"(?:{_SOLVER}|recall)"
_BY = r"(?:with|by|using|via|in|through)"
_BE = r"(?:was|is|were|are|has[ \t]+been|have[ \t]+been|had[ \t]+been|['\u2019]s[ \t]+been)"

# Claim words inside a clause, each removed where it stands.
_CLAIM_SPANS = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        # ", which SymPy verified," / ", as the solver confirmed,"
        rf"[ \t]*,[ \t]*(?:which|as)[ \t]+{_SOLVER}[ \t]+(?:has[ \t]+|have[ \t]+)?{_CLAIM_VERB}"
        r"[ \t]*,",
        # "was verified by the server (and)" in "The answer x = 42 was verified by … is final."
        rf"[ \t]+{_BE}[ \t]+(?:also[ \t]+)?{_CLAIM_VERB}[ \t]+{_BY}[ \t]+{_AGENT}\b"
        r"(?:[ \t]+and(?=[ \t]))?",
        # "(,) verified with SymPy", "as confirmed by the solver", "checked this with SymPy"
        rf"(?:[ \t]*[,\u2014\u2013][ \t]*|[ \t]+-[ \t]+|[ \t]*)(?:as[ \t]+|and[ \t]+)?{_CLAIM_VERB}"
        rf"[ \t]+(?:(?:[\w'\u2019]+[ \t]+){{1,2}}(?={_BY}[ \t]+{_SOLVER}))?{_BY}[ \t]+{_AGENT}\b",
        # "Recall's solver confirmed (that)", "SymPy-verified", "\u2014 SymPy agrees"
        rf"(?:[ \t]*[\u2014\u2013-][ \t]*)?\b{_SOLVER}[ \t-]+(?:(?:has|have|also|just)[ \t]+){{0,2}}"
        r"(?:verified|confirmed|checked|validated|verifies|confirms|checks|validates|agrees|agreed)"
        r"(?:[ \t]+that)?\b",
        # "I ran it through SymPy (and got)"
        rf"\b(?:i|we)[ \t]+(?:ran|put|plugged|checked)[ \t]+(?:it|this|that|them)[ \t]+"
        rf"(?:through|into|in|with)[ \t]+{_SOLVER}(?:[ \t]+and[ \t]+(?:got|found|get|find))?",
    )
)
# ✅ Verified with SymPy. / ✓ Checked, ending its sentence or line: "✅ Checked in online" stays.
_MARK_CLAIM = re.compile(
    rf"[ \t]*[{_CHECK_MARKS}]️?[ \t]*{_EMPHASIS}?[ \t]*{_CLAIM_VERB}\b(?:[ \t]+(?:"
    rf"{_BY}[ \t]+{_AGENT}|(?:with|using|via)[ \t]+[A-Za-z][\w.-]*))?"
    rf"[ \t]*{_EMPHASIS}?[ \t]*(?:[.!]{_EMPHASIS}?(?=\s|$)|(?=[ \t]*(?:\n|$)))",
    re.IGNORECASE,
)
# (verified) / (verified with SymPy) / [checked]
_PAREN_CLAIM = re.compile(
    rf"[ \t]*[(\[][ \t]*[{_CHECK_MARKS}]?️?[ \t]*{_CLAIM_VERB}"
    r"(?:[ \t]+(?:with|by|using|via|in)[ \t]+[^)\]\n]{1,40})?[ \t]*[)\]]",
    re.IGNORECASE,
)
# "Verified answer:" / "The verified result:": the label keeps its noun.
_NOUN_LABEL = re.compile(
    r"(?P<lead>^[ \t>]*(?:(?:[-*+]|\d{1,3}[.)])[ \t]+)?(?:\*\*|__)?[ \t]*(?:the[ \t]+)?)"
    rf"[{_CHECK_MARKS}]?️?[ \t]*verified[ \t]+(?P<noun>answer|result|solution|value)(?P<s>s?)"
    r"(?=[ \t]*(?:\*\*|__)?[ \t]*:)",
    re.IGNORECASE | re.MULTILINE,
)

# A reply that holds maths: an equation's value, or maths in $…$.
_MATHS = re.compile(r"\$[^$\n]+\$|\\[(\[]|[\w)\]}][ \t]*=[ \t]*[-\w(\\$.]")
_RESULT_NOUN = r"(?:results?|answers?|solutions?|values?|roots?)"
# On a maths reply: the whole clause says its result was verified ("The solution is verified").
_RESULT_CLAIM = re.compile(
    rf"(?:(?:the|this|that|these|those|each|both|all|my|our|every)[ \t]+)?(?:final[ \t]+)?"
    rf"{_RESULT_NOUN}(?:[ \t]+{_BE}|[ \t]+(?:is|are))?[ \t]+(?:(?:all|both|now|also)[ \t]+)?"
    r"(?:verified|validated|(?:double|cross)[- ]?checked)"
    r"(?:[ \t]+(?:independently|again|too|numerically|symbolically|algebraically))?"
    rf"(?:[ \t]*[{_CHECK_MARKS}]️?)?",
    re.IGNORECASE,
)
# On a maths reply: "Verified" alone as a clause or label ("x = 4. Verified.", "✓ Verified:").
_BARE_VERIFIED = re.compile(rf"[{_CHECK_MARKS}]?️?[ \t]*verified", re.IGNORECASE)
# On a maths reply: a check mark beside a value ("x = 42 ✓", "✅ x = 42").
_VALUE_MARK = re.compile(rf"[ \t]*[{_CHECK_MARKS}]️?(?=[ \t]*$)|^[ \t]*[{_CHECK_MARKS}]️?[ \t]*")
# A clause the claim left with no words of its own: "This", "I", "the result".
_LEFTOVER = re.compile(
    rf"(?:(?:this|that|it|i|we|which)|(?:the|this|that|my|our)[ \t]+(?:\w+[ \t]+)?{_RESULT_NOUN}"
    r"|(?:the|this|that)[ \t]+(?:work|working|calculation|step))?",
    re.IGNORECASE,
)

# Where a clause ends: sentence or clause punctuation (and emphasis closing on it) before a
# space or the line's end. "4.5", "5:00" and "https://" do not end one.
_CLAUSE_END = re.compile(rf"(?<=\S)([.!?;:]{_EMPHASIS}?)(?=[ \t]|$)")
# A clause's lead: list marker, quote, emphasis and check mark, before its words.
_LEAD = re.compile(
    rf"^(?P<keep>[ \t>]*(?:(?:[-*+]|\d{{1,3}}[.)])[ \t]+)?)(?P<dress>[*_ \t{_CHECK_MARKS}️]*)"
)
_SENTENCE_ENDS = (".", "!")


def _clause(text: str, end: str, *, maths: bool) -> str | None:
    """The clause without its claim words; None when nothing of its own is left."""
    if end.startswith("?"):
        return text
    lead = _LEAD.match(text)
    keep, dress = (lead.group("keep"), lead.group("dress")) if lead else ("", "")
    words = text[len(keep) + len(dress) :].rstrip(" \t*_")
    tail = text[len(keep) + len(dress) + len(words) :]
    if maths and (
        _RESULT_CLAIM.fullmatch(words) is not None
        or (_BARE_VERIFIED.fullmatch(words) is not None and end[:1] in {".", "!", ":", ""})
    ):
        return None
    stripped = words
    for span in _CLAIM_SPANS:
        stripped = span.sub("", stripped)
    if maths and _MATHS.search(words):
        # A check mark beside a value is the server's to draw.
        stripped = _VALUE_MARK.sub("", stripped)
        dress = "".join(char for char in dress if char not in _CHECK_MARKS + "\ufe0f")
    if stripped == words:
        return f"{keep}{dress}{words}{tail}"
    rest = stripped.strip(" \t,\u2014\u2013-")
    if _LEFTOVER.fullmatch(rest) is not None:
        return None
    first = rest.split(" ", 1)[0]
    if words[:1].isupper() and rest[:1].islower() and len(first) > 1:
        rest = rest[0].upper() + rest[1:]
    return f"{keep}{dress}{rest}{tail}"


def _label(match: re.Match[str]) -> str:
    """ "**Verified answer:**" keeps "**Answer:**", "The verified result:" "The result:"."""
    lead, noun = match.group("lead"), match.group("noun")
    after_the = lead.rstrip().lower().endswith("the")
    return f"{lead}{noun.lower() if after_the else noun.capitalize()}{match.group('s')}"


def _line_without_claims(line: str, *, maths: bool) -> str:
    line = _PAREN_CLAIM.sub("", _MARK_CLAIM.sub("", line))
    line = _NOUN_LABEL.sub(_label, line)
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
        clause = _clause(text, end, maths=maths)
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


def strip_verification_claims(text: str) -> str:
    """Remove the model's own "verified" claims from prose (fences untouched).

    Only the server's card says a result was checked: on an unverified turn a claim fakes
    the check mark, and on a verified one the card says it (a claim beside a wrong value
    would contradict it).
    """
    lower = text.lower()
    if not any(mark in text for mark in _CHECK_MARKS) and not any(
        word in lower for word in ("verif", "checked", "confirm", "validat", "sympy", "agree")
    ):
        return text
    maths = _MATHS.search(text) is not None

    def claimless(prose: str) -> str:
        out = "\n".join(_line_without_claims(line, maths=maths) for line in prose.split("\n"))
        out = re.sub(r"[ \t]+([.,;:!?])", r"\1", out)
        out = re.sub(r"[ \t]{2,}", " ", out)
        out = re.sub(r"[ \t]+\n", "\n", out)
        return re.sub(r"\n{3,}", "\n\n", out)

    return map_outside_fences(text, claimless).strip()
