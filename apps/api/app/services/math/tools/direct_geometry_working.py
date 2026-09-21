"""Scan-friendly worked layouts for solver-verified geometry replies.

The geometry solver remains the source of every number.  This module only
turns its already validated dimensions and result into the familiar school
sequence: given values, requested quantity, named formula, and substitution.
"""

from __future__ import annotations

import math

from app.services.math.match.geometry import parse_solid
from app.services.math.match.literal_geometry import measurement_request


def _number(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    number = float(value)
    return number if math.isfinite(number) else None


def _display(value: float) -> str:
    """Keep significant decimals while never adding cosmetic trailing zeroes."""
    return format(value, ".12g")


def _unit(unit: object) -> str:
    text = unit if isinstance(unit, str) and unit else "units"
    safe = text.replace("\\", "").replace("{", "").replace("}", "")
    return rf"\mathrm{{{safe}}}"


def _given(label: str, symbol: str, value: float, unit: str) -> str:
    return rf"{label}: ${symbol} = {_display(value)}\,{_unit(unit)}$"


def _section(
    given: list[str],
    find: str,
    formula_name: str,
    formulas: list[str],
    substitutions: list[str],
) -> str:
    rows = ["**Given**", *given, "**Find**", find, "**Formula**", f"{formula_name}:"]
    rows.extend(f"${formula}$" for formula in formulas)
    rows.append("**Substitution**")
    rows.extend(f"${substitution}$" for substitution in substitutions)
    rows.append("**Answer**")
    return "\n\n".join(rows)


def _quantity(user_text: str) -> str | None:
    parsed = measurement_request(user_text)
    if parsed is None:
        return None
    quantity = parsed[0]
    return "surface area" if quantity == "total surface area" else quantity


def format_direct_geometry_working(
    user_text: str,
    spec: dict[str, object],
    answer: str,
) -> str | None:
    """Format one complete 2D measurement without recomputing its answer."""
    quantity = _quantity(user_text)
    kind = spec.get("type")
    unit_value = spec.get("unit")
    unit = unit_value if isinstance(unit_value, str) else "units"
    result = answer.strip()
    if not quantity or not result:
        return None

    if kind == "rectangle":
        width, height = _number(spec.get("width")), _number(spec.get("height"))
        if width is None or height is None:
            return None
        given = [_given("Width", "w", width, unit), _given("Height", "h", height, unit)]
        if quantity == "area":
            return _section(
                given,
                "Area ($A$)",
                "Rectangle area formula",
                [r"A = w \times h"],
                [rf"A = {_display(width)} \times {_display(height)} = {result}"],
            )
        if quantity == "perimeter":
            return _section(
                given,
                "Perimeter ($P$)",
                "Rectangle perimeter formula",
                [r"P = 2(w + h)"],
                [rf"P = 2({_display(width)} + {_display(height)}) = {result}"],
            )
        if quantity == "diagonal":
            return _section(
                given,
                "Diagonal ($d$)",
                "Pythagorean theorem",
                [r"d^2 = w^2 + h^2", r"d = \sqrt{w^2 + h^2}"],
                [
                    rf"d = \sqrt{{{_display(width)}^2 + {_display(height)}^2}}"
                    rf" = {result}"
                ],
            )

    if kind == "square":
        side = _number(spec.get("side"))
        if side is None:
            return None
        given = [_given("Side length", "s", side, unit)]
        if quantity == "area":
            return _section(
                given,
                "Area ($A$)",
                "Square area formula",
                [r"A = s^2"],
                [rf"A = {_display(side)}^2 = {result}"],
            )
        if quantity == "perimeter":
            return _section(
                given,
                "Perimeter ($P$)",
                "Square perimeter formula",
                [r"P = 4s"],
                [rf"P = 4 \times {_display(side)} = {result}"],
            )
        if quantity == "diagonal":
            return _section(
                given,
                "Diagonal ($d$)",
                "Pythagorean theorem",
                [r"d^2 = s^2 + s^2", r"d = s\sqrt{2}"],
                [rf"d = {_display(side)}\sqrt{{2}} = {result}"],
            )

    if kind in {"triangle", "right_triangle"}:
        base, height = _number(spec.get("base")), _number(spec.get("height"))
        if base is None or height is None:
            return None
        given = [_given("Base", "b", base, unit), _given("Height", "h", height, unit)]
        if quantity == "area":
            return _section(
                given,
                "Area ($A$)",
                "Triangle area formula",
                [r"A = \frac{1}{2}bh"],
                [
                    rf"A = \frac{{1}}{{2}} \times {_display(base)} \times "
                    rf"{_display(height)} = {result}"
                ],
            )
        hypotenuse = _number(spec.get("hypotenuse"))
        if kind == "right_triangle" and hypotenuse is not None and quantity == "hypotenuse":
            return _section(
                given,
                "Hypotenuse ($c$)",
                "Pythagorean theorem",
                [r"c^2 = a^2 + b^2", r"c = \sqrt{a^2 + b^2}"],
                [
                    rf"c = \sqrt{{{_display(base)}^2 + {_display(height)}^2}}"
                    rf" = {result}"
                ],
            )
        if kind == "right_triangle" and hypotenuse is not None and quantity == "perimeter":
            return _section(
                given,
                "Perimeter ($P$)",
                "Right-triangle perimeter formula",
                [r"c = \sqrt{a^2 + b^2}", r"P = a + b + c"],
                [
                    rf"c = \sqrt{{{_display(base)}^2 + {_display(height)}^2}}"
                    rf" = {_display(hypotenuse)}",
                    rf"P = {_display(base)} + {_display(height)} + "
                    rf"{_display(hypotenuse)} = {result}",
                ],
            )

    if kind == "triangle_sides":
        sides = [_number(spec.get(key)) for key in ("a", "b", "c")]
        if any(side is None for side in sides):
            return None
        a, b, c = (float(side) for side in sides if side is not None)
        given = [
            _given("Side", "a", a, unit),
            _given("Side", "b", b, unit),
            _given("Side", "c", c, unit),
        ]
        if quantity == "perimeter":
            return _section(
                given,
                "Perimeter ($P$)",
                "Triangle perimeter formula",
                [r"P = a + b + c"],
                [rf"P = {_display(a)} + {_display(b)} + {_display(c)} = {result}"],
            )
        if quantity == "area":
            semiperimeter = (a + b + c) / 2
            s = _display(semiperimeter)
            return _section(
                given,
                "Area ($A$)",
                "Heron's formula",
                [r"s = \frac{a+b+c}{2}", r"A = \sqrt{s(s-a)(s-b)(s-c)}"],
                [
                    rf"s = \frac{{{_display(a)}+{_display(b)}+{_display(c)}}}{{2}} = {s}",
                    rf"A = \sqrt{{{s}({s}-{_display(a)})({s}-{_display(b)})"
                    rf"({s}-{_display(c)})}} = {result}",
                ],
            )

    if kind == "parallelogram":
        base = _number(spec.get("base"))
        height = _number(spec.get("height"))
        side = _number(spec.get("side"))
        if base is None or height is None or side is None:
            return None
        given = [
            _given("Base", "b", base, unit),
            _given("Height", "h", height, unit),
            _given("Side", "s", side, unit),
        ]
        if quantity == "area":
            return _section(
                given,
                "Area ($A$)",
                "Parallelogram area formula",
                [r"A = bh"],
                [rf"A = {_display(base)} \times {_display(height)} = {result}"],
            )
        if quantity == "perimeter":
            return _section(
                given,
                "Perimeter ($P$)",
                "Parallelogram perimeter formula",
                [r"P = 2(b+s)"],
                [rf"P = 2({_display(base)} + {_display(side)}) = {result}"],
            )

    if kind == "trapezoid" and quantity == "area":
        top = _number(spec.get("top"))
        bottom = _number(spec.get("bottom"))
        height = _number(spec.get("height"))
        if top is None or bottom is None or height is None:
            return None
        return _section(
            [
                _given("Top base", "a", top, unit),
                _given("Bottom base", "b", bottom, unit),
                _given("Height", "h", height, unit),
            ],
            "Area ($A$)",
            "Trapezoid area formula",
            [r"A = \frac{1}{2}(a+b)h"],
            [
                rf"A = \frac{{1}}{{2}}({_display(top)}+{_display(bottom)})"
                rf" \times {_display(height)} = {result}"
            ],
        )

    if kind == "circle":
        radius = _number(spec.get("radius"))
        if radius is None:
            return None
        supplied_diameter = "diameter" in user_text.lower()
        diameter = radius * 2
        given = [
            _given("Diameter", "d", diameter, unit)
            if supplied_diameter
            else _given("Radius", "r", radius, unit)
        ]
        radius_step = [rf"r = \frac{{{_display(diameter)}}}{{2}} = {_display(radius)}"]
        if quantity == "area":
            substitutions = radius_step if supplied_diameter else []
            substitutions.append(rf"A = \pi({_display(radius)})^2 \approx {result}")
            formulas = [r"A = \pi r^2"]
            if supplied_diameter:
                formulas.insert(0, r"d = 2r")
            return _section(given, "Area ($A$)", "Circle area formula", formulas, substitutions)
        if quantity == "circumference":
            substitutions = radius_step if supplied_diameter else []
            substitutions.append(rf"C = 2\pi({_display(radius)}) \approx {result}")
            formulas = [r"C = 2\pi r"]
            if supplied_diameter:
                formulas.insert(0, r"d = 2r")
            return _section(
                given,
                "Circumference ($C$)",
                "Circle circumference formula",
                formulas,
                substitutions,
            )
        if quantity == "diameter":
            return _section(
                given,
                "Diameter ($d$)",
                "Radius-diameter relation",
                [r"d = 2r"],
                [rf"d = 2 \times {_display(radius)} = {result}"],
            )

    if kind == "sector":
        radius = _number(spec.get("radius"))
        angle = _number(spec.get("angle_deg"))
        if radius is None or angle is None:
            return None
        given = [
            _given("Radius", "r", radius, unit),
            rf"Central angle: $\theta = {_display(angle)}^\circ$",
        ]
        if quantity == "area":
            return _section(
                given,
                "Sector area ($A$)",
                "Sector area formula",
                [r"A = \frac{\theta}{360^\circ}\pi r^2"],
                [
                    rf"A = \frac{{{_display(angle)}^\circ}}{{360^\circ}}"
                    rf"\pi({_display(radius)})^2 \approx {result}"
                ],
            )
        if quantity == "arc length":
            return _section(
                given,
                "Arc length ($L$)",
                "Arc-length formula",
                [r"L = \frac{\theta}{360^\circ}(2\pi r)"],
                [
                    rf"L = \frac{{{_display(angle)}^\circ}}{{360^\circ}}"
                    rf"(2\pi \times {_display(radius)}) \approx {result}"
                ],
            )
    return None


def format_direct_solid_working(user_text: str, answer: str) -> str | None:
    """Apply the same worked hierarchy to supported 3D measurements."""
    parsed = parse_solid(user_text)
    quantity = _quantity(user_text)
    if parsed is None or quantity not in {"volume", "surface area"}:
        return None
    unit = parsed.unit
    result = answer.strip()
    shape = parsed.shape

    if shape == "cube" and parsed.side is not None:
        side = parsed.side
        if quantity == "volume":
            return _section(
                [_given("Side length", "s", side, unit)],
                "Volume ($V$)",
                "Cube volume formula",
                [r"V = s^3"],
                [rf"V = {_display(side)}^3 = {result}"],
            )
        return _section(
            [_given("Side length", "s", side, unit)],
            "Surface area ($S$)",
            "Cube surface-area formula",
            [r"S = 6s^2"],
            [rf"S = 6({_display(side)})^2 = {result}"],
        )

    if (
        shape == "rectangular_prism"
        and parsed.width is not None
        and parsed.depth is not None
        and parsed.height is not None
    ):
        length = parsed.width
        width = parsed.depth
        height = parsed.height
        given = [
            _given("Length", "l", length, unit),
            _given("Width", "w", width, unit),
            _given("Height", "h", height, unit),
        ]
        if quantity == "volume":
            return _section(
                given,
                "Volume ($V$)",
                "Rectangular-prism volume formula",
                [r"V = lwh"],
                [
                    rf"V = {_display(length)} \times {_display(width)} \times "
                    rf"{_display(height)} = {result}"
                ],
            )
        return _section(
            given,
            "Surface area ($S$)",
            "Rectangular-prism surface-area formula",
            [r"S = 2(lw+lh+wh)"],
            [
                rf"S = 2({_display(length)}\times{_display(width)} + "
                rf"{_display(length)}\times{_display(height)} + "
                rf"{_display(width)}\times{_display(height)}) = {result}"
            ],
        )

    if shape in {"cylinder", "cone"} and parsed.radius is not None and parsed.height is not None:
        radius, height = parsed.radius, parsed.height
        given = [_given("Radius", "r", radius, unit), _given("Height", "h", height, unit)]
        if shape == "cylinder" and quantity == "volume":
            return _section(
                given,
                "Volume ($V$)",
                "Cylinder volume formula",
                [r"V = \pi r^2h"],
                [rf"V = \pi({_display(radius)})^2({_display(height)}) \approx {result}"],
            )
        if shape == "cylinder":
            return _section(
                given,
                "Surface area ($S$)",
                "Closed-cylinder surface-area formula",
                [r"S = 2\pi r(r+h)"],
                [
                    rf"S = 2\pi({_display(radius)})({_display(radius)}+{_display(height)})"
                    rf" \approx {result}"
                ],
            )
        if quantity == "volume":
            return _section(
                given,
                "Volume ($V$)",
                "Cone volume formula",
                [r"V = \frac{1}{3}\pi r^2h"],
                [
                    rf"V = \frac{{1}}{{3}}\pi({_display(radius)})^2({_display(height)})"
                    rf" \approx {result}"
                ],
            )
        slant = math.hypot(radius, height)
        return _section(
            given,
            "Surface area ($S$)",
            "Cone surface-area formula",
            [r"l = \sqrt{r^2+h^2}", r"S = \pi r(r+l)"],
            [
                rf"l = \sqrt{{{_display(radius)}^2+{_display(height)}^2}}"
                rf" = {_display(slant)}",
                rf"S = \pi({_display(radius)})({_display(radius)}+{_display(slant)})"
                rf" \approx {result}",
            ],
        )

    if shape == "sphere" and parsed.radius is not None:
        radius = parsed.radius
        if quantity == "volume":
            return _section(
                [_given("Radius", "r", radius, unit)],
                "Volume ($V$)",
                "Sphere volume formula",
                [r"V = \frac{4}{3}\pi r^3"],
                [rf"V = \frac{{4}}{{3}}\pi({_display(radius)})^3 \approx {result}"],
            )
        return _section(
            [_given("Radius", "r", radius, unit)],
            "Surface area ($S$)",
            "Sphere surface-area formula",
            [r"S = 4\pi r^2"],
            [rf"S = 4\pi({_display(radius)})^2 \approx {result}"],
        )

    if shape == "pyramid" and parsed.side is not None and parsed.height is not None:
        side, height = parsed.side, parsed.height
        given = [_given("Base side", "s", side, unit), _given("Height", "h", height, unit)]
        if quantity == "volume":
            return _section(
                given,
                "Volume ($V$)",
                "Square-pyramid volume formula",
                [r"V = \frac{1}{3}s^2h"],
                [
                    rf"V = \frac{{1}}{{3}}({_display(side)})^2({_display(height)})"
                    rf" = {result}"
                ],
            )
        slant = math.hypot(height, side / 2)
        return _section(
            given,
            "Surface area ($S$)",
            "Square-pyramid surface-area formula",
            [r"l = \sqrt{h^2+(s/2)^2}", r"S = s^2+2sl"],
            [
                rf"l = \sqrt{{{_display(height)}^2+({_display(side)}/2)^2}}"
                rf" = {_display(slant)}",
                rf"S = {_display(side)}^2 + 2({_display(side)})({_display(slant)})"
                rf" = {result}",
            ],
        )
    return None
