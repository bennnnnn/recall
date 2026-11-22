"""A worked solution fitted to the question it answers: its parts are the question's own.

The model's records do not always say where each part starts, and the layout's parts came
out unlike the question's (hard geometry round, 2026-11-21):

- "a) The altitude. b) The lengths of both legs. c) The area" was laid out (a) to (d), a leg
  a part;
- with no ``part`` record, the block came apart at every new formula: an exterior angle
  worked first went under "(a) Number of sides", a semi-perimeter under "(a) Area" with the
  area itself under "(b) Inradius";
- "Find the lengths of all three sides" asks one thing and got two invented parts;
- three formulas written before the first ``part`` record all stood under (a).

Once the block is whole (never while it streams: a part drawn must not move), the solution
is fitted:

1. A block with no ``part`` record whose asks each name a symbol of their own is split by
   what each line works out: a line setting an asked symbol, or an answer naming one, is
   that ask's, and a line setting anything else (a semi-perimeter, a slope) goes with the
   next line that sets an asked one (``_by_symbol``).
2. Formulas written together before the first ``part`` record go to the parts whose
   working uses them, else in order, one to each part (``_formulas_placed``).
3. A part with no answer of its own is working toward the next one, and joins it.
4. Parts the question asks as one (both legs, one part) are joined to the question's own
   parts, each run of the model's parts to the question part its words match best, in
   order (``_aligned``).
5. A question with no lettered parts that comes out as one part is laid out whole.

A joined part keeps each formula and its substitution under its own heading, as stages
under the part's one heading, closed by every answer it holds (``Part.then``).
"""

from __future__ import annotations

import re
from collections.abc import Sequence

from app.modules.chat.worked_solution import (
    MAX_PARTS,
    Answer,
    Formula,
    Part,
    PartLabel,
    RecordModel,
    Required,
    Step,
    WorkedSolution,
    assemble,
)
from app.modules.chat.worked_text import names_nothing, tidy_symbol

_WRAPPER = re.compile(
    r"\\(?:text|mathrm|mathcal|mathbf|mathit|operatorname|boldsymbol|vec|overline|bar|hat)\s*"
)
_POWER_AT_END = re.compile(r"\^\s*(?:\{[^{}]*\}|\\circ|\w)\s*$")
_LOOSE = re.compile(r"[\s{}$]")
_WORD = re.compile(r"[a-z]{3,}")
_STOP = frozenset(
    "the and its their for from with that this find what which each both all value values "
    "length lengths".split()
)


def _key(tex: str) -> str:
    """A symbol as one key however it is written: ``A_{\\text{tri}}`` and ``A_tri`` alike,
    ``h^2`` as ``h``."""
    side = _WRAPPER.sub("", tex.split("=", 1)[0]).strip()
    return _LOOSE.sub("", _POWER_AT_END.sub("", side))


def _ask_keys(asks: Sequence[Required]) -> list[frozenset[str]] | None:
    """Each ask's symbols as keys ("R, h" is two), or None when an ask names none or two asks
    share one: lines can then be told apart by what they set."""
    keys = [
        frozenset(_key(tidy_symbol(piece)) for piece in ask.symbol.split(",") if piece.strip())
        for ask in asks
    ]
    every = [key for group in keys for key in group]
    if any(not group or "" in group for group in keys) or len(every) != len(set(every)):
        return None
    return keys


def _owner(record: RecordModel, keys: Sequence[frozenset[str]]) -> int | None:
    """The ask a line or answer works out, by the symbol it sets or names."""
    if isinstance(record, Answer):
        named = {_key(tidy_symbol(piece)) for piece in record.symbol.split(",") if piece.strip()}
    elif isinstance(record, Formula) or (isinstance(record, Step) and record.kind != "say"):
        named = {_key(record.tex)} if "=" in record.tex else set()
    else:
        return None
    owners = [at for at, group in enumerate(keys) if named and named <= group]
    return owners[0] if len(owners) == 1 else None


