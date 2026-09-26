"""Compatibility import for suggestion persistence."""

import sys

from app.modules.suggestions import repository as _module

sys.modules[__name__] = _module
