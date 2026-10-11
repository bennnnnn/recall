"""Copy fenced regions byte-for-byte while rewriting the prose between them."""

from __future__ import annotations

from collections.abc import Callable


def _fence_marker(line: str) -> tuple[str, int, str] | None:
    """CommonMark fence opener: up to three leading spaces, then ``` or ~~~."""
    indent = 0
    while indent < len(line) and indent < 3 and line[indent] == " ":
        indent += 1
    if indent >= len(line):
        return None
    char = line[indent]
    if char not in {"`", "~"}:
        return None
    length = 0
    index = indent
    while index < len(line) and line[index] == char:
        length += 1
        index += 1
    if length < 3:
        return None
    return char, length, line[index:].strip()


def read_fence_marker(line: str) -> tuple[str, int, str] | None:
    """Public name for the fence opener used by presentation."""
    return _fence_marker(line)


def rewrite_fenced(
    text: str,
    rewrite_prose: Callable[[str], str],
    rewrite_fence: Callable[[str, str, str], str | None],
) -> str:
    """Rewrite prose, and replace a fence when ``rewrite_fence`` returns text.

    ``rewrite_fence`` receives the opener line, the body, and the closer line.
    ``None`` keeps that fence byte-for-byte. An unclosed fence stays raw.
    """
    if not text:
        return rewrite_prose(text)
    lines = text.split("\n")
    out: list[str] = []
    prose: list[str] = []
    open_fence: tuple[str, int] | None = None
    opener_line = ""
    body: list[str] = []

    def flush() -> None:
        if not prose:
            return
        out.append(rewrite_prose("\n".join(prose)))
        prose.clear()

    for line in lines:
        marker = _fence_marker(line)
        if open_fence is not None:
            char, length = open_fence
            if marker is not None and marker[0] == char and marker[1] >= length and marker[2] == "":
                replacement = rewrite_fence(opener_line, "\n".join(body), line)
                if replacement is None:
                    out.append(opener_line)
                    out.extend(body)
                    out.append(line)
                else:
                    out.append(replacement)
                open_fence = None
                body = []
            else:
                body.append(line)
            continue
        if marker is not None and "|" not in marker[2]:
            flush()
            open_fence = (marker[0], marker[1])
            opener_line = line
            continue
        prose.append(line)
    flush()
    if open_fence is not None:
        out.append(opener_line)
        out.extend(body)
    return "\n".join(out)


def map_prose_outside_fences(text: str, rewrite: Callable[[str], str]) -> str:
    """Apply ``rewrite`` to prose only. Fence openers, bodies, and closers stay intact."""
    if not text:
        return rewrite(text)
    lines = text.split("\n")
    out: list[str] = []
    prose: list[str] = []
    open_fence: tuple[str, int] | None = None

    def flush() -> None:
        if not prose:
            return
        out.append(rewrite("\n".join(prose)))
        prose.clear()

    for line in lines:
        marker = _fence_marker(line)
        if open_fence is not None:
            out.append(line)
            char, length = open_fence
            if marker is not None and marker[0] == char and marker[1] >= length and marker[2] == "":
                open_fence = None
            continue
        # `` ``` | ```java `` is a broken table cell, not a fence opener.
        if marker is not None and "|" not in marker[2]:
            flush()
            out.append(line)
            open_fence = (marker[0], marker[1])
            continue
        prose.append(line)
    flush()
    return "\n".join(out)


def leave_prose_line(line: str) -> bool:
    """Indented code and blockquotes keep their source spacing."""
    stripped = line.lstrip(" ")
    if line.startswith("    ") or line.startswith("\t"):
        return True
    return stripped.startswith(">")
