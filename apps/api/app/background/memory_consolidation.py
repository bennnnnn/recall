"""Compatibility alias for the memory consolidation service."""

import sys

from app.services.memory import consolidation_workflow as _service

consolidate_user_memory_sections = _service.consolidate_user_memory_sections

sys.modules[__name__] = _service
