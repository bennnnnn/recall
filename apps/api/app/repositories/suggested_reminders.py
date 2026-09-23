"""Compatibility alias for suggested-reminder persistence."""

import sys

from app.modules.integrations import suggestions_repository as _module

sys.modules[__name__] = _module
