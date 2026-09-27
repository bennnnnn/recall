"""Shared unit registry for math conversions and physics dimensional checks."""

from __future__ import annotations

from pint import UnitRegistry

_unit_registry: UnitRegistry | None = None


def get_unit_registry() -> UnitRegistry:
    global _unit_registry
    if _unit_registry is None:
        _unit_registry = UnitRegistry()
    return _unit_registry
