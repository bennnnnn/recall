"""Tests for math fence validation."""

import json

from app.models.math_schemas import GraphBlockSpec
from app.services.math_fence import densify_sparse_graph, validate_math_fences


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


def test_empty_points_graph_fence_is_sampled_from_expr() -> None:
    """The model often emits ```graph with expr but no points (it copies the
    schema without the verified sample). Resample from expr instead of
    stripping to 'Could not render that diagram.'"""
    content = '```graph\n{"type":"function","expr":"3*x+4","points":[]}\n```'
    out = validate_math_fences(content)
    assert "Could not render that diagram" not in out
    i = out.find("```graph\n")
    assert i != -1
    j = out.find("\n```", i)
    spec = json.loads(out[i + 8 : j])
    assert spec["type"] == "function"
    assert len(spec["points"]) >= 2
    x0, y0 = spec["points"][len(spec["points"]) // 2]
    assert abs(y0 - (3.0 * x0 + 4.0)) < 1e-4


def test_invalid_graph_json_still_strips() -> None:
    content = "```graph\n{bad json\n```"
    out = validate_math_fences(content)
    assert "Could not render that diagram" in out
    assert "Invalid graph block" not in out


def test_vertical_line_graph_fence_validates() -> None:
    content = '```graph\n{"type":"vertical","x":4,"y_min":-5,"y_max":5,"title":"x = 4"}\n```'
    assert validate_math_fences(content) == content


def test_replaces_truncated_unclosed_graph_fence_with_canonical() -> None:
    """Regression: a weak model often stops copying the verified points array
    mid-way (EOS at ~30 of 96 points), leaving a ```graph fence with no closing
    ```. _GRAPH_FENCE requires a closing fence, so the truncated JSON reached
    the client and rendered as "Could not render function graph." When this
    turn has a verified canonical fence, swap the truncated tail for the
    complete fence."""
    from app.core.config import get_settings
    from app.services.math_tools.prompt import build_math_augmentation

    settings = get_settings()
    import asyncio

    block, verified = asyncio.run(build_math_augmentation("Graph x^2", settings, needs_math=True))
    assert verified is not None and verified.canonical_fence is not None
    canonical = verified.canonical_fence
    assert canonical["type"] == "function"
    full_points = canonical["points"]
    # Simulate the model truncating the fence mid-points-array (no closing ```).
    truncated_json = json.dumps(canonical)
    cut = truncated_json[: truncated_json.find(",[-3.") + 5]
    content = "Here's the graph for $x^2$:\n\n```graph\n" + cut
    out = validate_math_fences(content, verified=verified)
    i = out.find("```graph\n")
    assert i != -1, "graph fence missing from output"
    j = out.find("\n```", i)
    assert j != -1, "fence not closed"
    out_json = out[i + 8 : j]
    out_spec = json.loads(out_json)
    assert out_spec["type"] == "function"
    assert out_spec["expr"] == "x**2"
    assert len(out_spec["points"]) == len(full_points)
    assert "Could not render" not in out


def test_truncated_unclosed_graph_fence_without_canonical_strips_json() -> None:
    """With no verified canonical fence, a truncated unclosed ```graph fence is
    stripped to 'Could not render that diagram.' rather than leaking the raw
    half-pasted points array."""
    content = "```graph\n" + '{"type":"function","expr":"x**2","points":[[-10,100],[-9,81'
    out = validate_math_fences(content)
    assert "Could not render that diagram" in out
    assert "[-10,100" not in out


def test_replace_unclosed_graph_fence_safe_substitutes_canonical_without_sympy() -> None:
    """Timeout-fallback path: substitute a verified canonical fence SymPy-free
    (no densify) so a truncated graph fence doesn't leak raw JSON to the client
    when validate_math_fences was killed by the solve timeout."""
    from app.services.math_fence import replace_unclosed_graph_fence_safe

    canonical_points: list[list[float]] = [[-10.0, 100.0], [0.0, 0.0], [10.0, 100.0]]
    canonical: dict[str, object] = {
        "type": "function",
        "expr": "x**2",
        "variable": "x",
        "x_min": -10.0,
        "x_max": 10.0,
        "points": canonical_points,
    }
    truncated = "```graph\n" + json.dumps(canonical)[: json.dumps(canonical).find(",[0.0") + 5]
    out = replace_unclosed_graph_fence_safe(truncated, canonical)
    assert "Could not render" not in out
    i = out.find("```graph\n")
    assert i != -1
    j = out.find("\n```", i)
    assert j != -1, "safe fallback must close the fence"
    spec = json.loads(out[i + 8 : j])
    assert spec["type"] == "function"
    assert spec["expr"] == "x**2"
    # Canonical fence substituted as-is (no densify re-sample).
    out_points: list = spec["points"]
    assert len(out_points) == len(canonical_points)


def test_replace_unclosed_graph_fence_safe_strips_when_no_canonical() -> None:
    """No verified canonical fence → strip the truncated tail to the error note."""
    from app.services.math_fence import replace_unclosed_graph_fence_safe

    content = "```graph\n" + '{"type":"function","expr":"x**2","points":[[-10,100],[-9,81'
    out = replace_unclosed_graph_fence_safe(content, None)
    assert "Could not render that diagram" in out
    assert "[-10,100" not in out


def test_replace_unclosed_graph_fence_safe_noop_when_no_unclosed_fence() -> None:
    """No unclosed fence → return content unchanged (no SymPy, no rewrite)."""
    from app.services.math_fence import replace_unclosed_graph_fence_safe

    content = "Just prose, no graph fence at all."
    assert replace_unclosed_graph_fence_safe(content, None) == content


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


def test_corrects_trajectory_fence_to_canonical_points() -> None:
    points = [[i * 2.1 / 99, max(0.0, 20.0 - 4.905 * (i * 2.1 / 99) ** 2)] for i in range(100)]
    canonical = {
        "type": "trajectory",
        "expr": "h(t) = 20 - 0.5*9.81*t^2",
        "variable": "t",
        "x_min": 0.0,
        "x_max": 2.0,
        "points": points,
        "title": "Height vs. Time",
        "x_label": "Time (s)",
        "y_label": "Height (m)",
        "trajectory_type": "position_vs_time",
    }
    content = (
        '```graph\n{"type":"trajectory","expr":"h(t)=99","points":[[0,99],[1,99]],'
        '"title":"Wrong trajectory"}\n```'
    )

    out = validate_math_fences(content, verified=_verified(canonical))

    fence = out.split("```graph")[1].split("```")[0].strip()
    data = json.loads(fence)
    assert data["points"] == points
    assert data["title"] == "Height vs. Time"
    assert data["trajectory_type"] == "position_vs_time"


def test_densify_leaves_sparse_trajectory_points_unchanged() -> None:
    spec = GraphBlockSpec(
        type="trajectory",
        expr="h(t) = 20 - 0.5*9.81*t^2",
        variable="t",
        points=[[0.0, 20.0], [1.0, 15.095], [2.0, 0.38]],
        trajectory_type="position_vs_time",
    )

    assert densify_sparse_graph(spec) is spec


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


def test_result_fence_is_not_rewritten_as_math_answer() -> None:
    content = "```result\nAll 12 tests passed\n```"
    out = validate_math_fences(
        content,
        verified=_verified({"type": "answer", "content": "x = 4"}),
    )
    assert "All 12 tests passed" in out
    assert "```result" in out


def test_unclosed_graph_does_not_swallow_following_python_fence() -> None:
    content = (
        'See the plot:\n\n```graph\n{"type":"function","expr":"x"\n'
        "then the code:\n\n```python\nprint(1)\n```"
    )
    out = validate_math_fences(content)
    assert "print(1)" in out
    assert "```python" in out
    assert "Could not render that diagram" in out


def test_leaves_answer_fence_when_canonical_is_geometry() -> None:
    """Wrong-kind canonical must not clobber an ```answer body; geometry is appended."""
    content = "```answer\nx = 2\n```"
    out = validate_math_fences(
        content,
        verified=_verified({"type": "rectangle", "width": 8, "height": 5}),
    )
    assert "```answer\nx = 2\n```" in out
    assert "```geometry" in out
    assert '"type":"rectangle"' in out.replace(" ", "")


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

    bad_graph = "```graph\n{bad json\n```"
    graphs = "\n".join([bad_graph] * (_MAX_GRAPH_FENCES + 1))
    out_graph = validate_math_fences(graphs)
    assert out_graph.count("Could not render that diagram") == _MAX_GRAPH_FENCES
    assert out_graph.count("```graph") == 1


def test_converts_function_call_graph_text_to_fence() -> None:
    """A weak model emitted a tool call as TEXT (!function_call:{...}) instead
    of the structured tool_calls API, so the raw string reached the user.
    validate_math_fences must sample the expr server-side and replace it with a
    real ```graph fence (with points) so the renderer has a curve to draw."""
    content = (
        "Let me retry plotting x = 2y for you.\n\n"
        '!function_call:{"id": "call_DDKdZyJUmQWPSJVPyQNm7OyN", '
        '"call": "graph", "arguments": {"expr": "y=x/2", "variable": "x", '
        '"title": "Graph of x = 2y", "x_min": -10.0, "x_max": 10.0, '
        '"y_min": -5.0, "y_max": 5.0}}'
    )

    out = validate_math_fences(content)

    assert "!function_call" not in out
    assert "```graph" in out
    fence = out.split("```graph")[1].split("```")[0].strip()
    data = json.loads(fence)
    assert data["type"] == "function"
    assert data["expr"] == "x/2"
    assert len(data["points"]) >= 48  # densified into a real curve


def test_strips_non_graph_function_call_text() -> None:
    """A non-graph !function_call blob must be stripped, not shown as raw text."""
    content = '!function_call:{"call": "web_search", "arguments": {"query": "weather"}}'
    out = validate_math_fences(content)
    assert "!function_call" not in out
    assert "web_search" not in out


def test_appends_canonical_answer_when_model_omits_fence() -> None:
    verified = _verified({"type": "answer", "content": "x = 2"})
    out = validate_math_fences("The solution follows from the steps above.", verified=verified)
    assert "```answer\nx = 2\n```" in out


def test_does_not_append_answer_when_prose_already_has_math_result() -> None:
    verified = _verified({"type": "answer", "content": "x = 2"})
    out = validate_math_fences("The solution is $x = 2$.", verified=verified)
    assert "```answer" not in out


def test_appends_canonical_geometry_when_model_omits_fence() -> None:
    spec = {"type": "rectangle", "width": 8, "height": 5}
    out = validate_math_fences("Here is a rectangle.", verified=_verified(spec))
    assert "```geometry" in out
    assert '"type":"rectangle"' in out.replace(" ", "")
    assert "```geometry\n" not in "Here is a rectangle."


def test_appends_canonical_graph_when_model_omits_fence() -> None:
    spec = {
        "type": "function",
        "expr": "x**2",
        "variable": "x",
        "x_min": -2,
        "x_max": 2,
        "points": [[-2, 4], [0, 0], [2, 4]],
    }
    out = validate_math_fences("Here is the parabola.", verified=_verified(spec))
    assert "```graph" in out
    fence = out.split("```graph")[1].split("```")[0].strip()
    data = json.loads(fence)
    assert data["type"] == "function"
    assert data["expr"] == "x**2"


def test_appends_answer_and_graph_for_physics() -> None:
    from app.services.math_tools import VerifiedMathBlock

    spec = {
        "type": "trajectory",
        "expr": "h(t)",
        "points": [[0, 20], [1, 15]],
    }
    verified = VerifiedMathBlock(
        text="unused",
        canonical_fence=spec,
        canonical_answer="2.02 s",
    )
    out = validate_math_fences("The ball lands at $t = 2.02$ s.", verified=verified)
    assert "```answer" not in out
    assert "```graph" in out
    assert json.loads(out.split("```graph")[1].split("```")[0].strip())["type"] == "trajectory"


def test_appends_answer_when_prose_omits_verified_value() -> None:
    verified = _verified({"type": "answer", "content": "x = 12"})
    out = validate_math_fences("Worked steps follow.", verified=verified)
    assert "```answer\nx = 12\n```" in out


def test_skips_answer_pill_when_prose_already_states_result() -> None:
    verified = _verified({"type": "answer", "content": "2.02 s"})
    out = validate_math_fences("The ball lands at $t = 2.02$ s.", verified=verified)
    assert "```answer" not in out


def test_draw_geometry_without_canonical_answer_does_not_append_pill() -> None:
    from app.services.math_tools import VerifiedMathBlock

    verified = VerifiedMathBlock(
        text="unused",
        canonical_fence={
            "type": "right_triangle",
            "base": 3,
            "height": 4,
            "show_hypotenuse": True,
        },
        canonical_answer=None,
    )
    out = validate_math_fences("Here's the right triangle.", verified=verified)
    assert "```answer" not in out
    assert "```geometry" in out


def test_short_integer_in_exponent_does_not_suppress_answer_pill() -> None:
    verified = _verified({"type": "answer", "content": "2"})
    out = validate_math_fences("Consider $x^2$ for this problem.", verified=verified)
    assert "```answer\n2\n```" in out


def test_one_line_arithmetic_does_not_append_duplicate_answer() -> None:
    verified = _verified({"type": "answer", "content": "3"})
    out = validate_math_fences("$3 + 0 = 3$", verified=verified)
    assert "```answer" not in out


def test_does_not_duplicate_existing_answer_fence() -> None:
    verified = _verified({"type": "answer", "content": "x = 2"})
    content = "Worked steps…\n```answer\nx = 99\n```"
    out = validate_math_fences(content, verified=verified)
    assert out.count("```answer") == 1
    assert "```answer\nx = 2\n```" in out
    assert "x = 99" not in out


def test_append_unverified_math_note_once() -> None:
    from app.services.math_fence import append_unverified_math_note

    labeled = append_unverified_math_note("The roots are $x=1$.")
    assert labeled.endswith("*Couldn't verify this with SymPy.*")
    assert append_unverified_math_note(labeled) == labeled
