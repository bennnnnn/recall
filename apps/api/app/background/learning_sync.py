"""Compatibility import for the Learning background job."""

from app.modules.learning.jobs import sync_learning_from_chat

__all__ = ["sync_learning_from_chat"]
