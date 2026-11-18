"""The parts of a short subject follow-up that do not depend on the subject.

Physics and chemistry each replay their previous problem when a line only
continues it: explain the result, ask for another quantity of the same setup,
give the result in another unit, or replace or scale one given (``scaled_followup``
reads the scaling). Each subject keeps its own asks, units and check that the
rewrite verifies; the message reading, the adjacent exchange, the follow-up
phrases and the text rewrites are the same for both and live here.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from collections.abc import Callable, Collection, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from app.services.latex_markup import without_markup
from app.services.law_binding.fit import read_givens
from app.services.law_binding.givens import Given
from app.services.law_binding.units import UnitTable
from app.services.number_text import fold_scientific
from app.services.scaled_followup import (
    Scaling,
    counted,
    owns,
    plays_role,
    scaled_name,
    subject_of,
    thrown_at,
    written_owner,
)

# A line that asks only to have the previous result explained, read lowercase.
EXPLAIN_RE = re.compile(
    r"^(?:"
    r"why(?: is (?:it|that)(?: [-+]?\d+(?:\.\d+)?(?: [a-zμµ°/^0-9.]+)?)?)?"
    r"|how(?: come| did you get (?:that|it)| does that work)?"
    r"|i (?:didn't|did not|don't|do not) (?:get|understand)(?: it)?"
    r"|help me understand(?: it)?"
    r"|(?:that(?:'s| is)|this is|i(?:'m| am)) confus(?:ed|ing)"
    r"|(?:(?:can|could) you )?(?:show|give) (?:me )?(?:the )?(?:steps|working|work|solution)"
    r"(?: please)?"
    r"|explain(?: (?:it|that|this|the answer))?(?: please)?"
    r"|(?:walk me through|break down) (?:it|that|this)(?: please)?"
    r"|step by step(?: please)?"
    r")$"
)

_LEAD = r"(?:(?:and|but|so|ok(?:ay)?|now|then|please|can you|could you)[ ,]+)*"

# "in km/h", "what is that in mph", "convert it to feet please".
_IN_UNIT = re.compile(
    _LEAD + r"(?:(?:what(?:'s| is) (?:that|it|this|the answer)|convert (?:that|it|this|the answer)"
    r"|give (?:it|that|me (?:that|it)|the answer)|(?:put|write|show) (?:it|that|the answer))[ ]+)?"
    r"(?:in|into|to)[ ]+(?P<unit>[a-zμµ°/][a-zμµ°/^0-9.]{0,11})"
    r"(?:[ ,]+(?:please|pls|instead|too))*",
    re.IGNORECASE,
)

# "and after 10 s", "what if it's dropped from 80 m", "and 0.001 M": one new value.
_NEW_VALUE = re.compile(
    _LEAD + r"(?:(?:what about|how about|what if|try|with|instead)[ ,]+)?"
    r"(?:(?:it|she|he|they)(?:'s|'re| is| was| were| are)? )?"
    r"(?:[a-z]+ )?"
    r"(?:(?:after|for|from|at|with|over|of|to|in) )?"
    r"(?P<value>[-+]?(?:\d+(?:\.\d+)?|\.\d+)(?:e[-+]?\d+)?) ?"
    r"(?P<unit>[a-zμµ°/][a-zμµ°/^0-9.]{0,11})"
    r"(?: instead)?",
    re.IGNORECASE,
)

_ASK_SENTENCE = re.compile(r"\b(?:find|what|calculate|determine|how)\b", re.IGNORECASE)
_NAME_FILLER = re.compile(r"\b(?:final|initial|the|its|a|an)\b")


def message_role_content(message: Any) -> tuple[str | None, str | None]:
    """(role, content) of a chat message: a pair, a mapping, or a row with attributes."""
    if isinstance(message, tuple) and len(message) == 2:
        role, content = message
        if isinstance(role, str) and isinstance(content, str):
            return role, content
        return None, None
    if isinstance(message, Mapping):
        role = message.get("role")
        content = message.get("content")
    else:
        role = getattr(message, "role", None)
        content = getattr(message, "content", None)
    if not isinstance(role, str) or not isinstance(content, str):
        return None, None
    return role, content


def adjacent_problem(recent: Sequence[Any], is_subject: Callable[[str], bool]) -> str | None:
    """The user's problem in the last exchange, when it was answered and is this subject's."""
    if len(recent) < 2:
        return None
    role, prior = message_role_content(recent[-2])
    answer_role, answer = message_role_content(recent[-1])
    if role != "user" or answer_role != "assistant":
        return None
    if not prior or not prior.strip() or not answer or not answer.strip():
        return None
    if not is_subject(prior):
        return None
    return prior


def asked_unit(line: str) -> str | None:
    """The unit a line asks the previous result in: ``in km/h please`` → ``km/h``."""
    match = _IN_UNIT.fullmatch(line)
    return None if match is None else match.group("unit")


# A clock time is not a quantity: "and at 5 pm?" is never 5 picometres.
_CLOCK_UNITS = frozenset({"am", "pm", "a.m", "p.m", "a.m.", "p.m.", "oclock", "o'clock"})


def new_value(line: str) -> tuple[str, str] | None:
    """``and after 10 s`` → ``("10", "s")``: one value with its unit, nothing else."""
    match = _NEW_VALUE.fullmatch(line)
    if match is None or match.group("unit").lower() in _CLOCK_UNITS:
        return None
    return match.group("value"), match.group("unit")


# "10 s", "32.0 g", "200 \u03a9": a value and its unit, written alone.
_WRITTEN_VALUE = re.compile(
    r"(?P<value>[-+]?(?:\d+(?:\.\d+)?|\.\d+)(?:e[-+]?\d+)?) ?(?P<unit>\S(?:[^\n]{0,14}\S)?)",
    re.IGNORECASE,
)


def written_value(text: str) -> tuple[str, str] | None:
    """``10 s`` → ``("10", "s")``: a value given alone with its unit, as a change names it."""
    match = _WRITTEN_VALUE.fullmatch(" ".join(text.split()))
    if match is None or match.group("unit").lower() in _CLOCK_UNITS:
        return None
    return match.group("value"), match.group("unit")


def _quoted_numbers(text: str) -> set[float]:
    return {float(number) for number in re.findall(r"\d+(?:\.\d+)?", text)}


def scaled_value(value: float, factor: float) -> str:
    """The scaled number as a student would write it: 2 kg doubled is ``4``, not ``4.0``."""
    return f"{value * factor:.6g}"


def in_unit(prior: str, unit: str) -> str:
    """The prior problem asking for its answer in ``unit``."""
    return prior.rstrip() + f" Give the answer in {unit}."


def followup_line(query: str | None) -> str | None:
    """The line with its quotes, outer punctuation and repeated spaces taken off."""
    if not query or not query.strip():
        return None
    text = " ".join(query.replace("\u2019", "'").split()).strip(" \"'`")
    text = text.strip(".,!?:;")
    return text or None


def ask_replaced(prior: str, phrase: str) -> str:
    """The prior problem asking "Find the <phrase>." in place of its own ask sentence."""
    parts = re.split(r"(?<=[.?!])\s+", prior.strip())
    replacement = f"Find the {phrase}."
    if parts and _ASK_SENTENCE.search(parts[-1]):
        parts[-1] = replacement
        return " ".join(parts)
    return prior.rstrip(".?! ") + ". " + replacement


def given_name(name: str) -> str:
    """The quantity a changed given names, without "the", "its", "final" and the like."""
    return " ".join(_NAME_FILLER.sub(" ", name).split())


# "the same braking", "same acceleration": the words that may name a quantity kept.
_SAME = re.compile(r"\bsame (?=[a-z])", re.IGNORECASE)
# A line that takes up the problem before it: "and if…", "what about…", "with…instead".
_CONTINUES = re.compile(
    r"(?:(?:ok(?:ay)?|so|now|then)[ ,]+)*"
    r"(?:and|but|what about|how about|what if|if|with|try|suppose|say|now|then)\b",
    re.IGNORECASE,
)


def continues(line: str) -> bool:
    """True when the line reads as taking up the problem before it: it opens as a
    follow-up does, says something stays the same, or ends "instead". A remark that only
    holds a number ("my car weighs 1500 kg lol") does not."""
    stripped = line.strip()
    return (
        _CONTINUES.match(stripped) is not None
        or _SAME.search(stripped) is not None
        or stripped.lower().rstrip(" ?.!").endswith(" instead")
    )


# Words that make a value an addition or a difference, not the new value of a given:
# "add another 4 ohm in series", "10 m/s faster", "heavier by 2 kg", "twice the mass".
_RELATIVE = re.compile(
    r"\b(?:add(?:s|ed|ing)?|another|more|less|fewer|extra|plus|minus|also|second|third"
    r"|series|parallel|together|combined|each|by|increase[sd]?|decrease[sd]?|than"
    r"|faster|slower|heavier|lighter|higher|lower|longer|shorter|bigger|smaller|larger"
    r"|double[sd]?|triple[sd]?|half|halved?|twice|times)\b",
    re.IGNORECASE,
)


def changes_relatively(line: str) -> bool:
    """True when the line's value adds to the setup or differs from a given rather than
    replacing it: "now add another 4 ohm in series" is 8 Ω, not the 4 Ω again."""
    return _RELATIVE.search(line) is not None


# A word that only introduces a value ("stops in 4 s"), left behind when the value goes.
_INTRODUCER = re.compile(r"(?:in|after|for|within|over|at|of|from|to|with|by)[ \t]+$")


def same_quantities(line: str, names: Mapping[str, object]) -> list[str]:
    """The quantity names a line says stay the same, read longest first from ``names``:
    "with the same braking" → ``["braking"]``. Words no name begins are not a quantity."""
    found: list[str] = []
    lower = line.lower()
    for match in _SAME.finditer(lower):
        # Each "same" reads its own words: "the same acceleration and the same time".
        rest = " ".join(re.findall(r"[a-z]+", lower[match.end() : match.end() + 40]))
        best = max(
            (name for name in names if rest == name or rest.startswith(name + " ")),
            key=len,
            default=None,
        )
        if best is not None:
            found.append(best)
    return found


def remove_given(text: str, given: Given) -> str:
    """The text without one given: its value, the unit after it and the word that
    introduced it ("stops in 4 s." → "stops.")."""
    end = given.end
    old_unit = re.match(r"[ \t]*" + re.escape(given.unit), text[end:], re.IGNORECASE)
    if old_unit is not None:
        end += old_unit.end()
    head = text[: given.start]
    introducer = _INTRODUCER.search(head)
    if introducer is not None:
        head = head[: introducer.start()]
    return " ".join((head.rstrip() + text[end:]).split()).replace(" .", ".").replace(" ,", ",")


def with_sentences(prior: str, *, ask: str | None, stated: tuple[str, ...]) -> str:
    """The prior problem with sentences ``stated`` before its ask, and ``ask`` in place of
    its ask sentence when given."""
    parts = re.split(r"(?<=[.?!])\s+", prior.strip())
    has_ask = bool(parts) and _ASK_SENTENCE.search(parts[-1]) is not None
    setup = parts[:-1] if has_ask else parts
    question = ask if ask is not None else (parts[-1] if has_ask else "")
    body = " ".join(_sentence(part) for part in setup if part.strip())
    return " ".join(filter(None, (body, *stated, question.strip()))).strip()


def _sentence(part: str) -> str:
    """One sentence ending in its own stop: "…by 10 °C?" stays, "(c=4.18)" gains a "."."""
    part = part.strip()
    return part if part.endswith(("?", "!")) else part.rstrip(".") + "."


def replace_given(text: str, given: Given, value: str, unit: str) -> str:
    """The text with one given, and the unit written after it, replaced."""
    end = given.end
    tail = text[end:]
    old_unit = re.match(r"[ \t]*" + re.escape(given.unit), tail, re.IGNORECASE)
    if old_unit is not None:
        end += old_unit.end()
    return text[: given.start] + f"{value} {unit}" + text[end:]


# A number that names an item, not a value: "Solve 1", "question 9", "part 2", "Q3".
_ITEM = re.compile(
    r"\b(?:solve|question|problem|part|number|no\.?|item|exercise|example|q)[ \t]*#?[ \t]*$",
    re.IGNORECASE,
)
# A number assigned to a symbol: "n = 2", "μ = 0", "N = 300", "k=4".
_ASSIGNED = re.compile(r"(?<![\w])[^\W\d_][\w']{0,3}[ \t]*=[ \t]*$")


def item_number(text: str, start: int, end: int) -> bool:
    """The number at ``start:end`` names an item ("Solve 1", "question 9"), not a value: a
    number standing alone after an item word, never a term ("Solve 2x + 3 = 7")."""
    if text[end : end + 1].isalpha() or text[end : end + 1] in ("(", "^"):
        return False
    return _ITEM.search(text, max(0, start - 24), start) is not None


_NUMBER = re.compile(r"\d+(?:\.\d+)?")


def stated_numbers(text: str) -> Counter[str]:
    """The numbers ``text`` writes, each as often as it writes it, without its markup and
    never an item's number ("Solve 1"): "3x + 3 = 7" writes 3 twice."""
    plain = without_markup(fold_scientific(text))
    return Counter(
        match.group()
        for match in _NUMBER.finditer(plain)
        if not item_number(plain, match.start(), match.end())
    )


