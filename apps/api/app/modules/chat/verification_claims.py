"""The model's own claims that a result was verified, taken out of a reply.

Only the server's card says a result was checked; prose that says so would fake the check
mark, on any turn.

A claim says a result was checked, as done. On every turn, one that names the app's checker
goes: "verified with SymPy", "SymPy confirmed x = 42", "which the solver verified", "This was
verified by the server", "I ran it through SymPy and got x = 42", "✅ Verified with SymPy",
"x = 6, confirmed by the app". On a turn that can show a card (``finalize_subjects``), so do
a check mark or brackets on the verb ("✅ Verified.", "(verified)") and a "Verified" label
("**Verified answer:**"); on such a turn whose reply holds maths, so do the words that say
its result was checked with no checker named ("The solution is verified by substitution:",
"I've verified the answer:", "x = 6, which I verified.", "x = 6 is verified.", "x = 6 —
confirmed.", "Double-checked: x = 6"). Only the claim goes, never the value beside it
("Recall's solver confirmed x = 42." keeps "x = 42."), and a claim's words go only when what
is left still states a result.

What a tool does is no claim ("SymPy checks equality with simplify", "The server validates
the request body"), nor is an everyday use of the words ("The results were confirmed.",
"Your order was confirmed by the app.", "Each session is checked by the server"), a question,
a check the reader is asked to do, code (fences and inline spans), or a check mark beside a
value: in "check my work" it marks the student's own lines, ✗ beside ✓.
"""

from __future__ import annotations

import re

from app.services.answer_fence import map_outside_fences

_CHECK_MARKS = "✅✔☑✓"  # ✅ ✔ ☑ ✓
_EMPHASIS = r"(?:\*\*|__|\*|_)"
# Said as done: a past tense or a participle, never what a tool does ("SymPy checks …").
_CLAIM_VERB = r"(?:verified|checked|confirmed|validated|(?:double|cross)[- ]?checked)"
# What checks a result: the server's solvers, however a model names them. Never "the app"
# ("Your order was confirmed by the app") nor a checker with no maths in its name ("The
# checker validates each move").
_SOLVER = (
    r"(?:sym\s*py|rdkit|pubchem|recall['\u2019]s\s+(?:\w+\s+)?(?:solver|engine|checker)|"
    r"(?:the|a|our|my)\s+(?:(?:symbolic|math|maths|algebra)\s+)*solver|"
    r"(?:the|a|our|my)\s+(?:(?:symbolic|math|maths|algebra)\s+)+(?:engine|checker)|"
    r"symbolic\s+(?:math|maths|algebra)|(?:a|the)\s+computer\s+algebra\s+system|(?:a|the)\s+cas|"
    r"the\s+server)"
)
# A checker after the verb's "by": Recall itself too ("Checked by Recall").
_AGENT = rf"(?:{_SOLVER}|recall)"
_BY = r"(?:with|by|using|via|in|through)"
_BE = r"(?:was|is|were|are|has[ \t]+been|have[ \t]+been|had[ \t]+been|['\u2019]s[ \t]+been)"
_RESULT_NOUN = r"(?:results?|answers?|solutions?|values?|roots?)"
# What a claim naming the app leaves: maths ("x = 4, confirmed by the app"), never an errand.
_MATHS_VALUE = re.compile(r"\$|\\[(\[]|[A-Za-z][\w']{0,3}[ \t]*=")
# A result a clause states: a value ("x = 42", "$x$", "42") or a result's noun.
_STATES_RESULT = re.compile(
    rf"\$|\\[(\[]|[A-Za-z][\w']{{0,3}}[ \t]*=|\d|\b{_RESULT_NOUN}\b", re.IGNORECASE
)
# What a claim's colon leads to when it is a label ("Double-checked: x = 6").
_VALUE_START = re.compile(
    r"[ \t]*(?:\*\*|__)?[ \t]*(?:\$|\\[(\[]|[A-Za-z][\w']{0,3}[ \t]*=|[-\u2212]?\d)"
)

