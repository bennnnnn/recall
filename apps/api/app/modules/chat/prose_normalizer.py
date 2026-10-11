"""Post-stream prose artifact normalizer.

Cleans up known model output artifacts that survive prompt instructions:
- Orphan colon lines (model puts `:` on its own line as a "leads to next line" marker)
- Excess blank lines (3+ consecutive newlines collapsed to 2)
- Markdown pipe tables accidentally wrapped in a generic/markdown code fence

Runs after all fence enrichment so it never interferes with fence parsing.
Only sets final_content when the text actually changes.
Never rewrites the inside of fenced code blocks.
"""

from __future__ import annotations

import re

_COPY_FENCE_TAGS = frozenset(
    {"email", "message", "sms", "copy", "twitter", "linkedin", "facebook", "instagram", "social"}
)
_TEMPLATE_CUES = ("template", "placeholder", "fill in", "fill-in", "reusable")
_RECIPIENT_SLOT_CUES = (
    "name",
    "recipient",
    "coworker",
    "colleague",
    "boss",
    "manager",
    "friend",
    "client",
    "customer",
)
_GREETING_SLOT = re.compile(
    r"^(?P<indent>\s*)(?P<greeting>hi|hello|hey|dear)\s+"
    r"\[(?P<label>[^\]\n]{1,80})\](?:\s*[,!])?",
    re.IGNORECASE,
)


def strip_unrequested_recipient_placeholders(text: str, user_text: str) -> str:
    """Remove invented recipient slots from send-ready copy fences.

    Unknown recipients should be greeted generically (``Hi,``), not exposed as
    ``[Coworker's Name]`` in a supposedly ready-to-send card. Explicit template
    requests retain their placeholders.
    """
    request = user_text.casefold()
    if any(cue in request for cue in _TEMPLATE_CUES):
        return text

    lines = text.split("\n")
    out: list[str] = []
    copy_fence = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("```"):
            tag = stripped[3:].strip().split(maxsplit=1)[0].lower() if stripped[3:].strip() else ""
            if copy_fence and not tag:
                copy_fence = False
            elif not copy_fence and tag in _COPY_FENCE_TAGS:
                copy_fence = True
            out.append(line)
            continue
        if not copy_fence:
            out.append(line)
            continue
        match = _GREETING_SLOT.match(line)
        if match is None or not any(
            cue in match.group("label").casefold() for cue in _RECIPIENT_SLOT_CUES
        ):
            out.append(line)
            continue
        greeting = match.group("greeting")
        if greeting.casefold() == "dear":
            greeting = "Hello"
        out.append(f"{match.group('indent')}{greeting},{line[match.end() :]}")
    return "\n".join(out)


def _is_gfm_separator_row(line: str) -> bool:
    cells = line.strip().strip("|").split("|")
    return bool(cells) and all(
        "-" in cell and not (set(cell.strip()) - {"-", ":"}) for cell in cells
    )


def _is_pipe_table_body(lines: list[str]) -> bool:
    body = [line for line in lines if line.strip()]
    if len(body) < 2:
        return False
    if not body[0].strip().startswith("|") or not _is_gfm_separator_row(body[1]):
        return False
    return all(line.strip().startswith("|") and line.strip().endswith("|") for line in body)


def _unwrap_fenced_pipe_tables(text: str) -> str:
    """Let a valid table render as a table when the model fenced it.

    Only generic and explicitly-markdown fences whose complete body is a GFM
    table are unwrapped.  Programming-language fences and mixed prose/code are
    left byte-for-byte alone.
    """
    lines = text.split("\n")
    out: list[str] = []
    index = 0
    while index < len(lines):
        opener = lines[index].strip().lower()
        if opener not in {"```", "```markdown", "```md"}:
            out.append(lines[index])
            index += 1
            continue
        closer = index + 1
        while closer < len(lines) and lines[closer].strip() != "```":
            closer += 1
        if closer >= len(lines):
            out.extend(lines[index:])
            break
        body = lines[index + 1 : closer]
        if _is_pipe_table_body(body):
            out.extend(body)
        else:
            out.extend(lines[index : closer + 1])
        index = closer + 1
    return "\n".join(out)


def normalize_prose_artifacts(text: str) -> str:
    """Remove orphan colon lines and collapse excess blank lines outside fences."""
    text = _unwrap_fenced_pipe_tables(text)
    lines = text.split("\n")
    out: list[str] = []
    in_fence = False
    blank_run = 0
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("```"):
            in_fence = not in_fence
            blank_run = 0
            out.append(line)
            continue
        if in_fence:
            out.append(line)
            continue
        if stripped == ":":
            blank_run += 1
            if blank_run < 2:
                out.append("")
            continue
        if stripped == "":
            blank_run += 1
            if blank_run >= 2:
                continue
            out.append(line)
            continue
        blank_run = 0
        out.append(line)
    return "\n".join(out).strip()


def prose_changed(original: str, normalized: str) -> bool:
    """True when the normalizer actually modified the text."""
    return normalized != original.strip()
