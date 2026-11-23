"""A photographed chemistry problem is read as plain text, then solved like typed text."""

from __future__ import annotations

from app.modules.chemistry.block import build_verified_chemistry
from app.modules.chemistry.direct import maybe_direct_chemistry_reply
from app.modules.chemistry.extract import extract_chemistry_intent
from app.modules.chemistry.read import CHEMISTRY_READ_PROMPT
from app.services.scan_text import reading_from_vision


def test_the_vision_prompt_asks_for_plain_text() -> None:
    assert "plain text" in CHEMISTRY_READ_PROMPT
    assert "Do not solve" in CHEMISTRY_READ_PROMPT
    assert "apparatus" in CHEMISTRY_READ_PROMPT
    assert "mathpix" not in CHEMISTRY_READ_PROMPT.casefold()
    assert "equation" not in CHEMISTRY_READ_PROMPT.casefold()


def test_a_math_kind_payload_is_not_a_chemistry_reading() -> None:
    raw = '{"kind":"equation","lhs":"2x+3","rhs":"7","found":true}'
    assert reading_from_vision(raw) == ""
    assert reading_from_vision("Find the molar mass of H2O") == "Find the molar mass of H2O"


def test_a_confirmed_reading_solves_with_the_photo() -> None:
    from app.modules.chemistry.reading import chemistry_text_for_solve, confirmed_chemistry_reading
    from app.services.subject_scan import CHEMISTRY_CAMERA_PROMPT, SCAN_CONFIRMED_PREFIX

    caption = CHEMISTRY_CAMERA_PROMPT
    confirmed = f"{caption}\n\n{SCAN_CONFIRMED_PREFIX} Find the molar mass of H2O"
    assert confirmed_chemistry_reading(caption) is None
    assert chemistry_text_for_solve(confirmed) == "Find the molar mass of H2O"
    intent = extract_chemistry_intent(chemistry_text_for_solve(confirmed))
    assert intent is not None
    verified = build_verified_chemistry(intent)
    reply = maybe_direct_chemistry_reply(verified, has_image_attachment=True, user_text=confirmed)
    assert reply is not None
    assert "18.02" in reply
    assert (
        maybe_direct_chemistry_reply(verified, has_image_attachment=True, user_text=caption) is None
    )


def test_a_confirmed_reading_solves_as_typed_text_without_the_photo() -> None:
    reading = "Find the molar mass of H2O"
    assert not reading.startswith("Show steps:")
    intent = extract_chemistry_intent(reading)
    assert intent is not None
    verified = build_verified_chemistry(intent)
    reply = maybe_direct_chemistry_reply(verified, has_image_attachment=False)
    assert reply is not None
    assert "18.02" in reply
    assert maybe_direct_chemistry_reply(verified, has_image_attachment=True) is None
