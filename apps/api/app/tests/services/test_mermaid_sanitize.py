from app.services.mermaid_sanitize import (
    sanitize_mermaid_fences,
    sanitize_mermaid_node_labels,
)

GRIND = "D --> E[Grind Beans (Medium Grind)]"
GRIND_QUOTED = 'D --> E["Grind Beans (Medium Grind)"]'


def test_quotes_parenthetical_rectangle_label() -> None:
    assert sanitize_mermaid_node_labels(GRIND) == GRIND_QUOTED


def test_already_quoted_labels_unchanged() -> None:
    assert sanitize_mermaid_node_labels(GRIND_QUOTED) == GRIND_QUOTED


def test_stadium_start_unchanged() -> None:
    line = "start([Start]) --> step[Do the work]"
    assert sanitize_mermaid_node_labels(line) == line


def test_closed_fence_body_is_quoted() -> None:
    raw = "```mermaid\nflowchart TD\n  D --> E[Grind Beans (Medium Grind)]\n```\n"
    out = sanitize_mermaid_fences(raw)
    assert 'E["Grind Beans (Medium Grind)"]' in out
    assert "E[Grind Beans (Medium Grind)]" not in out
    assert "```mermaid" in out
