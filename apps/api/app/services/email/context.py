"""Compatibility alias for Gmail inbox context."""

import sys

from app.modules.integrations import inbox as _module

sys.modules[__name__] = _module
