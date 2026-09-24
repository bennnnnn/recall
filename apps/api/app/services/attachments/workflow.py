"""Compatibility import for the attachments module."""

import sys

from app.modules.attachments import workflow as _module

sys.modules[__name__] = _module