class _Group:
    """One ask's records: its stages, each opened by a formula, and its answers."""

    def __init__(self) -> None:
        self.stages: list[list[Formula | Step]] = [[]]
        self.answers: list[Answer] = []
        self.lines = 0

    def add(self, record: Formula | Step | Answer, *, own: bool = False) -> None:
        if isinstance(record, Answer):
            self.answers.append(record)
            return
        self.lines += own
        stage = self.stages[-1]
        if isinstance(record, Formula) and any(
            isinstance(line, Step) and line.kind == "substitution" for line in stage
        ):
            self.stages.append([record])
        else:
            stage.append(record)

    def part(self, title: str) -> Part:
        built = [_stage(lines) for lines in self.stages if lines]
        first = built[0] if built else Part()
        return first.model_copy(
            update={"title": title, "answers": tuple(self.answers), "then": tuple(built[1:])}
        )


def _stage(lines: Sequence[Formula | Step]) -> Part:
    formula = lines[0] if isinstance(lines[0], Formula) else None
    working = [
        line if isinstance(line, Step) else Step(kind="step", tex=line.tex, move=line.name)
        for line in (lines[1:] if formula is not None else lines)
    ]
    return Part(formula=formula, working=tuple(working))


def _by_symbol(records: Sequence[RecordModel], solution: WorkedSolution) -> WorkedSolution | None:
    """The block split by what each line works out (module docstring, 1), or None when the
    asks cannot be told apart or one of them has no line of its own."""
    asks = list(solution.required)
    keys = _ask_keys(asks) if 2 <= len(asks) <= MAX_PARTS else None
    if keys is None:
        return None
    groups = [_Group() for _ask in asks]
    pending: list[Formula | Step] = []
    current: int | None = None
    for record in records:
        if not isinstance(record, Formula | Step | Answer):
            continue
        owner = _owner(record, keys)
        if owner is None and isinstance(record, Answer):
            owner = current if current is not None else 0
        if owner is None:
            if not isinstance(record, Answer):
                pending.append(record)
            continue
        for line in pending:
            groups[owner].add(line)
        pending.clear()
        groups[owner].add(record, own=True)
        current = owner if not isinstance(record, Answer) else current
    if current is None or not all(group.lines for group in groups):
        return None
    for line in pending:
        groups[current].add(line)
    parts = tuple(group.part(ask.meaning) for group, ask in zip(groups, asks, strict=True))
    return solution.model_copy(update={"parts": parts, "in_parts": True})


def _formulas_placed(records: Sequence[RecordModel]) -> list[RecordModel]:
    """The records with each formula written before the first ``part`` record moved to the
    part whose working sets its symbol, else, when there is one such formula for each part,
    to the part of its place (module docstring, 2)."""
    labels = [at for at, record in enumerate(records) if isinstance(record, PartLabel)]
    if not labels:
        return list(records)
    early = [at for at in range(labels[0]) if isinstance(records[at], Formula)]
    if len(early) < 2:
        return list(records)
    ends = [*labels[1:], len(records)]
    sets = [
        {
            _key(record.tex)
            for record in records[start:end]
            if isinstance(record, Step | Formula) and "=" in record.tex
        }
        for start, end in zip(labels, ends, strict=True)
    ]
    # By place only when no later part has a formula of its own: then they were the parts'.
    by_place = len(early) == len(labels) and not any(
        isinstance(record, Formula) for record in records[labels[1] if len(labels) > 1 else 0 :]
    )
    target: dict[int, int] = {}
    for place, at in enumerate(early):
        formula = records[at]
        if not isinstance(formula, Formula):
            continue
        owner = next((index for index, set_ in enumerate(sets) if _key(formula.tex) in set_), None)
        if owner is None and by_place:
            owner = place
        if owner is not None:
            target[at] = owner
    if not target:
        return list(records)
    out: list[RecordModel] = []
    for at, record in enumerate(records):
        if at in target:
            continue
        out.append(record)
        if isinstance(record, PartLabel):
            index = labels.index(at)
            out.extend(records[early_at] for early_at, owner in target.items() if owner == index)
    return out


