"""Compatibility import for Home.

New code belongs in :mod:`app.modules.home`.
"""

from app.modules.home.legacy_alias import install

install(__name__)
