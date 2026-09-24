"""Compatibility import for the attachments module."""

import sys

from app.modules.attachments import upload as _module

sys.modules[__name__] = _module
