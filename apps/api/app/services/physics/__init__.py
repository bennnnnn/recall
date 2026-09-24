"""Compatibility import for the physics service.

New code belongs in :mod:`app.modules.physics`.
"""

from app.modules.physics.legacy_alias import install

install(__name__)
