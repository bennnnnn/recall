"""Tests for math fence validation."""

from app.services.math_fence import validate_math_fences


def test_validates_geometry_fence() -> None:
    content = '```geometry\n{"type":"rectangle","width":8,"height":5}\n```'
    assert validate_math_fences(content) == content


def test_validates_square_geometry_fence() -> None:
    content = '```geometry\n{"type":"square","side":5,"show_area":true}\n```'
    assert validate_math_fences(content) == content


def test_validates_rect_geometry_fence() -> None:
    content = '```geometry\n{"type":"rect","width":8,"height":5}\n```'
    assert validate_math_fences(content) == content


def test_validates_triangle_geometry_fence() -> None:
    content = '```geometry\n{"type":"triangle","base":8,"height":5}\n```'
    assert validate_math_fences(content) == content


def test_validates_right_triangle_geometry_fence() -> None:
    content = (
        '```geometry\n{"type":"right_triangle","base":6,"height":4,"show_hypotenuse":true}\n```'
    )
    assert validate_math_fences(content) == content


def test_replaces_invalid_geometry_fence() -> None:
    content = "```geometry\n{bad json\n```"
    out = validate_math_fences(content)
    assert "Invalid geometry block" in out


def test_replaces_invalid_graph_fence_with_empty_points() -> None:
    content = '```graph\n{"type":"function","expr":"x","points":[]}\n```'
    out = validate_math_fences(content)
    assert "Invalid graph block" in out
