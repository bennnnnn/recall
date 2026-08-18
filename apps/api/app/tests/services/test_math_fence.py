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
    assert "Could not render that diagram" in out
    assert "Invalid geometry block" not in out


def test_replaces_invalid_graph_fence_with_empty_points() -> None:
    content = '```graph\n{"type":"function","expr":"x","points":[]}\n```'
    out = validate_math_fences(content)
    assert "Could not render that diagram" in out
    assert "Invalid graph block" not in out


def test_vertical_line_graph_fence_validates() -> None:
    content = '```graph\n{"type":"vertical","x":4,"y_min":-5,"y_max":5,"title":"x = 4"}\n```'
    assert validate_math_fences(content) == content


def test_rewrites_unverified_inequality_step_to_number_line() -> None:
    content = (
        '```graph\n{"type":"function","expr":"x > 3","title":"x > 3 (number line)",'
        '"points":[[-10,0],[3,0],[3,1],[10,1]]}\n```'
    )
    out = validate_math_fences(content)
    fence = out.split("```graph")[1].split("```")[0].strip()
    data = json.loads(fence)
    assert data["type"] == "number_line"
    assert data["intervals"][0]["start"] == 3.0
    assert data["intervals"][0]["end"] is None
    assert data["title"] == "x > 3 (number line)"


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
    # Already-dense canonical — rewrite without densify churn.
    points = [[float(i) / 5, (float(i) / 5) ** 2] for i in range(-50, 51)]
    canonical = {
        "type": "function",
        "expr": "x**2",
        "variable": "x",
        "x_min": -10.0,
        "x_max": 10.0,
        "points": points,
    }
    content = '```graph\n{"type":"function","expr":"x**2","points":[[0,0],[1,999]]}\n```'

    out = validate_math_fences(content, verified=_verified(canonical))

    assert "[1,999]" not in out
    fence = out.split("```graph")[1].split("```")[0].strip()
    data = json.loads(fence)
    assert data["points"] == points


def test_corrects_points_less_function_fence_to_canonical() -> None:
    """The model often emits a ```graph fence with type=function but DROPS the
    points array (e.g. "Graph x=2y" → {"type":"function","expr":"x/2",...} with
    no points). validate_math_fences must substitute the verified canonical
    fence (with points) so the renderer has a curve to draw — and the rewritten
    text differs from the streamed draft, which is what lets the stream set
    final_content and the client re-render instead of showing
    "Could not render function graph."."""
    points = [[float(i) / 5, (float(i) / 5) / 2] for i in range(-50, 51)]
    canonical = {
        "type": "function",
        "expr": "x/2",
        "variable": "x",
        "x_min": -10.0,
        "x_max": 10.0,
        "points": points,
    }
    content = (
        '```graph\n{"type":"function","expr":"x/2","variable":"x",'
        '"x_min":-10.0,"x_max":10.0,"title":"x = 2y"}\n```'
    )

    out = validate_math_fences(content, verified=_verified(canonical))

    assert out != content  # rewritten → final_content would be set
    fence = out.split("```graph")[1].split("```")[0].strip()
    data = json.loads(fence)
    assert data["points"] == points


def test_leaves_fence_alone_when_kind_differs_from_canonical() -> None:
    """A canonical rectangle shouldn't overwrite an unrelated square fence."""
    canonical = {"type": "rectangle", "width": 8, "height": 5}
    content = '```geometry\n{"type":"square","side":5}\n```'

    out = validate_math_fences(content, verified=_verified(canonical))

    assert out == content


def test_no_canonical_fence_falls_back_to_schema_validation_only() -> None:
    """Turns without a canonical fence leave well-formed fences untouched."""
    content = '```geometry\n{"type":"rectangle","width":8,"height":5}\n```'

    out = validate_math_fences(content, verified=_verified(None))

    assert out == content


def test_rewrites_answer_fence_from_canonical() -> None:
    content = "Worked steps…\n```answer\nx = 99\n```"
    out = validate_math_fences(
        content,
        verified=_verified({"type": "answer", "content": "x = \\pm 2"}),
    )
    assert "```answer\nx = \\pm 2\n```" in out
    assert "x = 99" not in out


def test_leaves_answer_fence_when_canonical_is_geometry() -> None:
    """Wrong-kind canonical must not clobber an ```answer body."""
    content = "```answer\nx = 2\n```"
    out = validate_math_fences(
        content,
        verified=_verified({"type": "rectangle", "width": 8, "height": 5}),
    )
    assert out == content


