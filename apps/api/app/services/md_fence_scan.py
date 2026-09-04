"""Linear markdown-fence scan — no nested regex on untrusted assistant text."""

from __future__ import annotations

from collections.abc import Callable, Iterator


def is_fence_closer(line: str) -> bool:
    """True when the line is only backticks (a closer), not ```python."""
    stripped = line.strip()
    return len(stripped) >= 3 and stripped == "`" * len(stripped)


def next_fence_marker_line(text: str, from_index: int) -> tuple[int, int, str] | None:
    """Next line that starts with ```. Returns (line_start, after_line, stripped)."""
    index = from_index
    length = len(text)
    while index < length:
        newline = text.find("\n", index)
        end = length if newline < 0 else newline
        line = text[index:end]
        stripped = line.strip()
        if stripped.startswith("```"):
            after = length if newline < 0 else newline + 1
            return index, after, stripped
        if newline < 0:
            return None
        index = newline + 1
    return None


def find_lang_opener(text: str, lang: str, start: int = 0) -> int | None:
    """Index of the next line-start ```lang opener, or None."""
    needle = "```" + lang.lower()
    lower = text.lower()
    index = start
    tag_len = len(lang)
    while True:
        pos = lower.find(needle, index)
        if pos < 0:
            return None
        if pos == 0 or text[pos - 1] == "\n":
            after = pos + 3 + tag_len
            if after >= len(text) or text[after] in " \t\r\n":
                return pos
        index = pos + 1


def iter_closed_fences(text: str, lang: str) -> Iterator[tuple[int, int, str]]:
    """Yield (start, end, body) for closed ```lang fences. Linear, fence-aware.

    A fence is closed only by a line of bare backticks. A following
    ```python opener does not close the previous fence.
    """
    index = 0
    while True:
        opener = find_lang_opener(text, lang, index)
        if opener is None:
            return
        newline = text.find("\n", opener)
        if newline < 0:
            return
        body_start = newline + 1
        marker = next_fence_marker_line(text, body_start)
        if marker is None:
            return
        line_start, after, stripped = marker
        if not is_fence_closer(stripped):
            index = line_start
            continue
        yield opener, after, text[body_start:line_start]
        index = after


def replace_first_closed_fence_body(text: str, lang: str, new_body: str) -> str | None:
    """Replace the inner body of the first closed ```lang fence. Keep opener/closer."""
    hit = next(iter_closed_fences(text, lang), None)
    if hit is None:
        return None
    opener, _after, old_body = hit
    newline = text.find("\n", opener)
    if newline < 0:
        return None
    body_start = newline + 1
    line_start = body_start + len(old_body)
    body = new_body.rstrip("\n") + "\n"
    return text[:body_start] + body + text[line_start:]


def has_closed_fence(text: str, lang: str) -> bool:
    return next(iter_closed_fences(text, lang), None) is not None


def map_closed_fences(
    text: str,
    lang: str,
    replace: Callable[[str], str],
    *,
    max_count: int | None = None,
) -> str:
    """Rewrite up to max_count closed ```lang fences. Linear scan."""
    pieces: list[str] = []
    cursor = 0
    count = 0
    for start, end, body in iter_closed_fences(text, lang):
        if max_count is not None and count >= max_count:
            break
        pieces.append(text[cursor:start])
        pieces.append(replace(body))
        cursor = end
        count += 1
    pieces.append(text[cursor:])
    return "".join(pieces)


def strip_closed_fences(text: str, lang: str) -> str:
    return map_closed_fences(text, lang, lambda _body: "")


def close_unclosed_fences(text: str) -> str:
    """If a fence is left open (cancel / provider fail), close it."""
    count = 0
    index = 0
    while True:
        marker = next_fence_marker_line(text, index)
        if marker is None:
            break
        count += 1
        index = marker[1]
    if count % 2 == 1:
        return text.rstrip() + "\n```\n"
    return text
