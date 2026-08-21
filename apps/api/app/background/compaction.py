"""Compatibility alias for the chat compaction service."""

import sys

from app.services.chat import compaction as _service

compress_chat_history = _service.compress_chat_history

sys.modules[__name__] = _service
