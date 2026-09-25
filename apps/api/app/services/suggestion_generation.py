"""Compatibility import for suggestion generation."""

import sys

from app.modules.suggestions import service as _module

sys.modules[__name__] = _module
