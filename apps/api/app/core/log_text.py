"""A value from outside, written into a log line so it cannot start another one.

An id from a path or a webhook, a provider's field, a URL the user shared, a model slug from
the settings a route is handed: a log call writes it through ``log_safe``. Both formatters
already escape CR and LF in the finished line (``core/logging.py``), but a log call is checked
where it is written (CodeQL ``py/log-injection`` reads the call, not the handler), and a handler
without those formatters (a test's capture, a library's own) writes the message as it is.
"""

from __future__ import annotations

import re

# C0 controls, DEL, C1 controls (NEL among them) and the Unicode line and paragraph
# separators: each can end a line, or rewrite one, in some log viewer.
_CONTROL = re.compile(r"[\x00-\x1f\x7f-\x9f\u2028\u2029]")


def _escaped(match: re.Match[str]) -> str:
    return match.group().encode("unicode_escape").decode("ascii")


def log_safe(value: object) -> str:
    """``value`` as one line of text: CR, LF and every other control character escaped.

    Ordinary text, an id or a number comes back as ``%s`` would print it.
    """
    # CR and LF first, with a literal ``.replace("\n", ...)``: CodeQL recognises that call as
    # the line-break sanitizer, so the value is clean where the log call uses it.
    text = str(value).replace("\r", "\\r").replace("\n", "\\n")
    return _CONTROL.sub(_escaped, text)
