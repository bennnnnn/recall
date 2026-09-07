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
    leftover: Callable[[str], str] | None = None,
) -> str:
    """Rewrite closed ```lang fences. Linear scan.

    ``max_count`` limits how many fences ``replace`` sees. Further closed
    fences of this lang stay as-is unless ``leftover`` is set (then each
    extra fence is rewritten with that callback — used to fail-closed
    geometry/graph JSON beyond the per-kind cap).
    """
    pieces: list[str] = []
    cursor = 0
    count = 0
    for start, end, body in iter_closed_fences(text, lang):
        over_cap = max_count is not None and count >= max_count
        if over_cap:
            if leftover is None:
                break
            pieces.append(text[cursor:start])
            pieces.append(leftover(body))
        else:
            pieces.append(text[cursor:start])
            pieces.append(replace(body))
            count += 1
        cursor = end
    pieces.append(text[cursor:])
    return "".join(pieces)


def strip_closed_fences(text: str, lang: str) -> str:
    return map_closed_fences(text, lang, lambda _body: "")


_TABLE_HEAD_HINTS = ("point", "plot", "sketch", "table")


def _is_pipe_row(line: str) -> bool:
    s = line.strip()
    return s.startswith("|") and s.count("|") >= 2


def _is_gfm_sep_row(line: str) -> bool:
    """``|---|---|`` / ``|:---:|`` — not a data row."""
    s = line.strip()
    if not s.startswith("|") or s.count("|") < 2:
        return False
    i = 0
    n = len(s)
    saw_cell = False
    while i < n:
        if s[i] != "|":
            i += 1
            continue
        i += 1
        start = i
        while i < n and s[i] != "|":
            i += 1
        cell = s[start:i].strip()
        if not cell:
            continue
        for ch in cell:
            if ch not in "-:":
                return False
        if "-" not in cell:
            return False
        saw_cell = True
    return saw_cell


def strip_gfm_pipe_tables(text: str) -> str:
    """Drop GFM pipe tables in prose (not inside fences).

    Verified-graph turns still dump an xy sample table; the plot is the
    figure, and ``$x$`` / a lone ``1`` cell also mis-render on mobile.
    """
    lines = text.split("\n")
    n = len(lines)
    out: list[str] = []
    i = 0
    in_fence = False
    while i < n:
        stripped = lines[i].lstrip()
        if stripped.startswith("```"):
            in_fence = not in_fence
            out.append(lines[i])
            i += 1
            continue
        if not in_fence and i + 1 < n and _is_pipe_row(lines[i]) and _is_gfm_sep_row(lines[i + 1]):
            if out:
                prev = out[-1].strip()
                low = prev.lower()
                if prev.startswith("#") and any(h in low for h in _TABLE_HEAD_HINTS):
                    out.pop()
                    while out and out[-1].strip() == "":
                        out.pop()
            i += 2
            while i < n and _is_pipe_row(lines[i]):
                i += 1
            if i < n and lines[i].strip() == "":
                i += 1
            continue
        out.append(lines[i])
        i += 1
    return "\n".join(out)


_SKETCH_HEADS = (
    "### how to sketch",
    "### how to plot",
    "### quick sketch",
    "### points to plot",
    "### text-based sketch",
    "### sample points",
)
_SKETCH_PHRASES = ("ascii", "text-based sketch", "text based sketch")
_KEEP_FENCES = ("```graph", "```geometry", "```answer")


def _line_start_before(text: str, idx: int) -> int:
    nl = text.rfind("\n", 0, idx)
    return 0 if nl < 0 else nl + 1


def _next_owned_fence(text: str, start: int) -> int | None:
    lower = text.lower()
    best: int | None = None
    for lang in _KEEP_FENCES:
        p = start
        while True:
            idx = lower.find(lang, p)
            if idx < 0:
                break
            if idx == 0 or text[idx - 1] == "\n":
                if best is None or idx < best:
                    best = idx
                break
            p = idx + 1
    return best


def strip_hand_sketch_filler(text: str) -> str:
    """Drop 'how to sketch' / ASCII plot filler before the owned ```graph.

    After a verified plot exists, the model still writes a point table (already
    stripped) or an ASCII sketch in a quote — the same junk as the keypad graph
    screenshot.
    """
    lower = text.lower()
    cut_from: int | None = None
    for head in _SKETCH_HEADS:
        idx = lower.find(head)
        if idx < 0:
            continue
        line = _line_start_before(text, idx)
        if cut_from is None or line < cut_from:
            cut_from = line
    ascii_at = None
    for phrase in _SKETCH_PHRASES:
        idx = lower.find(phrase)
        if idx < 0:
            continue
        if ascii_at is None or idx < ascii_at:
            ascii_at = idx
    if ascii_at is not None:
        line = _line_start_before(text, ascii_at)
        if cut_from is None or line < cut_from:
            cut_from = line
    if cut_from is None:
        return text
    keep = _next_owned_fence(text, cut_from)
    head = text[:cut_from].rstrip()
    if keep is None:
        return head + ("\n" if head else "")
    return head + "\n\n" + text[keep:]


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
