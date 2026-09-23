"""Compatibility alias for the calendar tool."""

import sys

from app.modules.integrations import tool as _module

sys.modules[__name__] = _module
