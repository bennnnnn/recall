"""Compatibility import for the math chat tool."""

import sys

from app.modules.math import tool as _module

sys.modules[__name__] = _module
