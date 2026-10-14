"""Run STEM homework questions through the real chat path and judge the replies.

Each subject has a corpus in ``stem_corpus/<subject>/*.json``. An entry is a
question a student would type, worked independently from the textbook formula
(g = 9.81 m/s², CODATA constants), and what should happen:

- ``answer``: a verified reply whose answer card holds ``answer`` = [value, unit]
  (1% tolerance, any unit of the same kind; signs are compared as magnitudes);
- ``explain``: a question without numbers, left to the model, never "solved";
- ``decline``: an underdetermined question, never given a number;
- ``not_subject``: an everyday message that only sounds like the subject.

Every verified reply is also checked for its shape (Given, Find, Formula,
Substitution, Answer; no calculator notation; no invented zero given), and
every picture it carries is validated: a ``simulation`` scene against the
server schema and its own bounds, a ``graph`` for finite points. ``visual``
names the picture a student would want, and is counted, not required.

A problem is ``critical`` (a wrong number, a misread turn, a broken picture)
or ``coverage`` (a question declined or not recognised, a picture missing). The test fails on
the first kind; the second is held by floors that only go up.

    uv run python -m app.tests.behavior.stem_sweep physics --show
"""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import re
import sys
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

import pint

from app.modules.physics.schemas.simulation import SimulationBlockSpec
from app.tests.behavior.harness import Case, Expect, Route, route_case

CORPUS = Path(__file__).with_name("stem_corpus")
EXPECTS = {"answer", "explain", "decline", "not_subject"}
SUBJECT_NAMES = {"physics": "physics", "chemistry": "chemistry", "math": "math"}
TOLERANCE = 0.01
CRITICAL = {"wrong", "misread", "shape", "broken_visual"}

_UNITS = pint.UnitRegistry()
_UNITS.define("diopter = 1 / meter = D")
_UNITS.define("kWh = kilowatt * hour")


@dataclass(frozen=True)
class Entry:
    id: str
    area: str
    prompt: str
    expect: str
    answer: tuple[float, str] | None = None
    visual: str | None = None
    note: str | None = None
    gap: str | None = None


@dataclass
class Problem:
    kind: str
    text: str

    @property
    def critical(self) -> bool:
        return self.kind in CRITICAL


@dataclass
class Outcome:
    entry: Entry
    route: Route | None = None
    reply: str = ""
    got: str = ""
    visuals: list[str] = field(default_factory=list)
    problems: list[Problem] = field(default_factory=list)

    @property
    def critical(self) -> list[Problem]:
        return [problem for problem in self.problems if problem.critical]


def load(subject: str) -> list[Entry]:
    entries: list[Entry] = []
    for path in sorted((CORPUS / subject).glob("*.json")):
        for raw in json.loads(path.read_text()):
            answer = raw.get("answer")
            entries.append(
                Entry(
                    id=raw["id"],
                    area=raw["area"],
                    prompt=raw["prompt"],
                    expect="not_subject" if raw["expect"].startswith("not_") else raw["expect"],
                    answer=(float(answer[0]), str(answer[1])) if answer else None,
                    visual=raw.get("visual"),
                    note=raw.get("note"),
                    gap=raw.get("gap"),
                )
            )
    return entries


# --- reading the reply -------------------------------------------------------

_FENCE = re.compile(r"```([\w-]+)[ \t]*\n(.*?)\n?```", re.DOTALL)
_SUPER = str.maketrans("⁰¹²³⁴⁵⁶⁷⁸⁹⁻", "0123456789-")


def fences(reply: str) -> list[tuple[str, str]]:
    return [(lang.lower(), body.strip()) for lang, body in _FENCE.findall(reply)]


def latex_to_plain(latex: str) -> str:
    """``3.97 \\times 10^{-19}\\,\\mathrm{J}`` → ``3.97e-19 J``."""
    text = latex.strip().strip("$")
    text = re.sub(r"\\mathrm\{([^{}]*)\}", r"\1", text)
    text = re.sub(r"\\text\{([^{}]*)\}", r"\1", text)
    text = re.sub(r"\s*\\times\s*10\^\{?(-?\d+)\}?", r"e\1", text)
    text = re.sub(r"\s*×\s*10([⁰¹²³⁴⁵⁶⁷⁸⁹⁻]+)", lambda m: "e" + m.group(1).translate(_SUPER), text)
    text = text.replace("^\\circ", " deg").replace("^{\\circ}", " deg").replace("°", " deg ")
    text = (
        text.replace("\\,", " ").replace("\\ ", " ").replace("\\%", "%").replace("\\Omega", "ohm")
    )
    text = text.replace("{", "").replace("}", "").replace("\\", "")
    return " ".join(text.split())


