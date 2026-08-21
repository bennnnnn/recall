"""Register service-layer MCP tool orchestrators."""

from app.core.config import Settings
from app.gateways.mcp.registry import register
from app.services.mcp.calendar_adapter import CalendarAdapter
from app.services.mcp.image_gen_adapter import ImageGenAdapter
from app.services.mcp.sympy_adapter import SympyAdapter
from app.services.mcp.web_search_adapter import WebSearchAdapter


def setup_mcp_adapters(settings: Settings) -> None:
    register(WebSearchAdapter(settings))
    register(CalendarAdapter())
    if settings.math_tools_enabled:
        register(SympyAdapter(settings))
    if settings.image_generation_enabled:
        register(ImageGenAdapter(settings))
