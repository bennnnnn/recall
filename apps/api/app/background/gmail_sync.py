"""Compatibility alias for the Gmail sync job."""

import sys

from app.modules.integrations import jobs as _module

sys.modules[__name__] = _module
