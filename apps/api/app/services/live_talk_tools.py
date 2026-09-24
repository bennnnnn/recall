"""Compatibility import for the speech module."""

import sys

from app.modules.speech import live_talk_tools as _module

sys.modules[__name__] = _module
