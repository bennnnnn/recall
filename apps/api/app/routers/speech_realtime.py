"""Compatibility import for the speech API."""

import sys

from app.modules.speech import realtime as _module
from app.modules.speech.realtime import router

sys.modules[__name__] = _module

__all__ = ["router"]
