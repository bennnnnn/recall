"""Compatibility import for the speech API."""

import sys

from app.modules.speech import api as _module
from app.modules.speech.api import router

sys.modules[__name__] = _module

__all__ = ["router"]