# Claim words inside a clause, each removed where it stands when the clause still states a
# result without them.
_CLAIM_SPANS = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        # ", which SymPy verified," / ", as the solver confirmed,"
        rf"[ \t]*,[ \t]*(?:which|as)[ \t]+{_SOLVER}[ \t]+"
        rf"(?:(?:has|have|['\u2019]ve|also|just)[ \t]+){{0,2}}{_CLAIM_VERB}"
        r"(?:[ \t]+(?:it|this|that|them))?(?:[ \t]*,|$)",
        # "was verified by the server (and)" in "The answer x = 42 was verified by … is final."
        rf"[ \t]+{_BE}[ \t]+(?:also[ \t]+)?{_CLAIM_VERB}[ \t]+{_BY}[ \t]+{_AGENT}\b"
        r"(?:[ \t]+and(?=[ \t]))?",
        # "(,) verified with SymPy", "as confirmed by the solver", "checked this with SymPy"
        rf"(?:[ \t]*[,\u2014\u2013][ \t]*|[ \t]+-[ \t]+|[ \t]*)(?:as[ \t]+|and[ \t]+)?{_CLAIM_VERB}"
        rf"[ \t]+(?:(?:[\w'\u2019]+[ \t]+){{1,2}}(?={_BY}[ \t]+{_SOLVER}))?{_BY}[ \t]+{_AGENT}\b",
        # "Recall's solver confirmed (that)", "SymPy-verified", "— SymPy agrees"
        rf"(?:[ \t]*[\u2014\u2013-][ \t]*)?\b{_SOLVER}[ \t-]+(?:(?:has|have|also|just)[ \t]+){{0,2}}"
        r"(?:verified|confirmed|checked|validated|agrees|agreed)(?:[ \t]+that)?\b",
        # "I ran it through SymPy (and got)", before its value or nothing more
        rf"\b(?:i|we)[ \t]+(?:ran|put|plugged|checked)[ \t]+(?:it|this|that|them)[ \t]+"
        rf"(?:through|into|in|with)[ \t]+{_SOLVER}(?:[ \t]+and[ \t]+(?:got|found)(?=[ \t]+"
        r"(?:the[ \t]+same\b|\$|[A-Za-z][\w']{0,3}[ \t]*=|[-\u2212]?\d))|(?=[ \t]*$))",
    )
)
# The app named as the checker: what it leaves must be maths ("Your order was confirmed by
# the app" is the user's errand).
_APP_SPANS = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        rf"[ \t]+{_BE}[ \t]+(?:also[ \t]+)?{_CLAIM_VERB}[ \t]+{_BY}[ \t]+the[ \t]+app\b",
        rf"(?:[ \t]*[,\u2014\u2013][ \t]*|[ \t]+)(?:as[ \t]+)?{_CLAIM_VERB}[ \t]+{_BY}[ \t]+"
        r"the[ \t]+app\b",
        r"\bthe[ \t]+app[ \t]+(?:has[ \t]+)?(?:verified|confirmed|checked)(?:[ \t]+that)?\b",
    )
)
# On a maths reply: ", which I verified" after a value.
_OWN_RELATIVE = re.compile(
    rf"[ \t]*,[ \t]*(?:which|as)[ \t]+(?:i|we)[ \t]+(?:(?:have|['\u2019]ve|also|just)[ \t]+){{0,2}}"
    rf"{_CLAIM_VERB}(?:[ \t]+(?:it|this|that|them))?(?:[ \t]*,|$)",
    re.IGNORECASE,
)
# ✅ Verified with SymPy. / ✓ Checked, ending its sentence or line: "✅ Checked in online" stays.
_MARK_CLAIM = re.compile(
    rf"[ \t]*[{_CHECK_MARKS}]️?[ \t]*{_EMPHASIS}?[ \t]*{_CLAIM_VERB}\b(?:[ \t]+(?:"
    rf"{_BY}[ \t]+{_AGENT}|(?:with|using|via)[ \t]+[A-Za-z][\w.-]*))?"
    rf"[ \t]*{_EMPHASIS}?[ \t]*(?:[.!]{_EMPHASIS}?(?=\s|$)|(?=[ \t]*(?:\n|$)))",
    re.IGNORECASE,
)
# On any turn, a mark's claim that names the checker: "✅ Verified with SymPy."
_MARK_CHECKER = re.compile(
    rf"[ \t]*[{_CHECK_MARKS}]\ufe0f?[ \t]*{_EMPHASIS}?[ \t]*{_CLAIM_VERB}[ \t]+{_BY}[ \t]+"
    rf"{_AGENT}\b[ \t]*{_EMPHASIS}?[ \t]*(?:[.!]{_EMPHASIS}?(?=\s|$)|(?=[ \t]*(?:\n|$)))",
    re.IGNORECASE,
)
# (verified) / (verified with SymPy) / [checked]
_PAREN_CLAIM = re.compile(
    rf"[ \t]*[(\[][ \t]*[{_CHECK_MARKS}]?️?[ \t]*{_CLAIM_VERB}"
    r"(?:[ \t]+(?:with|by|using|via|in)[ \t]+[^)\]\n]{1,40})?[ \t]*[)\]]",
    re.IGNORECASE,
)
# On any turn, brackets that name the checker: "(verified by SymPy)".
_PAREN_CHECKER = re.compile(
    rf"[ \t]*[(\[][ \t]*[{_CHECK_MARKS}]?\ufe0f?[ \t]*{_CLAIM_VERB}[ \t]+{_BY}[ \t]+{_AGENT}\b"
    r"[^)\]\n]{0,30}[)\]]",
    re.IGNORECASE,
)
# "Verified answer:" / "The verified result:": the label keeps its noun.
_NOUN_LABEL = re.compile(
    r"(?P<lead>^[ \t>]*+(?:(?:[-*+]|\d{1,3}[.)])[ \t]++)?(?:\*\*|__)?[ \t]*+(?:the[ \t]++)?)"
    rf"(?:[{_CHECK_MARKS}]️?[ \t]*+)?verified[ \t]++(?P<noun>answer|result|solution|value)"
    r"(?P<s>s?)(?=[ \t]*+(?:\*\*|__)?[ \t]*+:)",
    re.IGNORECASE | re.MULTILINE,
)

