"""Compatibility import for the chemistry service.

New code belongs in :mod:`app.modules.chemistry`.
"""

import sys

from app.modules import chemistry as _module

sys.modules[__name__] = _module