def _joined(parts: Sequence[Part], title: str | None = None) -> Part:
    """Parts as one: the first's heading, every part's working as its stages, every answer."""
    first = parts[0]
    stages: list[Part] = []
    for part in parts[1:]:
        stages.append(part.model_copy(update={"answers": (), "then": (), "given": ()}))
        stages.extend(part.then)
    return first.model_copy(
        update={
            "title": first.title if title is None else title,
            "given": tuple(given for part in parts for given in part.given),
            "answers": tuple(answer for part in parts for answer in part.answers),
            "then": (*first.then, *stages),
        }
    )


def _answered_only(parts: Sequence[Part], want: int) -> list[Part]:
    """Each part with no answer joined to the next part, while there are more parts than
    the question has (module docstring, 3)."""
    out: list[Part] = []
    waiting: list[Part] = []
    for index, part in enumerate(parts):
        rest = len(parts) - index - 1
        if not part.answers and rest and len(out) + len(waiting) + rest >= max(want, 1):
            waiting.append(part)
            continue
        out.append(_joined([*waiting, part]) if waiting else part)
        waiting = []
    return out


def _words(text: str) -> set[str]:
    return {word.rstrip("s") for word in _WORD.findall(text.lower()) if word not in _STOP}


def _described(part: Part, asks: Sequence[Required]) -> set[str]:
    """The words that say what a part finds: its title, and what its answers' symbols ask."""
    named = {_key(tidy_symbol(answer.symbol)) for answer in part.answers if answer.symbol}
    meanings = [ask.meaning for ask in asks if _key(tidy_symbol(ask.symbol)) in named]
    return _words(" ".join([part.title, *meanings]))


def _runs(scores: list[list[int]], count: int, want: int) -> list[tuple[int, int]]:
    """The split of ``count`` parts, in order, into ``want`` runs of one or more, that
    matches each run to its question part best (``scores[part][question part]``); ties go
    to the earlier split."""
    best: dict[tuple[int, int], tuple[int, list[tuple[int, int]]]] = {(0, 0): (0, [])}
    for done in range(1, want + 1):
        for end in range(done, count - (want - done) + 1):
            options = [
                (
                    best[(start, done - 1)][0]
                    + sum(scores[at][done - 1] for at in range(start, end)),
                    [*best[(start, done - 1)][1], (start, end)],
                )
                for start in range(done - 1, end)
                if (start, done - 1) in best
            ]
            if options:
                best[(end, done)] = max(options, key=lambda option: option[0])
    return best[(count, want)][1]


def _title(words: str) -> str:
    """A question part's words as its heading: "The lengths of both legs." → "lengths of
    both legs"."""
    text = " ".join(words.split()).rstrip(" .?;:")
    text = re.sub(r"^(?:the|its|their|find|calculate|determine)\s+", "", text, flags=re.I)
    return text[:1].lower() + text[1:] if text[1:2].islower() else text


def _aligned(solution: WorkedSolution, asked: Sequence[str]) -> WorkedSolution:
    """The model's parts joined into the question's (module docstring, 4)."""
    parts = list(solution.parts)
    scores = [
        [len(_described(part, solution.required) & _words(words)) for words in asked]
        for part in parts
    ]
    joined: list[Part] = []
    for (start, end), words in zip(_runs(scores, len(parts), len(asked)), asked, strict=True):
        run = parts[start:end]
        joined.append(run[0] if len(run) == 1 else _joined(run, _title(words)))
    return solution.model_copy(
        update={"parts": tuple(joined), "required": _asks_of(joined, solution.required)}
    )


