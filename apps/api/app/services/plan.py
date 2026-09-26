"""Compatibility import for plan selection."""

import sys

from app.modules.billing import plan as _module

sys.modules[__name__] = _module
