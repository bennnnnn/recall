"""Regression tests for server-owned verified response blocks."""

from app.services.chat.verified_output import (
    enforce_verified_output_contract,
    validate_math_fences_worker,
)
from app.services.math_tools.block.common import VerifiedMathBlock


def test_unverified_output_is_unchanged() -> None:
    content = "Normal **Markdown** with $x^2$ and a list."
    assert enforce_verified_output_contract(content, None) == content


def test_verified_answer_replaces_model_answer() -> None:
    verified = VerifiedMathBlock(
        text="",
        canonical_fence={"type": "answer", "content": "4"},
        canonical_answer="4",
    )
    content = "Subtract 2 first.\n\n```answer\n5\n```"

    out = enforce_verified_output_contract(content, verified)

    assert "```answer\n5\n```" not in out
    assert out.endswith("```answer\n4\n```")
    assert out.count("```answer") == 1
    assert out.startswith("Subtract 2 first.")


def test_verified_answer_is_added_when_model_omits_fence() -> None:
    verified = VerifiedMathBlock(
        text="",
        canonical_fence={"type": "answer", "content": r"x = \pm 2"},
        canonical_answer=r"x = \pm 2",
    )

    out = validate_math_fences_worker("Taking square roots gives both solutions.", verified)

    assert out.endswith("```answer\nx = \\pm 2\n```")
    assert out.count("```answer") == 1


def test_verified_graph_and_answer_are_server_owned() -> None:
    graph = {
        "type": "vertical",
        "expr": "x = 4",
        "x": 4.0,
        "y_min": -10.0,
        "y_max": 10.0,
        "title": "x = 4",
    }
    verified = VerifiedMathBlock(
        text="",
        canonical_fence=graph,
        canonical_answer="4",
    )
    content = (
        "The graph is a vertical line.\n\n"
        "```graph\n{\"type\":\"vertical\",\"x\":99}\n```\n\n"
        "```answer\n99\n```"
    )

    out = enforce_verified_output_contract(content, verified)

    assert '"x":99' not in out
    assert '"x":4.0' in out
    assert out.count("```graph") == 1
    assert out.count("```answer") == 1
    assert out.endswith("```answer\n4\n```")


def test_truncated_server_owned_tail_is_removed_before_canonical_block() -> None:
    graph = {
        "type": "number_line",
        "expr": "x > 3",
        "title": "x > 3",
        "intervals": [
            {
                "start": 3,
                "end": None,
                "start_inclusive": False,
                "end_inclusive": False,
            }
        ],
    }
    verified = VerifiedMathBlock(text="", canonical_fence=graph)
    content = 'The solution is to the right of 3.\n\n```graph\n{"type":"function","expr":"x > 3"'

    out = enforce_verified_output_contract(content, verified)

    assert '"type":"function"' not in out
    assert out.count("```graph") == 1
    assert '"type":"number_line"' in out
    assert out.endswith("```")


def test_duplicate_canonical_diagram_is_emitted_once() -> None:
    graph = {
        "type": "vertical",
        "expr": "x = 2",
        "x": 2.0,
        "y_min": -5.0,
        "y_max": 5.0,
    }
    verified = VerifiedMathBlock(
        text="",
        canonical_fence=graph,
        canonical_fences=[graph],
    )

    out = enforce_verified_output_contract("A vertical line.", verified)

    assert out.count("```graph") == 1
