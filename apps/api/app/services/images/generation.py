"""Compatibility import for the images module."""

import sys

from app.modules.images import generation as _module

sys.modules[__name__] = _module
