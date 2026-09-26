"""Compatibility alias for the periodic Gmail sync."""

import sys

from app.modules.integrations import scheduler as _module

sys.modules[__name__] = _module
