"""One reader of a model's JSON: every caller decodes the same output the same way.

The structured-output gateway escaped the LaTeX a model writes unescaped in a JSON
string; the maths photo extract, the scan read and OCR's page text each unwrapped the
fence their own way and did not, so ``\\frac`` became a form feed there (DUP-04).
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.gateways.model_output import parse_model_json, unwrap_model_fence
from app.modules.math.image_extract import _read_extract
from app.services.scan_text import reading_from_vision

# As the model writes it inside the JSON string: one backslash, unescaped.
_RAW_TEXT = "\\frac{1}{2}x = 3"

_SHAPES = [
    '{{"problem": "{t}", "found": true}}',
    '```json\n{{"problem": "{t}", "found": true}}\n```',
    '{{"problem": "{t}", "found": true,}}',
    '{{“problem”: "{t}", “found”: true}}',
]


@pytest.mark.parametrize("shape", _SHAPES)
def test_every_shape_decodes_to_the_same_object(shape: str) -> None:
    assert parse_model_json(shape.format(t=_RAW_TEXT)) == {
        "problem": "\\frac{1}{2}x = 3",
        "found": True,
    }


@pytest.mark.parametrize("shape", _SHAPES)
def test_the_scan_read_keeps_the_latex(shape: str) -> None:
    assert reading_from_vision(shape.format(t=_RAW_TEXT)) == "\\frac{1}{2}x = 3"


def test_the_photo_extract_keeps_the_latex_in_its_transcription() -> None:
    content = (
        '```json\n{"found": true, "kind": "equation", "lhs": "x/2", "rhs": "3",'
        ' "variables": ["x"], "source_text": "\\frac{1}{2}x = 3"}\n```'
    )
    response = SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content))])

    extract = _read_extract(response)

    assert extract is not None
    assert extract.source_text == "\\frac{1}{2}x = 3"


def test_unwrapping_takes_the_fence_and_its_tag_only() -> None:
    assert unwrap_model_fence("```text\nPage one\n```", "text") == "Page one"
    assert unwrap_model_fence("no fence here", "text") == "no fence here"
