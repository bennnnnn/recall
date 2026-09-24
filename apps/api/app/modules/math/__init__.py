"""Math — the symbolic pipeline, from raw user text to a verified answer.

Three stages, each its own subpackage:

- ``match``  — cheap text scanning: does this look like math, and what kind
- ``tools``  — intent extraction, direct-reply decisions, verified block and
               prompt augmentation (the stage that decides what to hand the model)
- ``solve``  — SymPy evaluation: actually compute the answer

Alongside them: ``fence`` (post-stream fence correction), ``school``,
``followup``, ``ocr`` / ``image_extract`` (math from photos), ``reply_policy``
and ``sympy_executor`` (the sandboxed SymPy process pool).

Physics is a peer subject, not a corner of this package — see
``app.modules.physics``.

The package surface stays lazy. ``tools.block`` and ``physics.block`` reference
each other's primitives during initialization, so eager re-exports would close
an import cycle. Other modules import only the names in ``_EXPORTS``.
"""

from __future__ import annotations

from importlib import import_module
from typing import Any

_EXPORTS = {
    "extract_average_speed_intent": ("tools.school", "extract_average_speed_intent"),
    "get_unit_registry": ("school", "get_unit_registry"),
}

__all__ = list(_EXPORTS)


def __getattr__(name: str) -> Any:
    target = _EXPORTS.get(name)
    if target is None:
        raise AttributeError(name)
    module_name, attribute = target
    value = getattr(import_module(f"app.modules.math.{module_name}"), attribute)
    globals()[name] = value
    return value
