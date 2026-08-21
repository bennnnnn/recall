"""Compatibility alias for the suggestion generation service."""

import sys

from app.services import suggestion_generation as _service

MAX_ACTIVE_SUGGESTIONS = _service.MAX_ACTIVE_SUGGESTIONS
generate_suggestions = _service.generate_suggestions

sys.modules[__name__] = _service
