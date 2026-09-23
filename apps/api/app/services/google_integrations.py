"""Compatibility alias for Google connect and disconnect."""

import sys

from app.modules.integrations import connect as _module

sys.modules[__name__] = _module
