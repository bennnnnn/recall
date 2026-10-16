"""Camera math: read the equation in a turn's photo so SymPy can verify the answer.

It runs for the math scanner's caption, a caption that still reads as a math
request, or a reading the student already confirmed in the scanner.
"""

from __future__ import annotations

from app.core.config import Settings
from app.gateways.storage_gateway import StorageGateway
from app.modules.chat.stream_status import StreamStatusFn
from app.modules.math.schemas import MathImageExtract


async def camera_math_extract(
    content: str,
    *,
    image_attachments: list[tuple[str, str]],
    bytes_by_key: dict[str, bytes],
    gateway: StorageGateway,
    settings: Settings,
    on_status: StreamStatusFn | None,
) -> tuple[MathImageExtract | None, str]:
    """The equation in the first photo, and ``content`` with its ``Solve:`` line for the prompt.

    Bytes downloaded here are kept in ``bytes_by_key`` for the vision injection.
    """
    image_math_extract: MathImageExtract | None = None
    # Camera math solver: vision-extract equation so SymPy can verify.
    from app.modules.attachments import content as attachment_content_service
    from app.modules.math import image_extract as math_image_extract_service
    from app.modules.math import match as math_match
    from app.services.subject_scan import confirmed_scan_reading, scanner_camera_subject

    # BUG FIX: this used to require the sent text to be BYTE-FOR-BYTE
    # identical to the preset camera caption — the composer pre-fills that
    # caption into an editable text box, so any user edit (add a word, fix
    # a typo, autocorrect touching punctuation) silently dropped the OCR
    # step with no error shown; the photo still sent, just unverified.
    # An edited caption from someone who chose "Solve math with camera"
    # overwhelmingly still reads as a math ask ("solve this", "find x", a
    # stray leftover word) — reuse the same has_math_keyword signal
    # needs_symbolic_math already trusts for the image-attachment case, so
    # OCR fires whenever the caption still looks like a math request, not
    # only on an exact match. A caption with no math keyword at all (or the
    # default blank caption every plain image attachment sends) is left
    # alone — this must not fire a vision call on every unrelated photo.
    caption = content.strip()
    scan_subject = scanner_camera_subject(content)
    looks_like_math_caption = (
        scan_subject not in {"physics", "biology", "chemistry"}
        and bool(caption)
        and math_match.has_math_keyword(caption.lower())
    )
    # A physics or chemistry photo carries its confirmed reading too, but that
    # reading is the subject's request text, not an equation for math OCR.
    confirmed_reading = confirmed_scan_reading(content) if scan_subject in (None, "math") else None
    if image_attachments and (
        confirmed_reading or scan_subject == "math" or looks_like_math_caption
    ):
        if on_status is not None:
            await on_status("calculating")
        if confirmed_reading:
            # The student already verified OCR in the scanner. Re-running
            # vision here can silently solve a different equation.
            from app.modules.math.ocr import extract_from_confirmed_reading

            extracted = extract_from_confirmed_reading(confirmed_reading)
            if extracted is not None:
                image_math_extract = extracted
        else:
            mime, storage_key = image_attachments[0]
            image_bytes = bytes_by_key.get(storage_key)
            if image_bytes is None:
                image_bytes = await attachment_content_service.read_attachment_bytes(
                    gateway, storage_key
                )
                if image_bytes:
                    bytes_by_key[storage_key] = image_bytes
            if image_bytes:
                extracted = await math_image_extract_service.extract_equation_from_image(
                    settings, content_type=mime, data=image_bytes
                )
                if extracted is not None:
                    image_math_extract = extracted
                    suffix = math_image_extract_service.camera_math_user_suffix(extracted)
                    # Prompt/stream path sees Solve: for equations; stored bubble
                    # keeps the image marker + original caption only.
                    if suffix:
                        content = f"{content}\n\n{suffix}"
    return image_math_extract, content