def pure_value(text: str, start: int, end: int) -> bool:
    """The pure number at ``start:end`` is a value of the problem: a decimal ("n = 1.5",
    "0.25") or one assigned to a symbol ("n = 2", "μ = 0"), never an item's number. The
    one rule the follow-up readers and chat's new-value read share."""
    if item_number(text, start, end):
        return False
    return "." in text[start:end] or _ASSIGNED.search(text, max(0, start - 8), start) is not None


def _same_value(one: Given, other: Given) -> bool:
    """One value: the same kind and size, a pure number by its number."""
    if one.dimension != other.dimension:
        return False
    if one.si is not None and other.si is not None:
        return math.isclose(one.si, other.si, rel_tol=1e-9)
    return one.si is None and other.si is None and math.isclose(one.value, other.value)


@dataclass(frozen=True)
class GivenRewriter:
    """One subject's way to replace or scale one given of its previous problem.

    The subject brings its unit table, how it reads a unit's and a quantity name's
    dimension, and the check that a rewritten problem still verifies. A rewrite
    needs exactly one given of the asked kind, changes the text, and verifies.
    """

    units: UnitTable
    unit_dimension: Callable[[str], str | None]
    phrase_dimension: Callable[[str], str | None]
    verifies: Callable[[str], bool]
    # The dimensions a problem asks for, when the subject reads them: a named given of the
    # kind the problem asks for is never certain to be the one the line means.
    asked: Callable[[str], Collection[str]] | None = None
    # Whether the problem's words fit a named quantity: a string's 2 m is no "height".
    fits: Callable[[str, str], bool] | None = None
    # The quantities a problem asks for, by name ("range", "height"): two of one dimension
    # are told apart by it.
    asked_names: Callable[[str], Collection[str]] | None = None

    def changed(self, prior: str, name: str | None, value: str, unit: str | None) -> str | None:
        """``and after 10 s``, ``what if the mass was 4 kg``: that given replaced."""
        prior = fold_scientific(prior)  # "3.0 x 10^-6 C" is one value, read as one
        if not unit or not unit.strip():
            return None
        written_unit = " ".join(unit.split())
        new_dim = self.unit_dimension(written_unit)
        if new_dim is None or not fully_read(prior):
            return None
        if name:
            named_dim = self.phrase_dimension(given_name(name))
            if named_dim is None or named_dim != new_dim or not self._names(prior, name, named_dim):
                return None
        matches = [
            g for g in self._of_dimension(prior, new_dim) if plays_role(prior, g, name or "")
        ]
        kind = self._of_dimension(prior, new_dim)
        if (
            len(matches) != 1
            or counted(prior, matches[0], kind)
            or self._anothers(prior, matches[0])
        ):
            return None
        rewritten = replace_given(prior, matches[0], value, written_unit)
        if rewritten == prior:
            return None
        return rewritten if self.verifies(rewritten) else None

    def replaced(self, prior: str, changes: Sequence[tuple[str | None, str, str]]) -> str | None:
        """Each change ``(written, value, unit)`` puts the given of ``unit``'s kind to
        ``value``: the problem's one given of that kind, or of several the one whose number
        ``written`` quotes ("300 K" of "between 500 K and 300 K"). Every given is found in
        the problem as stated, never in a text another change already edited, so "the
        charges as 2.0 C and 3.0 C" swaps them, and two changes of one given are none.
        Every other given stays as written, and the rewrite verifies."""
        prior = fold_scientific(prior)
        if not changes or not fully_read(prior):
            return None
        targets: list[tuple[Given, str, str]] = []
        for written, value, unit in changes:
            spelled = " ".join(unit.split())
            new_dim = self.unit_dimension(spelled)
            if new_dim is None:
                return None
            kind = self._of_dimension(prior, new_dim)
            matches = kind
            if len(matches) > 1:
                matches = self._quoted(written or "", kind, new_dim)
            if len(matches) != 1 or counted(prior, matches[0], kind):
                return None
            if self._anothers(prior, matches[0]):
                return None
            targets.append((matches[0], value, spelled))
        if len({given.start for given, _value, _unit in targets}) != len(targets):
            return None
        rewritten = prior
        # From the last position back, so each earlier given's position still holds.
        for given, value, unit in sorted(targets, key=lambda t: t[0].start, reverse=True):
            rewritten = replace_given(rewritten, given, value, unit)
        return rewritten if rewritten != prior and self.verifies(rewritten) else None

    def scaled(self, prior: str, scaling: Scaling) -> str | None:
        """``what if the mass doubles``: the one given of that kind, times the factor."""
        prior = fold_scientific(prior)
        reading = scaled_name(prior, scaling, self._is_quantity)
        if reading is None or not fully_read(prior):
            return None
        name, owner = reading
        named_dim = self.phrase_dimension(given_name(name))
        if named_dim is None or not self._names(prior, name, named_dim):
            return None
        matches = [
            g
            for g in self._of_dimension(prior, named_dim)
            if plays_role(prior, g, name) and (owner is None or owns(prior, g, owner, name))
        ]
        if len(matches) != 1:
            return None
        given = matches[0]
        if counted(prior, given, self._of_dimension(prior, named_dim)):
            return None
        if not _scales(prior, given):
            return None
        # "The mass of Earth is 6e24 kg" in a satellite's problem: "the mass" may be either.
        if owner is None and self._anothers(prior, given):
            return None
        if scaling.thrown and not thrown_at(prior, given, scaling.thrown):
            return None
        rewritten = replace_given(
            prior, given, scaled_value(given.value, scaling.factor), given.unit
        )
        return rewritten if rewritten != prior and self.verifies(rewritten) else None

    def restated(self, prior: str, line: str) -> list[Given]:
        """The values ``line`` states of a kind ``prior`` gives: "3.0 pC" after a problem
        with charges, never "question 8" or a power of ten in a bracket."""
        prior, line = fold_scientific(prior), fold_scientific(line)
        kinds = {given.dimension for given in read_givens(prior, self.units) if given.dimension}
        return [given for given in read_givens(line, self.units) if given.dimension in kinds]

    def takes_every(self, prior: str, rewritten: str, line: str, new: Sequence[str]) -> bool:
        """Whether a rewrite made of ``new`` values stands for all of ``line``: every value
        the line states of the problem's kinds is one of them (a read that named one change
        of two would solve with a charge the user never gave), and the line asks nothing of
        its own or what the rewrite asks ("What is the momentum of a 5 kg ball?" is a new
        question, not a change to a kinetic energy problem)."""
        taken = [given for value in new for given in self._values(value)]
        # Every value the line states must be the problem's kind: a quantity the problem
        # lacks ("thrown downward at 10 m/s" after a drop) is another problem, which no
        # rewrite of the old one solves. A pure number counts as a decimal one: "diamond
        # (n = 2.42)" is a change the rewrite must take, never one it drops.
        kinds = {given.dimension for given in self._values(prior)}
        stated_all = self._values(line)
        if any(given.dimension not in kinds for given in stated_all):
            return False
        # One to one: "3.0 pC and 3.0 pC" are two values, which one named change never takes.
        left = list(taken)
        for stated in stated_all:
            match = next((given for given in left if _same_value(given, stated)), None)
            if match is None:
                return False
            left.remove(match)
        if self.asked is None:
            return True
        asked = set(self.asked(line))
        if asked and asked != set(self.asked(rewritten)):
            return False
        # A new ask of the same dimension: "find the maximum height" after "find its
        # range" is no rewrite that still asks for the range.
        return self._asks_the_same(line, rewritten)

    def _asks_the_same(self, line: str, rewritten: str) -> bool:
        """Every quantity ``line`` asks for by name is one ``rewritten`` asks for."""
        if self.asked_names is None:
            return True
        theirs = [name.lower() for name in self.asked_names(rewritten)]
        return all(
            any(mine in name or name in mine for name in theirs)
            for mine in (name.lower() for name in self.asked_names(line))
        )

    def states_new(self, prior: str, line: str) -> bool:
        """``line`` states a value ``prior`` does not, read with its unit: "20 minutes" after
        "20 seconds" is new, "Solve 1" names an item and states nothing."""
        stated = self._values(prior)
        return any(
            not any(_same_value(given, old) for old in stated) for given in self._values(line)
        )

    def _values(self, text: str) -> list[Given]:
        """The values ``text`` states: each with its unit, and each pure number that is a
        value (``pure_value``: an index, a coefficient, "n = 2"); never a count or an
        item's number."""
        # Scientific notation folded first, before markup comes off ("$2 \\times 10^{-6}$"
        # loses its caret and braces), so "2 x 10^-6 C" is one value, in any spelling;
        # "$T_C = 200\\,\\mathrm{K}$" is 200 K.
        plain = without_markup(fold_scientific(text))
        return [
            given
            for given in read_givens(plain, self.units)
            if given.dimension is not None or pure_value(plain, given.start, given.end)
        ]

    def _quoted(self, written: str, kind: list[Given], dimension: str) -> list[Given]:
        """The givens of ``kind`` ``written`` quotes: by size when it carries a unit of that
        kind ("3.0 μC" of "3.0 μC and 3.0 nC"), by its number when it carries none."""
        written = fold_scientific(written)
        sized = [g.si for g in read_givens(written, self.units) if g.dimension == dimension]
        if sized:
            return [
                given
                for given in kind
                if given.si is not None
                and any(si is not None and math.isclose(given.si, si) for si in sized)
            ]
        quoted = _quoted_numbers(written)
        return [given for given in kind if given.value in quoted]

    def _names(self, prior: str, name: str, dimension: str) -> bool:
        """False when ``name`` may not be a given of ``prior``: the problem asks for that
        kind ("the distance doubled" after "how far does it land?"), or its words do not
        fit the name (a string's 2 m is no height)."""
        if self.asked is not None and dimension in self.asked(prior):
            return False
        return self.fits is None or self.fits(prior, name)

    def _anothers(self, prior: str, given: Given) -> bool:
        """True when the problem writes a mass, speed or charge (what every body has) as a
        body's that is not its subject: "the mass" of a satellite's problem that gives
        Earth's may be either body's."""
        if given.dimension not in {self.phrase_dimension(n) for n in _EVERY_BODYS}:
            return False
        owner = written_owner(prior, given, self._is_quantity)
        subject = subject_of(prior, self._is_quantity)
        return owner is not None and subject is not None and owner != subject

    def _is_quantity(self, name: str) -> bool:
        return self.phrase_dimension(given_name(name)) is not None

    def _of_dimension(self, prior: str, dimension: str) -> list[Given]:
        return [given for given in read_givens(prior, self.units) if given.dimension == dimension]


