"""The aliases routing picks by job: data, changed here and not in routing code.

``app.models.model_catalog`` serves them (``auto_fast_alias``, ``vision_alias``,
``tool_selector_aliases``, ...), and ``test_model_catalog`` checks each lane against
the capability its job needs, so a lane can't point at a model that can't do it.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class RoutingLanes:
    """One product alias per routing job (Auto's three lanes, photos, tool selection)."""

    # Qwen3.7 Flash answers an everyday turn as fast as GPT-6 Luna (about 0.8s to
    # first text with thinking off) for about a third of the price. Auto's
    # everyday lane carries most turns; hard and maths turns route stronger.
    everyday: str
    hard: str
    # Live phone QA repeatedly saw DeepSeek R1 stream hidden reasoning and then
    # return no visible answer. GLM 5.2 produced the verified worked-math
    # contract in about two seconds, so Auto math uses this strong tier directly.
    math: str
    # A turn that shows the model a photo, when its own model cannot read one,
    # and the second photo reader (another company) when the first fails.
    vision: str
    vision_backup: str
    # The tool-selection round, in order: one fast tool-capable model, then one
    # from another company when the first fails.
    tool_selectors: tuple[str, ...]
    # A background structured call (memory, titles, word problems) asks this once when
    # its own model fails or answers out of shape. It must do JSON mode.
    structured_fallback: str


ROUTING = RoutingLanes(
    everyday="qwen-3.7-flash",
    hard="smart-chat",
    math="glm-5.2",
    vision="vision-chat",
    vision_backup="fallback-vision-model",
    tool_selectors=("gpt-6-luna", "free-chat"),
    structured_fallback="fallback-memory-model",
)
