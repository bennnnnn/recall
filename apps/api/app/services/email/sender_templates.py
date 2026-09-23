"""Compatibility alias for Gmail sender templates."""

import sys

from app.modules.integrations import sender_templates as _module

sys.modules[__name__] = _module