_NUMBER = re.compile(r"^\s*(-?\d+(?:\.\d+)?(?:e-?\d+)?)\s*(.*)$")


def read_answers(reply: str) -> list[tuple[float, str]]:
    """Each value and unit on the reply's answer card.

    One card can hold several results: "2.45 m/s² and 36.8 N",
    "50.0 N at 53.1°", "0 m/s and 4 m/s".
    """
    body = next((text for lang, text in fences(reply) if lang == "answer"), None)
    if body is None:
        return []
    found: list[tuple[float, str]] = []
    for line in body.splitlines():
        plain = latex_to_plain(line)
        for part in re.split(r"\s+(?:and|at)\s+|;|,\s+(?=[a-zA-Z\\]*\s*=)", plain):
            part = re.sub(r"^[^\d-]*=\s*", "", part.strip())  # "R = 62.7 m"
            match = _NUMBER.match(part)
            if match:
                unit = re.split(r"\s\(|,", match.group(2))[0].strip()
                found.append((float(match.group(1)), unit))
    return found


def read_answer(reply: str) -> tuple[float, str] | None:
    answers = read_answers(reply)
    return answers[0] if answers else None


def _pint_unit(unit: str) -> str:
    text = unit.strip()
    if not text:
        return "dimensionless"
    text = text.replace("²", "2").replace("³", "3")
    text = re.sub(r"\^?(\d)\b", r"**\1", text)
    text = text.replace("·", "*").replace("Ω", "ohm").replace("µ", "u").replace("μ", "u")
    text = re.sub(r"\bdeg\s*C\b|\bdegC\b", "degC", text)
    text = re.sub(r"\bdeg\b", "degree", text)
    return text.replace("%", "percent")


def same_quantity(got: tuple[float, str], want: tuple[float, str]) -> tuple[bool, str]:
    value, unit = got
    want_value, want_unit = want
    if want_unit == "dB" or unit == "dB":
        converted = value if unit == want_unit else math.nan
    else:
        try:
            quantity = _UNITS.Quantity(abs(value), _pint_unit(unit))
            converted = quantity.to(_pint_unit(want_unit)).magnitude
        except Exception as exc:  # A unit that does not convert is a wrong answer.
            return (
                False,
                f"{value} {unit} is not a {want_unit or 'pure number'} ({exc.__class__.__name__})",
            )
    target = abs(want_value)
    ok = math.isclose(abs(converted), target, rel_tol=TOLERANCE, abs_tol=1e-12)
    return ok, f"{value:g} {unit} = {converted:.4g} {want_unit}, want {target:.4g}"


# --- judging -------------------------------------------------------------------

_SECTIONS = ("**Given**", "**Find**", "**Formula**", "**Substitution**", "**Answer**")
_CALCULATOR = re.compile(r"\d(?:\.\d+)?[eE][-+]?\d")
_GIVEN_ROW = re.compile(r"^\$([^$=]+?)\s*=\s*0(?:\.0+)?(?:\\,|\s|\$)", re.MULTILINE)
_ZERO_WORDS = re.compile(
    r"\b(?:rest|stops?|stopped|dropp?ed|drops?|stationary|horizontal(?:ly)?|frictionless|"
    r"smooth|still|zero|falls?|released?|starting|starts|stopping|brakes?|braking|halts?)\b|\b0\b",
    re.IGNORECASE,
)


def _prose(reply: str) -> str:
    return _FENCE.sub("", reply)


def check_shape(entry: Entry, reply: str) -> list[Problem]:
    problems: list[Problem] = []
    prose = _prose(reply)
    positions = [prose.find(section) for section in _SECTIONS]
    missing = [name.strip("*") for name, at in zip(_SECTIONS, positions, strict=True) if at < 0]
    if missing:
        problems.append(Problem("shape", f"reply has no {', '.join(missing)}"))
    elif positions != sorted(positions):
        problems.append(Problem("shape", "sections out of order"))
    if calculator := _CALCULATOR.search(prose):
        problems.append(Problem("shape", f"calculator notation: {calculator.group(0)!r}"))
    if re.search(r"\b(?:nan|inf|None)\b", prose):
        problems.append(Problem("shape", "nan, inf or None in the reply"))
    given = prose.split("**Find**")[0]
    for symbol in _GIVEN_ROW.findall(given):
        if not _ZERO_WORDS.search(entry.prompt):
            problems.append(Problem("shape", f"invented a zero given: {symbol.strip()} = 0"))
    return problems


