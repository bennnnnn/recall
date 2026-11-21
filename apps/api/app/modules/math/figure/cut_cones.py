"""A cone cut parallel to its base: the frustum left, and the small cone cut off its top.

The small cone is similar to the whole one, so its height and radius are the same share k
of the whole cone's, and the frustum is (1 - k) of its height tall. A question gives the
whole cone's sizes, the small cone's, or the frustum's ("the original cone has height 24 cm
and base radius 12 cm; the smaller cone removed has height 8 cm"): values that fix k and the
whole cone's size draw the figure, every one of them true to scale and the ones it asks for
(the top radius, the frustum's height) unlabelled. Values that disagree, or that leave where
the cut is open, draw nothing.

Which cone a value is of is what the question writes it of, the cone named last before it in
its sentence: "the original cone", "a cone" is the whole one; "the smaller cone", "the cone
removed" the small one; "the frustum", "a frustum of a cone" the frustum. The words after a
height say so too ("8 cm from the top": the small cone's; "8 cm above the base": the
frustum's). The read's own tag (``of``) counts where the words say nothing or name a cone
without saying which ("a cone ... cut 10 cm from its top"), and a frustum given by its own
ends and height is left to ``frustums``. The figure is the whole
cone with the part cut off dashed above the frustum, the cut drawn whole, the axis dashed in
two (the small cone's height, the frustum's) and the whole cone's height beside it.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from itertools import product

from app.modules.math.figure.drawing import Drawing, length_label
from app.modules.math.figure.projection import ELLIPSE
from app.modules.math.figure.request import FigureRequest, Measure
from app.modules.math.figure.solids import round_base
from app.modules.math.schemas.figure import FigureSpec

# What a measure is of, once read: the whole cone, the cone cut off, the frustum.
WHOLE, CUT, FRUSTUM = "whole_cone", "cut_cone", "frustum"
_ROLES = frozenset({WHOLE, CUT, FRUSTUM})
_SHAPES = frozenset({"frustum", "cone_frustum", "truncated_cone", "cone"})
_CUT_WORDS = re.compile(r"\b(?:small\w*|remov\w*|cut[- ]off|little|tiny|top|upper)\b")
_WHOLE_WORDS = re.compile(r"\b(?:original|larg\w*|big\w*|whole|full|complete|entire|initial)\b")
_NOUN = re.compile(r"\b(?:frust\w*|cones?)\b")
_FRUSTUM_OF = re.compile(r"\bfrust\w* of (?:a|the) (?:right )?(?:circular )?$")
_AFTER_CUT = re.compile(
    r"^\s*(?:[a-z]+\s+)?(?:from|below)\s+(?:(?:the|its)\s+)?(?:top|apex|vertex|tip)\b"
)
_AFTER_FRUSTUM = re.compile(
    r"^\s*(?:[a-z]+\s+)?(?:from|above)\s+(?:(?:the|its)\s+)?(?:base|bottom)\b"
)
# A cone the words name with nothing to say which: the whole one, unless the read says.
_SOME_CONE = "some_cone"
_UNIT = re.compile(r"^\s*(?:mm|cm|m|km|in|ft)\b")
_BASE_END = re.compile(r"\b(?:base|bottom|lower)\b")
_TOP_END = re.compile(r"\b(?:top|upper)\b")
_OF_STEMS = {
    WHOLE: ("original", "large", "big", "whole", "full"),
    CUT: ("small", "remov", "cut"),
    FRUSTUM: ("frustum",),
}
# A length along the axis is a height: "cut 10 cm from its top" read as a length or a
# distance is the cut-off cone's height (2026-11-21).
_ALONG = frozenset({"height", "length", "distance"})
_TOLERANCE = 1e-4
_HEIGHT = 2.0  # the whole cone's height against its radius, when the question leaves it
_BESIDE = 1.3


def _named_cone(prefix: str) -> str | None:
    """The cone the last one the words name is: "the smaller cone removed has height" the
    cut one, "the original cone" the whole, "a frustum of a cone" the frustum; "a cone"
    names one without saying which."""
    nouns = list(_NOUN.finditer(prefix))
    if not nouns:
        return None
    noun = nouns[-1]
    if noun.group().startswith("frust") or _FRUSTUM_OF.search(prefix[: noun.start()]):
        return FRUSTUM
    # The words about it: the two before it ("the smaller cone") and those after it.
    before = prefix[: noun.start()].split()[-2:]
    around = " ".join([*before, prefix[noun.end() :]])
    if _CUT_WORDS.search(around):
        return CUT
    return WHOLE if _WHOLE_WORDS.search(around) else _SOME_CONE


def _found(words: str, value: float) -> re.Match[str] | None:
    return re.search(rf"(?<![\d.]){re.escape(f'{value:g}')}(?![\d]|\.\d)", words)


def _sentence_before(words: str, found: re.Match[str]) -> str:
    return re.split(r"[.;?!](?:\s|$)", words[: found.start()])[-1]


def _written_of(words: str, value: float) -> str | None:
    """What the question writes a value of, or None when its words say nothing."""
    found = _found(words, value)
    if found is None:
        return None
    after = _UNIT.sub("", words[found.end() :])
    if _AFTER_CUT.match(after):
        return CUT
    if _AFTER_FRUSTUM.match(after):
        return FRUSTUM
    return _named_cone(_sentence_before(words, found))


def _end_of(words: str, m: Measure) -> str:
    """A frustum's radius is its base's (the whole cone's) or its top's (the cone cut off),
    as the words just before it say ("base radius 6 cm"); FRUSTUM when they do not."""
    found = _found(words, m.value)
    if found is None or m.what not in {"radius", "diameter"}:
        return FRUSTUM
    end = " ".join(_sentence_before(words, found).split()[-3:])
    return WHOLE if _BASE_END.search(end) else CUT if _TOP_END.search(end) else FRUSTUM


def _read_of(m: Measure) -> str | None:
    return next((role for role, stems in _OF_STEMS.items() if any(s in m.of for s in stems)), None)


def _role(written: str | None, m: Measure) -> str | None:
    """The words' cone where they say which, else the read's, else a cone they name."""
    if written is not None and written != _SOME_CONE:
        return written
    return _read_of(m) or (WHOLE if written == _SOME_CONE else None)


def roles_as_said(request: FigureRequest, texts: Sequence[str]) -> FigureRequest:
    """A cone cut in two read with each value tied to the cone it is of (``of``). A frustum
    whose values are all the frustum's, or a cone none of whose values is a cut-off one's,
    is left as read."""
    if request.kind != "solid" or request.shape not in _SHAPES:
        return request
    words = " ".join(texts).lower()
    roles = [_role(_written_of(words, m.value), m) for m in request.measures]
    cut_said = CUT in roles if request.shape == "cone" else bool({WHOLE, CUT} & set(roles))
    if not cut_said:
        return request
    roles = [
        _end_of(words, m) if r == FRUSTUM else r
        for m, r in zip(request.measures, roles, strict=True)
    ]
    measures = [
        m.model_copy(update={"of": role or ""})
        for m, role in zip(request.measures, roles, strict=True)
    ]
    return request.model_copy(update={"shape": "frustum", "measures": measures})


def is_cut(request: FigureRequest) -> bool:
    """The reading is a cone cut in two: a value of the whole cone or of the part cut off."""
    return any(m.of in {WHOLE, CUT} for m in request.measures)


def _radius(m: Measure) -> float:
    return m.value / 2 if m.what == "diameter" else m.value


def _share(heights: dict[str, float], radii: dict[str, float]) -> float | None:
    """The cut-off cone's share k of the whole: from two heights, or two radii."""
    whole, cut, frustum = (heights.get(role) for role in (WHOLE, CUT, FRUSTUM))
    if whole is not None and cut is not None:
        return cut / whole
    if whole is not None and frustum is not None:
        return 1 - frustum / whole
    if cut is not None and frustum is not None:
        return cut / (cut + frustum)
    big, small = radii.get(WHOLE), radii.get(CUT)
    return small / big if big is not None and small is not None else None


def _tables(measures: Sequence[tuple[Measure, str]]) -> tuple[dict[str, float], ...] | None:
    """The heights and radii stated of each cone; None for a value of no part, or two
    different values of one."""
    heights: dict[str, float] = {}
    radii: dict[str, float] = {}
    for m, role in measures:
        if m.what in _ALONG:
            table, value = heights, m.value
        elif m.what in {"radius", "diameter"} and role != FRUSTUM:
            table, value = radii, _radius(m)
        else:
            return None
        if role not in _ROLES or abs(table.get(role, value) - value) > _TOLERANCE * value:
            return None
        table[role] = value
    return heights, radii


def _whole_size(
    k: float, heights: dict[str, float], radii: dict[str, float]
) -> tuple[float, float] | None:
    """The whole cone's height and radius from the cut's share k and what is stated."""
    big_h = heights.get(WHOLE)
    if big_h is None and CUT in heights:
        big_h = heights[CUT] / k
    if big_h is None and FRUSTUM in heights:
        big_h = heights[FRUSTUM] / (1 - k)
    big_r = radii.get(WHOLE)
    if big_r is None and CUT in radii:
        big_r = radii[CUT] / k
    if big_h is not None:
        return big_h, big_r if big_r is not None else big_h / _HEIGHT
    return None if big_r is None else (big_r * _HEIGHT, big_r)


def _holds(k: float, size: tuple[float, float], tables: tuple[dict[str, float], ...]) -> bool:
    big_h, big_r = size
    heights, radii = tables
    worked = {
        ("h", WHOLE): big_h, ("h", CUT): k * big_h, ("h", FRUSTUM): (1 - k) * big_h,
        ("r", WHOLE): big_r, ("r", CUT): k * big_r,
    }  # fmt: skip
    stated = [(("h", role), v) for role, v in heights.items()]
    stated += [(("r", role), v) for role, v in radii.items()]
    return all(abs(worked[key] - v) <= _TOLERANCE * v for key, v in stated)


def _solve(request: FigureRequest) -> tuple[float, float, float, list[tuple[Measure, str]]] | None:
    """(k, H, R) and each measure's cone: a frustum's radius is its base's or its top's,
    whichever holds (the two ends of a frustum are the whole cone's base and the cut)."""
    found: list[tuple[float, float, float, list[tuple[Measure, str]]]] = []
    choices = [
        (WHOLE, CUT) if m.of == FRUSTUM and m.what not in _ALONG else (m.of,)
        for m in request.measures
    ]
    for roles in product(*choices):
        measures = list(zip(request.measures, roles, strict=True))
        tables = _tables(measures)
        k = None if tables is None else _share(*tables)
        size = None if tables is None or k is None or not 0 < k < 1 else _whole_size(k, *tables)
        if tables is not None and k is not None and size is not None and _holds(k, size, tables):
            found.append((k, *size, measures))
    shapes = {tuple(round(v, 6) for v in f[:3]) for f in found}
    return found[0] if len(shapes) == 1 else None


def build_cut_cone(request: FigureRequest) -> FigureSpec | None:
    solved = _solve(request)
    if solved is None:
        return None
    k, big_h, big_r, measures = solved
    small_r, cut_y = k * big_r, (1 - k) * big_h
    drawing = Drawing("frustum")
    base = drawing.point((0.0, 0.0), dot=True)
    cut = drawing.point((0.0, cut_y), dot=True)
    apex = drawing.point((0.0, big_h))
    round_base(drawing, base, big_r)
    drawing.arc(cut, small_r, small_r * ELLIPSE)
    for side in (-1, 1):
        low, high = drawing.point((side * big_r, 0.0)), drawing.point((side * small_r, cut_y))
        drawing.line(low, high)
        drawing.line(high, apex, dashed=True)
    labels = _labels(request, measures)
    drawing.line(apex, cut, labels.get(("height", CUT)), dashed=True)
    drawing.line(cut, base, labels.get(("height", FRUSTUM)), dashed=True)
    for centre, r, y, role in ((base, big_r, 0.0, WHOLE), (cut, small_r, cut_y, CUT)):
        if ("diameter", role) in labels:
            left, right = drawing.point((-r, y)), drawing.point((r, y))
            drawing.line(left, right, labels[("diameter", role)], dashed=True, label_at=0.75)
        else:
            drawing.line(centre, drawing.point((r, y)), labels.get(("radius", role)), dashed=True)
    if ("height", WHOLE) in labels:
        # The whole cone's height beside it, from its base to its apex.
        x = -_BESIDE * big_r
        low, high = drawing.point((x, 0.0)), drawing.point((x, big_h))
        drawing.line(low, high, labels[("height", WHOLE)], dashed=True)
    return drawing.spec()


def _labels(
    request: FigureRequest, measures: list[tuple[Measure, str]]
) -> dict[tuple[str, str], str]:
    """Each stated value's label by what it is and its cone; a radius and a diameter of one
    circle are both stated only as one of them (the first)."""
    labels: dict[tuple[str, str], str] = {}
    for m, role in measures:
        if m.what == "diameter" and ("radius", role) in labels:
            continue
        if m.what == "radius" and ("diameter", role) in labels:
            continue
        what = "height" if m.what in _ALONG else m.what
        labels.setdefault((what, role), length_label(m.value, request.unit))
    return labels
