"""Compatibility import for chat history."""

import sys

from app.modules.chat import service as _module

sys.modules[__name__] = _module
