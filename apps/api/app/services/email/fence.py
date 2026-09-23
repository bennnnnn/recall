"""Compatibility alias for the email fence."""

import sys

from app.modules.integrations import fence as _module

sys.modules[__name__] = _module
