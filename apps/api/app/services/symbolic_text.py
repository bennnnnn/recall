"""Subject-neutral normalization for symbolic math and physics requests."""

from __future__ import annotations

from app.services.text_normalize import collapse_ws

_MAX_SYMBOLIC_REQUEST = 1000
# A multi-part worksheet can exceed the shared ceiling. Callers opt in;
# the default stays 1000 so a long essay cannot enter the math scanner.
_MAX_EXTENDED_SYMBOLIC_REQUEST = 4000
_SUP_GLYPHS = "⁰¹²³⁴⁵⁶⁷⁸⁹"
_SUP_ASCII = "0123456789"
_SUP_TABLE = str.maketrans(_SUP_GLYPHS, _SUP_ASCII)


def strip_inline_math_delimiters(text: str) -> str:
    """Remove composer delimiters without changing the enclosed expression."""
    return (
        text.replace("$$", "")
        .replace("$", "")
        .replace("\\(", "")
        .replace("\\)", "")
        .replace("\\[", "")
        .replace("\\]", "")
    )


def fold_numeric_superscripts(text: str) -> str:
    """Normalize Unicode and braced numeric powers to caret notation."""
    out: list[str] = []
    index = 0
    while index < len(text):
        char = text[index]
        if char in _SUP_GLYPHS:
            end = index + 1
            while end < len(text) and text[end] in _SUP_GLYPHS:
                end += 1
            out.append("^" + text[index:end].translate(_SUP_TABLE))
            index = end
            continue
        if char == "^" and index + 1 < len(text) and text[index + 1] == "{":
            close = text.find("}", index + 2)
            if close != -1:
                inner = text[index + 2 : close]
                if inner.isdigit() and (not out or out[-1] != "}"):
                    out.append("^" + inner)
                    index = close + 1
                    continue
        out.append(char)
        index += 1
    return "".join(out)


def collapse_repeated_si_unit_powers(text: str) -> str:
    """Collapse repeated keyboard inserts such as ``m/s^2^2.^2``."""
    out: list[str] = []
    index = 0
    while index < len(text):
        if index + 4 <= len(text) and text[index : index + 4] == "m/s^":
            end = index + 4
            if end < len(text) and text[end].isdigit():
                digit_end = end + 1
                while digit_end < len(text) and text[digit_end].isdigit():
                    digit_end += 1
                out.append(text[index:digit_end])
                index = digit_end
                while index < len(text):
                    repeat = index + (1 if text[index : index + 1] == "." else 0)
                    if (
                        repeat + 1 < len(text)
                        and text[repeat] == "^"
                        and text[repeat + 1].isdigit()
                    ):
                        repeat += 2
                        while repeat < len(text) and text[repeat].isdigit():
                            repeat += 1
                        index = repeat
                        continue
                    break
                continue
        out.append(text[index])
        index += 1
    return "".join(out)


def normalize_symbolic_request(text: str, *, limit: int = _MAX_SYMBOLIC_REQUEST) -> str | None:
    """Normalize bounded user text without applying subject semantics."""
    cleaned = collapse_ws(strip_inline_math_delimiters(text))
    bounded = min(max(limit, 0), _MAX_EXTENDED_SYMBOLIC_REQUEST)
    if len(cleaned) > bounded:
        return None
    return collapse_repeated_si_unit_powers(fold_numeric_superscripts(cleaned))
