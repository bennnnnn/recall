"""Register default MCP adapters."""

from app.core.config import Settings
from app.gateways.mcp.calendar_adapter import CalendarAdapter
from app.gateways.mcp.registry import register
from app.gateways.mcp.sympy_adapter import SympyAdapter
from app.gateways.mcp.web_search_adapter import WebSearchAdapter


def setup_mcp_adapters(settings: Settings) -> None:
    register(WebSearchAdapter(settings))
    register(CalendarAdapter())
    register(SympyAdapter(settings))
