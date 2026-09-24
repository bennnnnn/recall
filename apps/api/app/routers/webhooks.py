"""Compatibility import for the billing webhook API."""

import sys

from app.modules.billing import api as _module
from app.modules.billing.api import router

sys.modules[__name__] = _module

__all__ = ["router"]