def _asked_for(part: Part, asks: Sequence[Required]) -> Required | None:
    """What a part finds, as Required names it: the ask its answer names, else its answers'
    symbols under its title; None when its answers name no symbol."""
    named = {_key(tidy_symbol(answer.symbol)) for answer in part.answers if answer.symbol}
    own = [ask for ask in asks if _key(tidy_symbol(ask.symbol)) in named]
    if len(own) == 1:
        return own[0]
    symbols = ", ".join(dict.fromkeys(answer.symbol for answer in part.answers if answer.symbol))
    return Required(symbol=symbols, meaning=part.title) if symbols else None


def _asks_of(parts: Sequence[Part], asks: Sequence[Required]) -> tuple[Required, ...]:
    """What is asked, one line for each part once parts were joined; the asks as written
    when a part's line cannot be named (its answers name no symbol)."""
    lines = [_asked_for(part, asks) for part in parts]
    return tuple(asks) if any(line is None for line in lines) else tuple(filter(None, lines))


def plain_notes(records: Sequence[RecordModel]) -> list[RecordModel]:
    """The records with each answer's note that only names what the value is left out
    (``_label_only``), while the block streams too, so the card drawn never changes: the
    names it is read against are the ``required`` and ``part`` records before it."""
    named: set[str] = set()
    out: list[RecordModel] = []
    for record in records:
        if isinstance(record, Required | PartLabel):
            words = record.meaning if isinstance(record, Required) else record.title
            named |= set(_NOTE_WORD.findall(f"{words} {getattr(record, 'symbol', '')}".lower()))
        elif isinstance(record, Answer) and _label_only(record.note, named | {record.symbol}):
            record = record.model_copy(update={"note": ""})
        out.append(record)
    return out


def fitted(records: Sequence[RecordModel], asked: Sequence[str] = ()) -> WorkedSolution:
    """The block's records as one solution whose parts are the question's (module
    docstring). ``asked``: the question's lettered parts, each one's words."""
    labelled = any(isinstance(record, PartLabel) for record in records)
    records = plain_notes(records)
    placed = _formulas_placed(records) if labelled else list(records)
    solution = assemble(placed)
    if not labelled:
        solution = _by_symbol(records, solution) or solution
    solution = worked_givens(solution)
    if not solution.in_parts or len(solution.parts) < 2:
        return _whole(_notes_untold(solution), asked)
    want = len(asked) if len(asked) >= 2 else 0
    before = len(solution.parts)
    parts = _answered_only(solution.parts, want)
    if len(parts) != before:
        solution = solution.model_copy(
            update={"parts": tuple(parts), "required": _asks_of(parts, solution.required)}
        )
    if want and len(solution.parts) > want:
        solution = _aligned(solution, asked)
    return _whole(_notes_untold(solution), asked)


_TOKEN = re.compile(r"[A-Za-z]+|\d+(?:\.\d+)?")
_NUMBER = re.compile(r"\d+(?:\.\d+)?")
# A quantity in powers of ten, "3 \times 10^8": one value, given as data.
_SCIENTIFIC = re.compile(r"^-?\d+(?:\.\d+)?\s*(?:\\times|\\cdot|x)\s*10\^\{?-?\d+\}?$")


def _worked_out(value: str) -> bool:
    """A value still to work out, "\\frac{1}{3}\\pi(4)^2(8)": three numbers or more in a sum
    (never a power of ten, a point, or a fraction a question states)."""
    text = value.strip()
    letters = _COMMANDS.sub(" ", text)
    return (
        len(_NUMBER.findall(text)) >= 3
        and _OPERATION.search(text) is not None
        # A variable makes it an expression the question gives (an integral to evaluate).
        and not re.search(r"[A-Za-z]", letters)
        and not _SCIENTIFIC.match(text)
        and "," not in text
        and not _RELATION.search(text)
    )


