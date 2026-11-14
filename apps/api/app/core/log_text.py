"""Log text a request's value cannot break: a leaf, so a pure solver may log through it too."""

from __future__ import annotations


def one_line(value: object) -> str:
    """``value`` as log text that cannot start a line of its own: CR and LF written escaped.

    Both formatters already escape them; this marks a request's value where it is logged, for
    a reader and for CodeQL py/log-injection, which does not see the formatters.
    """
    return str(value).replace("\r", "\\r").replace("\n", "\\n")
