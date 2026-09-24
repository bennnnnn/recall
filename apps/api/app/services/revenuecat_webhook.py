"""Compatibility import for RevenueCat webhook handling."""

import sys

from app.modules.billing import revenuecat as _module

sys.modules[__name__] = _module
