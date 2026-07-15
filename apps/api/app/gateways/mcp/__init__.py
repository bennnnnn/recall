"""Register default MCP adapters."""

from app.core.config import Settings
from app.gateways.mcp.calendar_adapter import CalendarAdapter
from app.gateways.mcp.registry import register
from app.gateways.mcp.sympy_adapter import SympyAdapter
from app.gateways.mcp.web_search_adapter import WebSearchAdapter


def setup_mcp_adapters(settings: Settings) -> None:
    register(WebSearchAdapter(settings))
    register(CalendarAdapter())
    # Gate the model-callable SymPy tool on math_tools_enabled — without
    # this, the model could still reach SymPy via the "sympy" MCP tool even
    # when the operator disabled math_tools_enabled (which otherwise gates
    # only the pre-stream augment_prompt_messages path).
    if settings.math_tools_enabled:
        register(SympyAdapter(settings))
