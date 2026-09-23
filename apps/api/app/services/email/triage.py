"""Compatibility alias for Gmail triage."""

import sys

from app.modules.integrations import triage as _module

sys.modules[__name__] = _module
