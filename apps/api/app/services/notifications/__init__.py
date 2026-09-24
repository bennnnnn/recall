"""Compatibility import for notifications.

New code belongs in :mod:`app.modules.notifications`.
"""

from app.modules.notifications.legacy_alias import install

install(__name__)
