"""Quote mermaid node labels that contain raw parentheses.

Unquoted ``E[Grind Beans (Medium Grind)]`` is invalid Mermaid and the
WebView parse-fails. Linear scan — no nested regex.
"""

from __future__ import annotations

from app.services.md_fence_scan import map_closed_fences


def sanitize_mermaid_node_labels(text: str) -> str:
    """Wrap unquoted ``[...]`` bodies that contain ``(`` or ``)`` in quotes.

    Leaves already-quoted labels and stadium ``start([Start])`` (inner text
    has no parens) unchanged.
    """
    if "(" not in text and ")" not in text:
        return text
    pieces: list[str] = []
    index = 0
    length = len(text)
    while index < length:
        bracket = text.find("[", index)
        if bracket < 0:
            pieces.append(text[index:])
            break
        pieces.append(text[index:bracket])
        if bracket + 1 < length and text[bracket + 1] == '"':
            close = text.find('"]', bracket + 2)
            if close < 0:
                pieces.append(text[bracket:])
                break
            pieces.append(text[bracket : close + 2])
            index = close + 2
            continue
        close = text.find("]", bracket + 1)
        if close < 0:
            pieces.append(text[bracket:])
            break
        body = text[bracket + 1 : close]
        if ("(" in body or ")" in body) and not (
            len(body) >= 2 and body[0] == '"' and body[-1] == '"'
        ):
            pieces.append('["')
            pieces.append(body.replace('"', "'"))
            pieces.append('"]')
        else:
            pieces.append(text[bracket : close + 1])
        index = close + 1
    return "".join(pieces)


def _wrap_mermaid_body(body: str) -> str:
    sanitized = sanitize_mermaid_node_labels(body)
    if not sanitized.endswith("\n"):
        sanitized += "\n"
    return f"```mermaid\n{sanitized}```\n"


def sanitize_mermaid_fences(text: str) -> str:
    """Rewrite closed ```mermaid fences so parenthetical labels are quoted."""
    if "```mermaid" not in text.lower():
        return text
    return map_closed_fences(text, "mermaid", _wrap_mermaid_body)
