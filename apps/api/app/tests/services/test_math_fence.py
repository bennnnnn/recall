"""Tests for math fence validation."""

import json

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


def test_validates_circle_geometry_fence() -> None:
    """BUG FIX regression: circles were never a recognized geometry kind —
    the model's own ```geometry {"type":"circle",...} fence (there was no
    verified-math augmentation to guide it, since the schema/prompt never
    mentioned circles) got rejected here and replaced with the
    "[!WARNING] Invalid geometry block" fallback text instead of rendering.
    """
    content = (
        '```geometry\n{"type":"circle","radius":4,"show_diameter":true,'
        '"show_area":true,"show_circumference":true}\n```'
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


def test_validates_single_point_graph_fence() -> None:
    """BUG FIX regression: marking a single coordinate (e.g. "plot the
    point (2, 3)") is a legitimate single-point graph, not an error."""
    content = (
        '```graph\n{"type":"function","expr":"(2, 3)","title":"Point (2, 3)","points":[[2,3]]}\n```'
    )
    assert validate_math_fences(content) == content


def _verified(canonical_fence):
    from app.services.math_tools import VerifiedMathBlock

    return VerifiedMathBlock(text="unused", canonical_fence=canonical_fence)


def test_corrects_hallucinated_geometry_values_to_canonical() -> None:
    """The model claimed a wrong diagonal — the real computed value must win."""
    canonical = {
        "type": "rectangle",
        "width": 8,
        "height": 5,
        "diagonal": 9.434,
        "angle_deg": 32.0,
    }
    # Model's own fence: same kind, but wrong (hallucinated) diagonal.
    content = '```geometry\n{"type":"rectangle","width":8,"height":5,"diagonal":99}\n```'

    out = validate_math_fences(content, verified=_verified(canonical))

    assert '"diagonal":9.434' in out
    assert '"diagonal":99' not in out


def test_corrects_graph_fence_to_canonical_points() -> None:
    canonical = {
        "type": "function",
        "expr": "x**2",
        "variable": "x",
        "x_min": -10.0,
        "x_max": 10.0,
        "points": [[0, 0], [1, 1]],
    }
    content = '```graph\n{"type":"function","expr":"x**2","points":[[0,0],[1,999]]}\n```'

    out = validate_math_fences(content, verified=_verified(canonical))

    assert "[1,1]" in out
    assert "[1,999]" not in out


def test_leaves_fence_alone_when_kind_differs_from_canonical() -> None:
    """A canonical rectangle shouldn't overwrite an unrelated square fence."""
    canonical = {"type": "rectangle", "width": 8, "height": 5}
    content = '```geometry\n{"type":"square","side":5}\n```'

    out = validate_math_fences(content, verified=_verified(canonical))

    assert out == content


def test_no_canonical_fence_falls_back_to_schema_validation_only() -> None:
    """Equation/calculus turns have no canonical fence (verified.canonical_fence
    is None) — a well-formed fence elsewhere in the response is untouched."""
    content = '```geometry\n{"type":"rectangle","width":8,"height":5}\n```'

    out = validate_math_fences(content, verified=_verified(None))

    assert out == content


def test_densifies_sparse_continuous_graph_fence() -> None:
    """BUG FIX: models often list only roots/intercepts in ```graph — a
    polyline through those looks like a V instead of the real curve."""
    content = (
        '```graph\n{"type":"function","expr":"x**4 - 4*x**2 - 12","variable":"x",'
        '"x_min":-3,"x_max":3,"points":[[-2,0],[0,-12],[2,0]]}\n```'
    )

    out = validate_math_fences(content)
    assert "```graph" in out
    assert "[-2,0],[0,-12],[2,0]" not in out.replace(" ", "")
    # Dense enough to draw a smooth W, not three straight segments.
    fence = out.split("```graph")[1].split("```")[0].strip()
    data = json.loads(fence)
    assert len(data["points"]) >= 48


def test_leaves_point_marker_graph_undensified() -> None:
    content = (
        '```graph\n{"type":"function","expr":"(2, 3)","title":"Point (2, 3)","points":[[2,3]]}\n```'
    )
    assert validate_math_fences(content) == content


def test_leaves_already_dense_graph_formatting_alone() -> None:
    points = [[float(i) / 10, (float(i) / 10) ** 2] for i in range(-50, 51)]
    payload = {
        "type": "function",
        "expr": "x**2",
        "variable": "x",
        "x_min": -5.0,
        "x_max": 5.0,
        "points": points,
    }
    content = f"```graph\n{json.dumps(payload)}\n```"
    assert validate_math_fences(content) == content
