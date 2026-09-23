"""Compatibility alias for the calendar service."""

import sys

from app.modules.integrations import calendar as _module

sys.modules[__name__] = _module