# A reply that holds maths: an equation's value, or maths in $…$ (in its prose).
_MATHS = re.compile(r"\$[^$\n]+\$|\\[(\[]|[\w)\]}][ \t]*=[ \t]*[-\w(\\$.]")
_HOW = r"(?:[ \t]+(?:by|through|using|via)[ \t]+[^,;:.!?\n]{1,40})?"
_ADVERB = r"(?:[ \t]+(?:independently|again|twice|too|numerically|symbolically|algebraically))?"
# On a maths reply: the whole clause says its result was checked ("The solution is verified
# by substitution", "Both roots are verified").
_RESULT_CLAIM = re.compile(
    rf"(?:(?:the|this|that|these|those|each|both|all|my|our|every)[ \t]+)?(?:final[ \t]+)?"
    rf"{_RESULT_NOUN}(?:[ \t]+{_BE}|[ \t]+(?:is|are))?[ \t]+(?:(?:all|both|now|also)[ \t]+)?"
    rf"(?:verified|validated|(?:double|cross)[- ]?checked){_ADVERB}{_HOW}"
    rf"(?:[ \t]*[{_CHECK_MARKS}]️?)?",
    re.IGNORECASE,
)
# On a maths reply: the writer's own check of its result, the whole clause ("I've verified the
# answer", "I verified this answer by substituting it back").
_OWN_CHECK = re.compile(
    r"(?:i|we)(?:['\u2019]ve|[ \t]+have|[ \t]+had)?(?:[ \t]+(?:also|just|now|already))?[ \t]+"
    rf"{_CLAIM_VERB}(?:[ \t]+(?:it|this|that|them|(?:(?:the|this|that|my|our|your|each|both|all)"
    rf"[ \t]+)?(?:final[ \t]+)?{_RESULT_NOUN}))?{_ADVERB}{_HOW}",
    re.IGNORECASE,
)
# On a maths reply: "(I checked it twice)" after a value.
_OWN_PAREN = re.compile(
    r"[ \t]*\([ \t]*(?:i|we)(?:['\u2019]ve|[ \t]+have)?(?:[ \t]+(?:also|just|already))?[ \t]+"
    rf"{_CLAIM_VERB}(?:[ \t]+(?:it|this|that|them))?{_ADVERB}[ \t]*\)",
    re.IGNORECASE,
)
# On a maths reply: the claim alone as a clause or label ("x = 4. Verified.", "✓ Verified:",
# "Double-checked: x = 6").
_BARE_CLAIM = re.compile(rf"[{_CHECK_MARKS}]?️?[ \t]*{_CLAIM_VERB}", re.IGNORECASE)
# On a maths reply: the claim tagged after a value ("x = 6 — confirmed", "x = 6, verified").
_TAGGED_CLAIM = re.compile(
    rf"(?:[ \t]*[,\u2014\u2013]|[ \t]+-)[ \t]*(?:(?:and|now|also|fully)[ \t]+)?{_CLAIM_VERB}"
    rf"{_ADVERB}(?:[ \t]*[{_CHECK_MARKS}]️?)?$",
    re.IGNORECASE,
)
# On a maths reply: a value said to be checked ("x = 6 is verified").
_VALUE_CLAIM = re.compile(
    rf"[ \t]+{_BE}[ \t]+(?:(?:now|also|all|both)[ \t]+)?{_CLAIM_VERB}{_ADVERB}{_HOW}$",
    re.IGNORECASE,
)
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
# Inline code spans, held out of every rule as one private-use character each.
_INLINE_CODE = re.compile(r"``(?:[^`\n]|`(?!`))+``|`[^`\n]+`")
_HELD = 0xE000


def _whole_claim(words: str, end: str, following: str) -> bool:
    """On a maths reply: the clause is a claim and nothing else. A label's colon leads to a
    value ("Confirmed: x = 6"), never to a sentence ("Checked: you forgot the minus")."""
    if _RESULT_CLAIM.fullmatch(words) or _OWN_CHECK.fullmatch(words):
        return True
    if _BARE_CLAIM.fullmatch(words) is None:
        return False
    return end[:1] in {".", "!", ""} or (end[:1] == ":" and bool(_VALUE_START.match(following)))


