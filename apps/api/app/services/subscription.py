"""Compatibility import for store subscriptions."""

import sys

from app.modules.billing import subscription as _module

sys.modules[__name__] = _module