def _in_bounds(point: list[float], spec: SimulationBlockSpec, slack: float) -> bool:
    x, y = point
    return (
        spec.x_min - slack <= x <= spec.x_max + slack
        and spec.y_min - slack <= y <= spec.y_max + slack
    )


def check_visuals(reply: str) -> tuple[list[str], list[Problem]]:
    kinds: list[str] = []
    problems: list[Problem] = []
    for lang, body in fences(reply):
        if lang not in {"simulation", "graph"}:
            continue
        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            problems.append(Problem("broken_visual", f"{lang} fence is not JSON"))
            continue
        if lang == "graph":
            kinds.append(f"graph:{data.get('type')}")
            points = data.get("points") or []
            if any(not all(math.isfinite(v) for v in point) for point in points):
                problems.append(Problem("broken_visual", "graph has a non-finite point"))
            continue
        try:
            spec = SimulationBlockSpec.model_validate(data)
        except Exception as exc:
            problems.append(Problem("broken_visual", f"simulation fails its schema: {exc}"))
            continue
        kinds.append(spec.type)
        width, height = spec.x_max - spec.x_min, spec.y_max - spec.y_min
        if not 1 / 25 <= width / height <= 25:
            problems.append(
                Problem("broken_visual", f"{spec.type} box is {width:.3g} × {height:.3g}")
            )
        for body_spec in spec.bodies:
            slack = body_spec.radius * 1.05 + 1e-9
            outside = [p for p in body_spec.path if not _in_bounds(p, spec, slack)]
            if outside:
                problems.append(
                    Problem("broken_visual", f"{spec.type} body leaves the box at {outside[0]}")
                )
            share = body_spec.radius / max(width, height)
            if not 0.004 <= share <= 0.3:
                problems.append(
                    Problem("broken_visual", f"{spec.type} body radius is {share:.1%} of the box")
                )
    if "projectile_motion" in kinds and "graph:trajectory" in kinds:
        problems.append(
            Problem("duplicate_visual", "a trajectory graph and an animation of one path")
        )
    return kinds, problems


def judge(entry: Entry, subject: str, route: Route) -> Outcome:
    outcome = Outcome(entry=entry, route=route, reply=route.instant_text)
    problems = outcome.problems
    if route.photo:
        problems.append(Problem("misread", f"photo lookup took the turn ({route.photo!r})"))
    if route.image_gen:
        problems.append(Problem("misread", "image generation took the turn"))
    if entry.expect == "not_subject":
        if route.subject == subject:
            problems.append(Problem("misread", f"read as a {subject} question"))
        return outcome
    if entry.expect in {"explain", "decline"}:
        if route.instant and route.instant != "solver":
            problems.append(Problem("misread", f"instant {route.instant} reply"))
        if route.solved:
            answer = read_answer(route.instant_text)
            problems.append(Problem("wrong", f"gave a number to a question with none: {answer}"))
        return outcome
    if not route.subject:
        problems.append(Problem("missed", f"not read as a {subject} question"))
    elif route.subject != subject and not route.solved:
        problems.append(Problem("misread", f"read as {route.subject}, not {subject}"))
    if route.search == "yes":
        problems.append(Problem("misread", "searched the web"))
    if route.instant and route.instant != "solver":
        # "How far is the image from the lens?" answered "Turn on Location".
        problems.append(
            Problem("misread", f"instant {route.instant} reply: {route.instant_text[:70]!r}")
        )
    if not route.solved:
        problems.append(Problem("unsolved", "no verified answer"))
        return outcome
    if not route.instant_text:
        # Verified, but the model writes the reply around the verified result
        # (an image question, a law kept off the direct path). Check the result.
        verified = _verified_answer(entry.prompt, subject)
        if verified is None:
            problems.append(Problem("unsolved", "no verified answer"))
        elif entry.answer is not None:
            ok, detail = same_quantity(verified, entry.answer)
            outcome.got = detail
            if not ok:
                problems.append(Problem("wrong", detail))
        return outcome
    answers = read_answers(route.instant_text)
    if not answers:
        problems.append(Problem("shape", "verified reply has no readable answer card"))
    elif entry.answer is not None:
        checks = [same_quantity(got, entry.answer) for got in answers]
        match = next((detail for ok, detail in checks if ok), None)
        outcome.got = match or checks[0][1]
        if match is None:
            problems.append(Problem("wrong", "; ".join(detail for _ok, detail in checks)))
    if route.subject == subject:
        problems.extend(check_shape(entry, route.instant_text))
    outcome.visuals, visual_problems = check_visuals(route.instant_text)
    problems.extend(visual_problems)
    if entry.visual and entry.visual not in outcome.visuals:
        problems.append(Problem("no_visual", f"no {entry.visual} picture"))
    return outcome