def _cut(words: str, span: re.Pattern[str], leaves: re.Pattern[str], *, alone: bool) -> str:
    """``words`` without ``span`` when what is left matches ``leaves`` (or, ``alone``, is no
    words of its own), else as they were."""
    out = span.sub("", words)
    rest = out.strip(" \t,\u2014\u2013-")
    kept = (alone and _LEFTOVER.fullmatch(rest) is not None) or leaves.search(rest) is not None
    return out if out != words and kept else words


def _without_spans(words: str, *, maths: bool) -> str:
    """The clause's words without each claim span that leaves a result stated."""
    stripped = words
    for span in _CLAIM_SPANS:
        stripped = _cut(stripped, span, _STATES_RESULT, alone=True)
    for span in _APP_SPANS:
        stripped = _cut(stripped, span, _MATHS_VALUE, alone=False)
    if maths and _STATES_RESULT.search(stripped):
        stripped = _OWN_PAREN.sub("", _OWN_RELATIVE.sub("", stripped))
        for span in (_TAGGED_CLAIM, _VALUE_CLAIM):
            stripped = _cut(stripped, span, _MATHS_VALUE, alone=False)
    return stripped


def _clause(text: str, end: str, following: str, *, maths: bool) -> str | None:
    """The clause without its claim words; None when nothing of its own is left."""
    if end.startswith("?"):
        return text
    lead = _LEAD.match(text)
    keep, dress = (lead.group("keep"), lead.group("dress")) if lead else ("", "")
    words = text[len(keep) + len(dress) :].rstrip(" \t*_")
    tail = text[len(keep) + len(dress) + len(words) :]
    if maths and _whole_claim(words, end, following):
        return None
    stripped = _without_spans(words, maths=maths)
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


def _line_without_claims(line: str, *, card: bool, maths: bool) -> str:
    if card:
        line = _NOUN_LABEL.sub(_label, _PAREN_CLAIM.sub("", _MARK_CLAIM.sub("", line)))
    else:
        line = _PAREN_CHECKER.sub("", _MARK_CHECKER.sub("", line))
    pieces = _CLAUSE_END.split(line)
    kept: list[list[str]] = []
    # After a claim that ended in a colon, its value takes the claim's place.
    space: str | None = None
    for index in range(0, len(pieces), 2):
        text = pieces[index]
        end = pieces[index + 1] if index + 1 < len(pieces) else ""
        following = pieces[index + 2] if index + 2 < len(pieces) else ""
        if space is not None:
            text = space + text.lstrip(" \t")
            space = None
        clause = _clause(text, end, following, maths=maths)
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


def _held(line: str) -> tuple[str, list[str]]:
    """The line with each inline code span held out as one character, and the spans."""
    spans: list[str] = []

    def hold(match: re.Match[str]) -> str:
        spans.append(match.group(0))
        return chr(_HELD + len(spans) - 1)

    return _INLINE_CODE.sub(hold, line), spans


def _tidied(line: str, *, card: bool, maths: bool) -> str:
    """The line without its claims (each takes its own space with it); a line with none is
    left exactly as written (a French " :", an indent, a Markdown line break). Inline code is
    code: no rule reads it."""
    held, spans = _held(line) if "`" in line else (line, [])
    out = _line_without_claims(held, card=card, maths=maths)
    if out == held:
        return line
    for index, span in enumerate(spans):
        out = out.replace(chr(_HELD + index), span)
    return out.rstrip()


def _prose_holds_maths(text: str) -> bool:
    """Whether the reply's prose holds maths: never its code, fenced or inline."""
    prose: list[str] = []

    def collect(run: str) -> str:
        prose.append(_INLINE_CODE.sub(" ", run))
        return run

    map_outside_fences(text, collect)
    return any(_MATHS.search(run) for run in prose)


def strip_verification_claims(text: str, *, card_turn: bool = True) -> str:
    """Remove the model's own "verified" claims from prose (code untouched): on every turn
    those that name the app's checker, and on a ``card_turn`` the rest.

    Only the server's card says a result was checked: on an unverified turn a claim fakes
    the check mark, and on a verified one the card says it (a claim beside a wrong value
    would contradict it).
    """
    lower = text.lower()
    if not any(mark in text for mark in _CHECK_MARKS) and not any(
        word in lower for word in ("verif", "checked", "confirm", "validat", "sympy", "agree")
    ):
        return text
    maths = card_turn and _prose_holds_maths(text)

    def claimless(prose: str) -> str:
        lines = prose.split("\n")
        out = "\n".join(_tidied(line, card=card_turn, maths=maths) for line in lines)
        return re.sub(r"\n{3,}", "\n\n", out)

    return map_outside_fences(text, claimless).strip()
