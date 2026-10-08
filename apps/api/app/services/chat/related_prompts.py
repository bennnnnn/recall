"""Related question strings for a math, physics, chemistry, or biology turn.

Built from the user's own wording. No model call, so the reply is not held
up waiting for another suggestion.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from decimal import Decimal

from app.services.subject_solving import detect_subject
from app.services.text_normalize import collapse_ws

_MAX_PROMPTS = 3

# Same cues the presentation subject uses, plus plain biology topics that
# have no number to rewrite.
_BIOLOGY_BANKS: tuple[tuple[tuple[str, ...], tuple[str, str, str]], ...] = (
    (
        ("photosynthesis",),
        (
            "What is the equation for photosynthesis?",
            "Where does photosynthesis happen?",
            "How is photosynthesis different from cellular respiration?",
        ),
    ),
    (
        ("mitosis",),
        (
            "What are the stages of mitosis?",
            "How is mitosis different from meiosis?",
            "What is the result of mitosis?",
        ),
    ),
    (
        ("punnett", "allele"),
        (
            "What is a Punnett square for a heterozygous cross?",
            "What is the difference between a genotype and a phenotype?",
            "What is a dominant allele?",
        ),
    ),
    (
        ("hardy-weinberg", "hardy weinberg"),
        (
            "What is the Hardy-Weinberg equation?",
            "What does p + q = 1 mean in Hardy-Weinberg?",
            "What changes allele frequencies in a population?",
        ),
    ),
    (
        ("dilution",),
        (
            "What is C1V1 = C2V2?",
            "How do you dilute a stock solution by half?",
            "What is the difference between a dilution and a concentration?",
        ),
    ),
    (
        ("enzyme kinetics", "michaelis"),
        (
            "What is the Michaelis-Menten equation?",
            "What does Km mean in enzyme kinetics?",
            "How does substrate concentration change the rate of an enzyme?",
        ),
    ),
    (
        ("population growth",),
        (
            "What is exponential population growth?",
            "What is the difference between exponential and logistic growth?",
            "What limits population growth?",
        ),
    ),
)

_BINARY_ARITH = re.compile(
    r"^(?P<prefix>.*?)"
    r"(?P<a>\d+(?:\.\d+)?)"
    r"(?P<gap1>\s*)"
    r"(?P<op>[+\-*/\u00d7\u00f7\u2212xX])"
    r"(?P<gap2>\s*)"
    r"(?P<b>\d+(?:\.\d+)?)"
    r"(?P<suffix>[^0-9]*)$"
)
# Skip exponents (m/s^2) and digits glued to a formula (H2O).
_NUMBER = re.compile(r"(?<![\w.^])(\d+(?:\.\d+)?)")
_NEXT_OP = {
    "+": "\u2212",
    "-": "\u00d7",
    "\u2212": "\u00d7",
    "*": "\u00f7",
    "\u00d7": "\u00f7",
    "x": "\u00f7",
    "X": "\u00f7",
    "/": "+",
    "\u00f7": "+",
}


def related_prompts(user_text: str) -> list[str]:
    """Up to three related questions, or nothing when this is not a subject turn."""
    text = collapse_ws(user_text or "")
    if not text:
        return []
    subject = _subject(text)
    if subject is None:
        return []
    if subject == "math":
        arithmetic = _arithmetic_prompts(text)
        if arithmetic:
            return arithmetic
    numbered = _numbered_prompts(text)
    if numbered:
        return numbered
    if subject == "biology":
        return _biology_prompts(text)
    return []


def latest_related_prompts(turns: Sequence[tuple[str, str]]) -> list[str]:
    """Prompts for the latest assistant turn, from the user line just before it."""
    if not turns or turns[-1][0] != "assistant":
        return []
    for role, content in reversed(turns[:-1]):
        if role == "user":
            return related_prompts(content)
    return []


def related_prompts_for_page(
    turns: Sequence[tuple[str, str]],
    *,
    newest_page: bool,
) -> list[str]:
    """Older history pages do not repeat chips that belong on the latest reply."""
    if not newest_page:
        return []
    return latest_related_prompts(turns)


def _subject(text: str) -> str | None:
    detected = detect_subject(text)
    if detected is not None:
        return detected
    if _biology_bank(text) is not None:
        return "biology"
    return None


def _biology_bank(text: str) -> tuple[str, str, str] | None:
    lowered = text.casefold()
    for cues, questions in _BIOLOGY_BANKS:
        if any(cue in lowered for cue in cues):
            return questions
    return None


def _biology_prompts(text: str) -> list[str]:
    bank = _biology_bank(text)
    if bank is None:
        return []
    return _unique(text, list(bank))


def _arithmetic_prompts(text: str) -> list[str]:
    match = _BINARY_ARITH.match(text)
    if match is None:
        return []
    prefix = match.group("prefix")
    left = match.group("a")
    gap1 = match.group("gap1")
    op = match.group("op")
    gap2 = match.group("gap2")
    right = match.group("b")
    suffix = match.group("suffix")
    swapped = _NEXT_OP.get(op)
    if swapped is None:
        return []
    candidates = [
        _arith(prefix, _bump(left, 1), gap1, op, gap2, right, suffix),
        _arith(prefix, left, gap1, op, gap2, _bump(right, 1), suffix),
        _arith(prefix, left, gap1, swapped, gap2, right, suffix),
        _arith(prefix, _bump(left, 2), gap1, op, gap2, right, suffix),
        _arith(prefix, left, gap1, op, gap2, _bump(right, 2), suffix),
    ]
    return _unique(text, candidates)


def _arith(
    prefix: str,
    left: str,
    gap1: str,
    op: str,
    gap2: str,
    right: str,
    suffix: str,
) -> str:
    return f"{prefix}{left}{gap1}{op}{gap2}{right}{suffix}"


def _numbered_prompts(text: str) -> list[str]:
    matches = list(_NUMBER.finditer(text))
    if not matches:
        return []
    candidates: list[str] = []
    if len(matches) == 1:
        token = matches[0]
        for step in (1, 2, 3):
            candidates.append(_replace_span(text, token, _bump(token.group(1), step)))
    else:
        for match in matches[:_MAX_PROMPTS]:
            candidates.append(_replace_span(text, match, _bump(match.group(1), 1)))
        if len(candidates) < _MAX_PROMPTS:
            first = matches[0]
            candidates.append(_replace_span(text, first, _bump(first.group(1), 2)))
    return _unique(text, candidates)


def _replace_span(text: str, match: re.Match[str], replacement: str) -> str:
    return f"{text[: match.start()]}{replacement}{text[match.end() :]}"


def _bump(token: str, steps: int) -> str:
    if "." in token:
        places = len(token.split(".", 1)[1])
        value = Decimal(token) + (Decimal(steps) / (Decimal(10) ** places))
        return f"{value:.{places}f}"
    return str(int(token) + steps)


def _unique(original: str, candidates: list[str]) -> list[str]:
    seen = {collapse_ws(original).casefold()}
    chosen: list[str] = []
    for candidate in candidates:
        key = collapse_ws(candidate).casefold()
        if not key or key in seen:
            continue
        seen.add(key)
        chosen.append(candidate)
        if len(chosen) == _MAX_PROMPTS:
            break
    return chosen
