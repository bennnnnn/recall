"""Compatibility import for conversation search."""

import sys

from app.modules.search import service as _module

sys.modules[__name__] = _module
