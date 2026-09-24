"""Compatibility import for the web search chat tool."""

import sys

from app.modules.web_search import tool as _module

sys.modules[__name__] = _module
