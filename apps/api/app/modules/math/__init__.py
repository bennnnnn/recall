"""Math — the symbolic pipeline, from raw user text to a verified answer.

Three stages, each its own subpackage:

- ``match``  — cheap text scanning: does this look like math, and what kind
- ``tools``  — intent extraction, direct-reply decisions, verified block and
               prompt augmentation (the stage that decides what to hand the model)
- ``solve``  — SymPy evaluation: actually compute the answer

Alongside them: ``fence`` (post-stream fence correction), ``school``,
``followup``, ``ocr`` / ``image_extract`` (math from photos), ``reply_policy``
and ``sympy_warmup`` (the solve that warms the shared SymPy pool in
``app.core.sympy_executor``).

Physics is a peer subject, not a corner of this package — see
``app.modules.physics``.

The package surface stays lazy so importing a matcher does not eagerly load the
symbolic solver stack. Other modules import only the names in ``_EXPORTS``.
"""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from app.modules.math.unit_conversion import (
        get_unit_registry as get_unit_registry,
    )

_EXPORTS = {"get_unit_registry": ("unit_conversion", "get_unit_registry")}

__all__ = list(_EXPORTS)


def __getattr__(name: str) -> Any:
    target = _EXPORTS.get(name)
    if target is None:
        raise AttributeError(name)
    module_name, attribute = target
    value = getattr(import_module(f"app.modules.math.{module_name}"), attribute)
    globals()[name] = value
    return value


# Seams the chat turn uses: camera reads, and the tool loop's check that a sympy call is the
# problem the user wrote.
_MODULE_EXPORTS = (
    "image_extract",
    "match",
    "ocr",
    # The verified block's types (services/solving).
    "response_intent",
    "solve.key_steps",
    # Maths as the subject registry asks it (services/subjects/registry).
    "subject",
    "text_plot",
    "tool_check",
    "tools.extract",
    # The model reader (modules/model_reader) keeps maths' own typed read.
    "tools.llm_extract",
    "tools.prompt",
    # The subject order (services/subjects/order): a curve physics cannot read.
    "tools.school.curve_points",
)
