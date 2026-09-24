"""Compatibility import for web search.

New code belongs in :mod:`app.modules.web_search`.
"""

from app.modules.web_search import *  # noqa: F403
from app.modules.web_search.legacy_alias import install

install(__name__)
