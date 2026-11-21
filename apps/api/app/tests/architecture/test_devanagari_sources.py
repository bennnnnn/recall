"""Hindi words in the server's code are written one way: a dotted letter as its letter and
its dot (U+093C), never as one sign (U+0958 to U+095F, ऩ ऱ ऴ).

Each reader of Hindi words writes the message that way first
(``core.validation.unify_devanagari``), so a word listed with ज़ as one sign would never
match: "अंग्रेज़ी में जवाब दो" typed with one sign was not seen naming English (2026-11-20).
"""

from __future__ import annotations

import re
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[2]
_ONE_SIGN = re.compile("[ऩऱऴक़-य़]")


def test_no_dotted_devanagari_letter_is_one_sign_in_the_code() -> None:
    found = [
        f"{path.relative_to(APP_ROOT)}:{number}"
        for path in sorted(APP_ROOT.rglob("*.py"))
        if "tests" not in path.relative_to(APP_ROOT).parts
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1)
        if _ONE_SIGN.search(line)
    ]
    assert not found, "write the letter and its dot (unify_devanagari): " + ", ".join(found)
