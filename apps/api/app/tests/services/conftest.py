"""Fixtures shared by service tests."""

import pytest

from app.gateways.mcp import registry as mcp_registry
from app.modules.web_search import WebSearchAdapter
from app.tests.services.tool_loop_support import settings


@pytest.fixture
def web_search_registered():
    mcp_registry.clear()
    mcp_registry.register(WebSearchAdapter(settings()))
    yield
    mcp_registry.clear()
