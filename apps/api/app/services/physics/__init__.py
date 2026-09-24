"""Compatibility import for the physics service.

New code belongs in :mod:`app.modules.physics`.
"""

import sys

from app.modules import physics as _module

sys.modules[__name__] = _module
