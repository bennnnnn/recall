"""Compatibility import for the attachments module."""

import sys

from app.modules.attachments import reuse as _module

sys.modules[__name__] = _module
