"""Compatibility alias for Gmail connection persistence."""

import sys

from app.modules.integrations import gmail_repository as _module

sys.modules[__name__] = _module