def _verified_answer(prompt: str, subject: str) -> tuple[float, str] | None:
    if subject != "physics":
        return None
    from app.core.config import Settings
    from app.modules.physics import build_verified_physics_block, extract_physics_intent

    intent = extract_physics_intent(prompt)
    block = build_verified_physics_block(intent, Settings()) if intent else None
    if block is None or not block.display_answer:
        return None
    return read_answer(f"```answer\n{block.display_answer}\n```")


async def run_entry(entry: Entry, subject: str) -> Outcome:
    route = await route_case(Case(entry.id, entry.area, entry.prompt, Expect(), ""))
    return judge(entry, subject, route)


async def run(entries: list[Entry], subject: str) -> list[Outcome]:
    outcomes: list[Outcome] = []
    for entry in entries:
        try:
            outcomes.append(await run_entry(entry, subject))
        except Exception as exc:  # A crash is a finding too.
            outcomes.append(
                Outcome(entry=entry, problems=[Problem("misread", f"crashed: {exc!r}")])
            )
    return outcomes


def answered(outcomes: list[Outcome]) -> list[Outcome]:
    """The ``answer`` turns that got a verified answer."""
    return [
        o
        for o in outcomes
        if o.entry.expect == "answer" and not any(p.kind == "unsolved" for p in o.problems)
    ]


def drawn(outcomes: list[Outcome]) -> list[Outcome]:
    """The ``answer`` turns that carry the picture a student would want."""
    return [
        o
        for o in outcomes
        if o.entry.expect == "answer"
        and o.entry.visual
        and not any(p.kind == "no_visual" for p in o.problems)
    ]


def report(outcomes: list[Outcome], *, show: bool = False) -> str:
    kinds = Counter(problem.kind for outcome in outcomes for problem in outcome.problems)
    answers = [o for o in outcomes if o.entry.expect == "answer"]
    solved = answered(outcomes)
    wanted = [o for o in answers if o.entry.visual]
    lines = [
        f"{len(outcomes)} turns: {len(solved)}/{len(answers)} answered, "
        f"{len(drawn(outcomes))}/{len(wanted)} with the picture a student would want",
        "problems: "
        + (", ".join(f"{kind} {count}" for kind, count in kinds.most_common()) or "none"),
    ]
    by_area: dict[str, list[int]] = {}
    for outcome in answers:
        tally = by_area.setdefault(outcome.entry.area, [0, 0, 0])
        tally[0] += 1
        tally[1] += outcome in solved
        tally[2] += bool(outcome.critical)
    lines.append(f"  {'area':<15} answered  critical")
    for area, (total, solved_here, bad) in sorted(by_area.items()):
        lines.append(f"  {area:<15} {solved_here:>3} / {total:<3} {bad:>4}")
    for outcome in outcomes:
        shown = outcome.problems if show else outcome.critical
        if not shown:
            continue
        entry = outcome.entry
        lines.append(f"\n[{entry.id}] ({entry.area}, expect {entry.expect}) {entry.prompt}")
        for problem in shown:
            lines.append(f"  - {problem.kind}: {problem.text}")
        if outcome.visuals:
            lines.append(f"  pictures: {', '.join(outcome.visuals)}")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("subject", choices=sorted(SUBJECT_NAMES))
    parser.add_argument("--only", help="comma-separated entry ids")
    parser.add_argument("--area", help="one area")
    parser.add_argument("--show", action="store_true", help="also list coverage problems")
    args = parser.parse_args()
    from app.core.sympy_executor import ThreadSympyExecutor, set_sympy_executor

    set_sympy_executor(ThreadSympyExecutor(max_workers=1))
    entries = load(args.subject)
    if args.only:
        wanted = {item.strip() for item in args.only.split(",")}
        entries = [entry for entry in entries if entry.id in wanted]
    if args.area:
        entries = [entry for entry in entries if entry.area == args.area]
    outcomes = asyncio.run(run(entries, SUBJECT_NAMES[args.subject]))
    print(report(outcomes, show=args.show))
    sys.exit(1 if any(outcome.critical for outcome in outcomes) else 0)


if __name__ == "__main__":
    main()
