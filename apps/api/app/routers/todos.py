"""Compatibility import for the Todos API owned by ``app.modules.todos``."""

from app.modules.todos.api import router

__all__ = ["router"]
