"""Compatibility import for the images API."""

import sys

from app.modules.images import api as _module
from app.modules.images.api import router

sys.modules[__name__] = _module

__all__ = ["router"]
