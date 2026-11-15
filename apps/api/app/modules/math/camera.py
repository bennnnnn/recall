"""Camera maths: read the equation in a turn's photo so SymPy can verify the answer.

It runs for the maths scanner's caption, a caption that still reads as a maths request,
or a reading the student already confirmed in the scanner. Chat asks it through maths'
adapter (``photo``, ``services/subjects/registry``) and hands it the photo's bytes.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

from app.core.config import Settings
from app.modules.math.schemas import MathImageExtract
from app.services.solving import PhotoReading

if TYPE_CHECKING:
    from app.modules.math.ocr import MathOcrResult


async def read_camera_maths(
    content: str,
    *,
    image_attachments: list[tuple[str, str]],
    load_image: Callable[[str], Awaitable[tuple[str, bytes] | None]],
    settings: Settings,
    on_status: Callable[[str], Awaitable[None]] | None,
) -> PhotoReading:
    """The equation in the first photo, and ``content`` with its ``Solve:`` line for the prompt.

    ``load_image`` gives a photo by its storage key, upright, with its content type (the
    caller keeps the stored bytes for the vision injection). The reading says whether the
    OCR was sure of it, and carries its transcription for the subject order.
    """
    image_math_extract: MathImageExtract | None = None
    uncertain = False
    transcription: str | None = None
    # Camera math solver: vision-extract equation so SymPy can verify.
    from app.modules.math import image_extract as math_image_extract_service
    from app.modules.math import match as math_match
    from app.services.subject_scan import confirmed_scan_reading, scanner_camera_subject

    # The composer pre-fills the camera caption into an editable box, so the student may
    # have changed it (a word added, a typo fixed, autocorrect on the punctuation). An
    # edited caption still reads as a maths ask ("solve this", "find x"), so OCR runs
    # whenever the caption has a maths keyword, the signal needs_symbolic_math trusts for
    # an attached image, not only on the exact caption. A caption with no maths keyword
    # is left alone: no vision call on every captioned photo. A photo sent alone is read
    # like a scan: a homework photo with no caption got plain "Step 1 … Step 4" lines and no
    # checked answer, while the same question typed got both (2026-11-06). A photo with no
    # problem on it reads found=false and goes on as an ordinary photo.
    caption = content.strip()
    scan_subject = scanner_camera_subject(content)
    photo_alone = not caption
    looks_like_math_caption = scan_subject not in {"physics", "biology", "chemistry"} and (
        photo_alone or math_match.has_math_keyword(caption.lower())
    )
    # A physics or chemistry photo carries its confirmed reading too, but that
    # reading is the subject's request text, not an equation for math OCR.
    confirmed_reading = confirmed_scan_reading(content) if scan_subject in (None, "math") else None
    if image_attachments and (
        confirmed_reading or scan_subject == "math" or looks_like_math_caption
    ):
        # A photo alone may be anything: it says "calculating" only once it holds a problem.
        if on_status is not None and not photo_alone:
            await on_status("calculating")
        if confirmed_reading:
            # The student already verified OCR in the scanner. Re-running
            # vision here can silently solve a different equation.
            from app.modules.math.ocr import extract_from_confirmed_reading

            extracted = extract_from_confirmed_reading(confirmed_reading)
            if extracted is not None:
                image_math_extract = extracted
        else:
            _mime, storage_key = image_attachments[0]
            photo = await load_image(storage_key)
            if photo is not None and photo[1]:
                read = await _read_equation(settings, *photo)
                uncertain = read.uncertain
                transcription = read.display_text or None
                extracted = read.extract
                if extracted is not None:
                    image_math_extract = extracted
                    suffix = math_image_extract_service.camera_math_user_suffix(extracted)
                    # Prompt/stream path sees Solve: for equations; stored bubble
                    # keeps the image marker + original caption only.
                    if suffix:
                        content = f"{content}\n\n{suffix}"
    return PhotoReading(
        image_math_extract, content, uncertain=uncertain, transcription=transcription
    )


async def _read_equation(settings: Settings, content_type: str, data: bytes) -> MathOcrResult:
    """The OCR read of one photo, its Mathpix call counted toward the day's spend.

    Only the scanner's old read-back (``services/scan_read``) counted one, and the phone no
    longer calls it: every photo the turn read was billed and never metered (audit SCAN-07).
    """
    from app.gateways import mathpix_gateway, mock_llm
    from app.gateways.llm_spend import meter_reported_cost
    from app.modules.math.ocr import extract_math_from_image
    from app.services.quota import MATH_SCAN_READ_SPEND_USD

    if mathpix_gateway.is_configured(settings) and not mock_llm.should_mock_llm(settings):
        meter_reported_cost("mathpix", MATH_SCAN_READ_SPEND_USD)
    return await extract_math_from_image(settings, content_type=content_type, data=data)
