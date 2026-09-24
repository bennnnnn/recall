"""Compatibility import for the chemistry service.

New code belongs in :mod:`app.modules.chemistry`.
"""

from app.modules.chemistry import *  # noqa: F403
from app.modules.chemistry.legacy_alias import install

install(__name__)
