"""Compatibility alias for the To-do domain module."""

import sys
from importlib import import_module

sys.modules[__name__] = import_module("app.modules.todos")
