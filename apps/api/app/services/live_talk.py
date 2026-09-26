"""Compatibility import for the speech module."""

import sys

from app.modules.speech import live_talk as _module

sys.modules[__name__] = _module
