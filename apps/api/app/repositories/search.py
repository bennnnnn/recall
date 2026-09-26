"""Compatibility import for conversation search persistence."""

import sys

from app.modules.search import repository as _module

sys.modules[__name__] = _module