# A value written in words ("dropped from ten metres") is one no reading counts: a
# problem with one may have more givens of a kind than the reader sees.
_SPELLED_VALUE = re.compile(
    r"\b(?:one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|fifteen|twenty"
    r"|thirty|forty|fifty|hundred|thousand) (?:(?:kilo|centi|milli)?met(?:re|er)s?|seconds?"
    r"|minutes?|hours?|(?:kilo)?grams?|newtons?|joules?|volts?|amps?|ohms?|lit(?:re|er)s?"
    r"|moles?|degrees?|kelvins?)\b",
    re.IGNORECASE,
)


def fully_read(prior: str) -> bool:
    """False when the problem states a value in words the reader does not count."""
    return _SPELLED_VALUE.search(prior) is None


_KELVIN = frozenset({"k", "kelvin", "kelvins"})
# What every body has, so "the mass" of a two-body problem may be either's.
_EVERY_BODYS = ("mass", "speed", "charge")
_CHANGE = re.compile(r"\b(?:by|change of|rise of|increase of|drop of|fall of)[ \t]*$", re.I)


def _scales(prior: str, given: Given) -> bool:
    """False for a temperature on a scale with no true zero: 27 °C doubled is not 54 °C.
    Kelvin scales, and so does a change ("raised by 10 °C")."""
    if "temperature" not in (given.dimension or "") or given.unit.lower() in _KELVIN:
        return True
    return _CHANGE.search(prior[: given.start]) is not None
