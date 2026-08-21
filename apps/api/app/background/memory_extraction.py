"""Compatibility alias for the memory extraction service."""

import sys

from app.services.memory import extraction_workflow as _service

extract_and_store_memories = _service.extract_and_store_memories

sys.modules[__name__] = _service