_RELATION = re.compile(r"=|[<>≤≥]")
_COMMANDS = re.compile(r"\\[A-Za-z]+|\\.")
# Arithmetic still to do: a sign between terms, a product, a fraction, a root, a power.
_OPERATION = re.compile(r"\S\s*[-+\u00d7\u00f7*/]\s*\S|\\(?:times|cdot|div|frac|sqrt)|\^|\)\s*\(")


def _as_maths(symbol: str) -> str:
    """A symbol written in words ("V large cone volume") set upright as words."""
    return rf"\text{{{symbol}}}" if names_nothing(symbol) else symbol


def worked_givens(solution: WorkedSolution) -> WorkedSolution:
    """Givens whose value is working (the small cone's volume, $\\frac{1}{3}\\pi(4)^2(8)$):
    a given is data, so each is a line at the start of the working, never a row of Given
    (hard geometry round, 2026-11-21). While the block streams and no part has begun, it
    waits: the first part opens with it, so nothing drawn moves."""
    worked = [given for given in solution.given if given.value and _worked_out(given.value)]
    if not worked:
        return solution
    lines = tuple(
        Step(kind="substitution", tex=f"{_as_maths(given.symbol)} = {given.value}")
        for given in worked
    )
    parts = list(solution.parts)
    if parts:
        parts[0] = parts[0].model_copy(update={"working": (*lines, *parts[0].working)})
    return solution.model_copy(
        update={
            "given": tuple(given for given in solution.given if given not in worked),
            "parts": tuple(parts),
        }
    )


def _notes_untold(solution: WorkedSolution) -> WorkedSolution:
    """Each answer without a note that says only what its part is called ("tangent at
    (8,1)" under "(c) Tangent at (8, 1)"): Required and the part's heading say it."""
    named = {
        token.lower()
        for text in [
            *(ask.meaning for ask in solution.required),
            *(p.title for p in solution.parts),
        ]
        for token in _TOKEN.findall(text)
    }

    def untold(answer: Answer) -> Answer:
        tokens = {token.lower() for token in _TOKEN.findall(answer.note)}
        return answer.model_copy(update={"note": ""}) if tokens and tokens <= named else answer

    parts = tuple(
        part.model_copy(update={"answers": tuple(untold(answer) for answer in part.answers)})
        for part in solution.parts
    )
    return solution.model_copy(update={"parts": parts})


def _whole(solution: WorkedSolution, asked: Sequence[str]) -> WorkedSolution:
    """A question with no lettered parts that comes out as one part: laid out whole, with no
    letter (module docstring, 5)."""
    if len(asked) >= 2 or len(solution.parts) != 1 or not solution.labelled:
        return solution
    part = solution.parts[0].model_copy(update={"letter": "", "title": ""})
    return solution.model_copy(update={"parts": (part,), "in_parts": False})


# Words that name a value without saying anything of it: "exact value", "possible values".
_NAMING = frozenset(
    "exact value values possible final answer result results numerical numeric number the of "
    "a an its each all total in and both required asked".split()
)
_NOTE_WORD = re.compile(r"[A-Za-z]+")


def _label_only(note: str, named: set[str]) -> bool:
    """A note that only names what the value is ("length", "exact value", "each exterior
    angle", "possible values"): its words are what Required and the part's label say
    (``named``), or words that name any value. On the card it was a caption in brackets,
    or a line of its own under it (hard geometry round, 2026-11-21). A note with words of
    its own says something of the value ("attractive", "upright and diminished", "east"),
    and one with a number or maths in it more still: both stay."""
    words = note.strip()
    if not words or any(char.isdigit() or char in "$\\^_=" for char in words):
        return False
    said = {_stem(word) for word in _NOTE_WORD.findall(words.lower())}
    return bool(said) and said <= {_stem(word) for word in named} | set(_NAMING)


def _stem(word: str) -> str:
    return word.lower().removesuffix("s")
