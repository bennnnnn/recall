"""Compatibility import for the math service.

New code belongs in :mod:`app.modules.math`.
"""

from app.modules.math.legacy_alias import install

install(__name__)
