"""Compatibility alias for calendar nudges."""

import sys

from app.modules.integrations import nudges as _module

sys.modules[__name__] = _module