def test_rewrites_answer_fence_when_geometry_has_canonical_answer() -> None:
    from app.services.math_tools import VerifiedMathBlock

    content = (
        '```geometry\n{"type":"rectangle","width":4,"height":5,"diagonal":99}\n```\n'
        "```answer\n99\n```"
    )
    verified = VerifiedMathBlock(
        text="unused",
        canonical_fence={
            "type": "rectangle",
            "width": 4,
            "height": 5,
            "area": 20,
            "diagonal": 6.403,
        },
        canonical_answer="20",
    )
    out = validate_math_fences(content, verified=verified)
    assert '"diagonal":6.403' in out
    assert '"diagonal":99' not in out
    assert "```answer\n20\n```" in out
    assert "```answer\n99\n```" not in out


def test_densifies_unverified_sparse_function_graph_fence() -> None:
    """Key-point sketches (vertex + intercepts) must be resampled so the
    client draws a curve, not a 3-point V. Point-marker fences stay sparse.
    """
    content = (
        '```graph\n{"type":"function","expr":"3*x**2 - 12","variable":"x",'
        '"x_min":-2,"x_max":2,"points":[[-2,0],[0,-12],[2,0]]}\n```'
    )

    out = validate_math_fences(content)
    fence = out.split("```graph")[1].split("```")[0].strip()
    data = json.loads(fence)
    assert len(data["points"]) >= 48
    assert data["expr"] == "3*x**2 - 12"


def test_densifies_sparse_canonical_graph_after_rewrite() -> None:
    """Verified sparse samples may still need densify — safe because expr
    came from SymPy, not the model's free-text fence."""
    canonical = {
        "type": "function",
        "expr": "x**4 - 4*x**2 - 12",
        "variable": "x",
        "x_min": -3.0,
        "x_max": 3.0,
        "points": [[-2.0, 0.0], [0.0, -12.0], [2.0, 0.0]],
    }
    # Model listed wrong y values — canonical wins, then densify.
    content = (
        '```graph\n{"type":"function","expr":"x**4 - 4*x**2 - 12","variable":"x",'
        '"x_min":-3,"x_max":3,"points":[[-2,0],[0,999],[2,0]]}\n```'
    )

    out = validate_math_fences(content, verified=_verified(canonical))
    assert "```graph" in out
    assert "[0,999]" not in out.replace(" ", "")
    fence = out.split("```graph")[1].split("```")[0].strip()
    data = json.loads(fence)
    assert len(data["points"]) >= 48


def test_leaves_point_marker_graph_undensified() -> None:
    content = (
        '```graph\n{"type":"function","expr":"(2, 3)","title":"Point (2, 3)","points":[[2,3]]}\n```'
    )
    assert validate_math_fences(content) == content


def test_sample_domain_unions_declared_window_and_key_points() -> None:
    """Default [-10,10] must expand when key points sit outside that window."""
    from app.models.math_schemas import GraphBlockSpec
    from app.services.math_fence import _sample_domain

    spec = GraphBlockSpec(
        type="function",
        expr="x**2",
        variable="x",
        x_min=-10.0,
        x_max=10.0,
        points=[[-2.0, 4.0], [25.0, 625.0]],
    )
    x_min, x_max = _sample_domain(spec)
    assert x_min <= -10.0
    assert x_max >= 25.0


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


def test_validate_math_fences_caps_per_kind() -> None:
    from app.services.math_fence import _MAX_GEOMETRY_FENCES, _MAX_GRAPH_FENCES

    bad_geo = "```geometry\n{bad json\n```"
    geo = "\n".join([bad_geo] * (_MAX_GEOMETRY_FENCES + 1))
    out_geo = validate_math_fences(geo)
    assert out_geo.count("Could not render that diagram") == _MAX_GEOMETRY_FENCES
    assert out_geo.count("```geometry") == 1

    bad_graph = '```graph\n{"type":"function","expr":"x","points":[]}\n```'
    graphs = "\n".join([bad_graph] * (_MAX_GRAPH_FENCES + 1))
    out_graph = validate_math_fences(graphs)
    assert out_graph.count("Could not render that diagram") == _MAX_GRAPH_FENCES
    assert out_graph.count("```graph") == 1
