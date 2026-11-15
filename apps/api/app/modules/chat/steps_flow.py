"""Finalize pass: a how-to's steps reach the phone as the flow card the prompt asked for.

"If I ask how to do something, I need to see a flow with arrows" (the owner, 2026-11-14). The
how-to rules ask for the steps in one ```steps card (``STEPS_FORMAT_HINT``), which the phone
draws as boxes joined by arrows; in live probes five how-tos in six came as the card, and "how
do I make a budget" as a numbered list of bold labels. So on a turn whose prompt carried those
rules, the reply's numbered list whose every item opens with a bold label becomes the card: the
label is the step's title, the rest of the item the line under it.

The rules keep a goal reached in several independent ways (save money, sleep better) as bullets
that open with a bold label, never numbered: a numbered list there is a sequence. A list of
plain items, a short one, or a reply that already holds the card stays as written.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from app.modules.chat.prompt_constants import STEPS_FORMAT_HINT
from app.services.md_fence_scan import iter_fences, line_fences

if TYPE_CHECKING:
    from app.modules.chat.finalize_passes import FinalizeState

_STEPS_LANG = "steps"
# Fewer than this is no sequence worth a flow.
MIN_STEPS = 3
_ITEM = re.compile(r"^ {0,3}(\d{1,2})[.)]\s+(.*)$")
# "**Add up your income:** Use the take-home amount": its label, then the rest.
_LABELLED = re.compile(r"^\*\*(?P<label>[^*\n]+?)\*\*\s*(?P<rest>.*)$")
# What closes a label: "**Boil the water:**", "**Boil the water.** Then".
_LABEL_END = re.compile(r"[\s:.\u2014\u2013-]+$")
_REST_START = re.compile(r"^[:\u2014\u2013-]\s*")


def _asked_for_steps(state: FinalizeState) -> bool:
    return any(
        message.get("role") == "system"
        and isinstance(content := message.get("content"), str)
        and STEPS_FORMAT_HINT in content
        for message in state.ctx.prompt_messages
    )


def _numbered_runs(lines: list[str], owners: list[object]) -> list[tuple[int, int]]:
    """Each run of prose lines that is one numbered list (items 1, 2, 3 … with the lines
    under them), as (first, past last) line indexes, at least ``MIN_STEPS`` items long."""
    runs: list[tuple[int, int]] = []
    start, expected, end = None, 1, 0

    def close() -> None:
        if start is not None and expected - 1 >= MIN_STEPS:
            runs.append((start, end))

    for index, line in enumerate(lines):
        item = _ITEM.match(line) if owners[index] is None else None
        if item and int(item.group(1)) == expected and (start is not None or expected == 1):
            start = index if start is None else start
            expected, end = expected + 1, index + 1
            continue
        # A line straight under an item, or indented under it, is that item's; a fence,
        # another list or prose after a blank line ends the run.
        under = start is not None and owners[index] is None and line.strip() and not item
        if under and (line.startswith(" ") or lines[index - 1].strip()):
            end = index + 1
        elif line.strip() or owners[index] is not None:
            close()
            start, expected = None, 1
            if item and int(item.group(1)) == 1:
                start, expected, end = index, 2, index + 1
    close()
    return runs


def _card(lines: list[str]) -> str | None:
    """The run's items as a ```steps card, or None when an item opens with no bold label."""
    steps: list[list[str]] = []
    for line in lines:
        item = _ITEM.match(line)
        if item is None:
            if line.strip():
                steps[-1].append(line.strip())
            continue
        labelled = _LABELLED.match(item.group(2).strip())
        if labelled is None:
            return None
        label = _LABEL_END.sub("", labelled.group("label"))
        rest = _REST_START.sub("", labelled.group("rest")).strip()
        steps.append([f"{len(steps) + 1}. **{label}**", *([rest] if rest else [])])
    body = "\n".join(line for step in steps for line in step)
    return f"```{_STEPS_LANG}\n{body}\n```"


def as_step_flow(text: str) -> str:
    """The reply with its numbered list of labelled steps as one ```steps card."""
    if any(fence.lang == _STEPS_LANG for fence in iter_fences(text)):
        return text
    lines = text.split("\n")
    # The steps come after what is needed: the last list whose every item is labelled.
    for start, end in reversed(_numbered_runs(lines, list(line_fences(text)))):
        card = _card(lines[start:end])
        if card is not None:
            return "\n".join([*lines[:start], card, *lines[end:]])
    return text


def hold_step_flow(state: FinalizeState) -> str:
    """Pass entry: on a how-to turn, the steps as the flow card."""
    if state.server_text or state.was_cancelled or not _asked_for_steps(state):
        return state.text
    return as_step_flow(state.text)
