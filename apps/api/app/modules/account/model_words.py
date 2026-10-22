"""Which model a word in a chat line names, read from the catalog (code-health audit ARCH-06).

Settings → Models lists the catalog's labels, so a chat line names a model the same way:
by its brand ("GLM", "Claude", "DeepSeek"), with its version when two share a brand
("GLM 5.2"), or by its id. "Pro" and "Flash" name a tier: the catalog's first model of
it, the one the picker lists first. No model is written here, so adding or retiring one
in the catalog needs no edit.
"""

from __future__ import annotations

import functools
import re

from app.models.model_catalog import selectable_models

AUTO = "auto"
_AUTO_WORDS = frozenset({"auto", "automatic"})
# Words for a kind of model rather than one.
_TIER_WORDS = {
    "flash": "fast",
    "free": "fast",
    "fast": "fast",
    "pro": "smart",
    "smart": "smart",
    "plus": "smart",
}
# What people call a brand when its label does not say it.
_BRAND_WORDS = {"chatgpt": "gpt"}
_LETTERS = re.compile(r"[a-z]+")


def _brand(word: str) -> str:
    """``gpt-6`` → ``gpt``, ``qwen3.7`` → ``qwen``: the name before its version."""
    if word in _BRAND_WORDS:
        return _BRAND_WORDS[word]
    match = _LETTERS.match(word)
    return match.group() if match else word


@functools.cache
def model_ids() -> frozenset[str]:
    """``auto`` and every model the picker offers."""
    return frozenset({AUTO, *(model.id for model in selectable_models())})


@functools.cache
def _brands() -> dict[str, tuple[tuple[str, tuple[str, ...]], ...]]:
    """Brand → its models in catalog order, each with its label's words."""
    found: dict[str, list[tuple[str, tuple[str, ...]]]] = {}
    for model in selectable_models():
        words = tuple(model.label.lower().split())
        found.setdefault(_brand(words[0]), []).append((model.id, words))
    return {brand: tuple(models) for brand, models in found.items()}


def tier_model(word: str) -> str | None:
    """The model ``auto`` or a tier word ("pro", "flash") names, or None."""
    if word in _AUTO_WORDS:
        return AUTO
    tier = _TIER_WORDS.get(word)
    if tier is None:
        return None
    return next((model.id for model in selectable_models() if model.tier == tier), None)


def brand_model(tokens: list[str], index: int) -> str | None:
    """The model the brand word ``tokens[index]`` names, or None when it is no brand."""
    models = _brands().get(_brand(tokens[index]))
    if not models:
        return None
    rest = tokens[index + 1 :]

    def reach(model: tuple[str, tuple[str, ...]]) -> int:
        # How far the next words follow the label past its brand ("glm 5.2").
        count = 0
        for want, got in zip(model[1][1:], rest, strict=False):
            if want != got:
                break
            count += 1
        return count

    # ``max`` keeps the first of a tie: the brand's first model in the catalog.
    return max(models, key=reach)[0]
