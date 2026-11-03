"""A single task is not a fact about the person: model facts read off a request are dropped.

After one question the memory model saved "User is working on solving the quadratic
equation x^2 - 5x + 6 = 0" (from "solve x^2 - 5x + 6 = 0"), "User is learning basic web
development with HTML and JavaScript" (from "write a simple HTML page with a button that
counts clicks") and "User scored 85 in math, 72 in chemistry …" (from "make a bar chart
of my test scores: math 85, chemistry 72 …"), 2026-11-02. The prompt says a one-off
question is not a fact; these rules hold it in code:

- Lines that only ask for work (a task verb, a question, an expression) and say nothing
  of the user (no I, my, we, our) state no fact: the model's facts from them are dropped.
- Numbers a request hands over (a list of three or more, or an equation) are the task's
  material: a fact that repeats two or more of them, and no other number, is dropped,
  unless a clause says them of the user ("I got 85 in maths").

How the user wants replies (a preferences fact) is kept either way: "keep replies short"
asks for no task. A "remember …" line skips these rules (``pass_writes``). Pure text, no IO.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence

from app.modules.memory.text import is_memory_candidate
from app.modules.memory.writes_repository import MemoryFactWrite
from app.services.text_normalize import straighten_apostrophes

# Verbs that ask for work on something the message hands over or names.
_TASK_VERBS = frozenset({
    "solve", "write", "make", "create", "draw", "plot", "graph", "chart", "explain",
    "calculate", "compute", "find", "translate", "summarize", "summarise", "generate",
    "convert", "list", "give", "show", "tell", "simplify", "factor", "factorise", "factorize",
    "differentiate", "integrate", "evaluate", "build", "code", "design", "fix", "debug",
    "compare", "check", "proofread", "rewrite", "define", "describe", "outline", "sketch",
    "derive", "prove", "expand", "balance", "render", "format", "sort", "estimate",
    "analyze", "analyse", "review", "edit", "correct", "improve", "shorten", "paraphrase",
    "implement", "compose", "draft", "visualize", "visualise", "simulate", "count",
})  # fmt: skip
_QUESTION_WORDS = frozenset({
    "what", "what's", "whats", "how", "why", "when", "where", "which", "who", "whose",
    "is", "are", "does", "do", "can", "could", "would", "will", "should",
})  # fmt: skip
# Words before the ask that change nothing: "please", "hey", "ok so".
_LEADS = frozenset({
    "please", "pls", "plz", "hey", "hi", "ok", "okay", "so", "now", "also", "and", "then",
    "just", "quickly", "kindly", "quick", "yo",
})  # fmt: skip
# "Can you", "I need you to", "I want a": a request's opening, not a fact about the user.
_REQUEST_OPENINGS: tuple[tuple[str, ...], ...] = (
    ("can", "you"), ("could", "you"), ("would", "you"), ("will", "you"),
    ("i", "want", "you", "to"), ("i", "need", "you", "to"), ("i'd", "like", "you", "to"),
    ("i", "would", "like", "you", "to"), ("help", "me"), ("i", "want", "a"),
    ("i", "want", "an"), ("i", "need", "a"), ("i", "need", "an"), ("i'd", "like", "a"),
    ("i'd", "like", "an"),
)  # fmt: skip
_FIRST_PERSON = frozenset({
    "i", "i'm", "im", "i've", "ive", "i'll", "i'd", "my", "mine", "myself", "we", "we're",
    "we've", "our", "ours", "ourselves", "me", "us",
})  # fmt: skip
# "Make me a chart", "show us the steps": who gets the work, not a fact about them.
_OBJECT_PRONOUNS = frozenset({"me", "us"})
_SELF_SUBJECTS = frozenset({
    "i", "i'm", "im", "i've", "ive", "i'll", "i'd", "we", "we're", "we've", "my", "our",
})  # fmt: skip
_CLAUSE_BREAK = re.compile(r"[.!?;:,\n]+")
_WORD = re.compile(r"[a-z0-9']+")
_NUMBER = re.compile(r"(?<![\w.])\d+(?:\.\d+)?")
# An expression handed over: "x^2 - 5x + 6 = 0", "3*4", "12/5". A minus needs spaces round
# it, so "2024-2025" and "well-known" are not one.
_EXPRESSION = re.compile(r"[\w)]\s*[=^*/+]\s*[\w(]|\w\s-\s\w")
_MATERIAL_MIN_NUMBERS = 3


def drop_task_facts(
    writes: Sequence[MemoryFactWrite], lines: str
) -> tuple[list[MemoryFactWrite], int]:
    """``writes`` without the facts the rules above drop, and how many were dropped."""
    said = _user_lines(lines)
    tasks_only = bool(said) and all(_task_saying_nothing_of_user(line) for line in said)
    material = _handed_over_numbers(said)
    kept: list[MemoryFactWrite] = []
    for write in writes:
        if write.op in {"add", "update", "supersede"} and write.type != "preference":
            if tasks_only or _repeats_material(write.text, material):
                continue
        kept.append(write)
    return kept, len(writes) - len(kept)


def _user_lines(lines: str) -> list[str]:
    said: list[str] = []
    for raw in lines.splitlines():
        line = raw.strip()
        if line.lower().startswith("assistant:"):
            continue
        line = line.split(":", 1)[1].strip() if line.lower().startswith("user:") else line
        # "Thanks", "ok": small talk neither states nor asks.
        if line and is_memory_candidate(line):
            said.append(line)
    return said


def _words(text: str) -> list[str]:
    return _WORD.findall(straighten_apostrophes(text).lower())


def _opening_skipped(words: list[str]) -> list[str]:
    """The words after any "please", "hey", "can you" or "I need you to"."""
    while words:
        if words[0] in _LEADS:
            words = words[1:]
            continue
        opening = next((o for o in _REQUEST_OPENINGS if tuple(words[: len(o)]) == o), None)
        if opening is None:
            return words
        words = words[len(opening) :]
    return words


def _is_request(line: str) -> bool:
    words = _opening_skipped(_words(line))
    if not words:
        return False
    return (
        words[0] in _TASK_VERBS
        or words[0] in _QUESTION_WORDS
        or line.rstrip().endswith("?")
        or (_EXPRESSION.search(line) is not None and any(c.isdigit() for c in line))
    )


def _names_the_user(line: str) -> bool:
    """I, my, we, our anywhere, past the request's opening; "make me a chart" names no one."""
    for clause in _CLAUSE_BREAK.split(line):
        words = _opening_skipped(_words(clause))
        for index, word in enumerate(words):
            if word not in _FIRST_PERSON:
                continue
            if word in _OBJECT_PRONOUNS and index > 0 and words[index - 1] in _TASK_VERBS:
                continue
            return True
    return False


def _task_saying_nothing_of_user(line: str) -> bool:
    return _is_request(line) and not _names_the_user(line)


def _states_of_user(line: str) -> bool:
    """A clause with the user as its subject: "I got 85 in maths", "my scores are …"."""
    for clause in _CLAUSE_BREAK.split(line):
        words = _words(clause)
        while words and words[0] in _LEADS:
            words = words[1:]
        if words and words[0] in _SELF_SUBJECTS and _opening_skipped(words) == words:
            return True
    return False


def _handed_over_numbers(said: Iterable[str]) -> set[str]:
    """The numbers requests hand over as material: a list of three or more, or an equation."""
    material: set[str] = set()
    for line in said:
        if not _is_request(line) or _states_of_user(line):
            continue
        numbers = _NUMBER.findall(line)
        if len(numbers) >= _MATERIAL_MIN_NUMBERS or (numbers and _EXPRESSION.search(line)):
            material.update(numbers)
    return material


def _repeats_material(text: str, material: set[str]) -> bool:
    if not material:
        return False
    numbers = _NUMBER.findall(text)
    return len(numbers) >= 2 and all(number in material for number in numbers)
