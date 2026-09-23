"""Compatibility alias for calendar connection persistence."""

import sys

from app.modules.integrations import calendar_repository as _module

sys.modules[__name__] = _module
