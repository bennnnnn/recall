"""Detect user intent to produce an HTML/CSS/JS preview in chat.

When the user asks to build/render/design a web UI, page, form, card, layout,
dashboard, or mockup, the model emits a ```html fence (per VISUALIZATION_HINTS
in prompt_constants/visuals.py). Those fences are large; the "short"
response-style cap (400 tokens) truncates them mid-CSS, leaving a blank or
broken preview. ``turn_prep`` uses this detector to bump the output cap for
those turns so the model has room to finish the complete fence.

Matching is linear token scans — no ``\\s+`` / ``.+`` regex on user chat text
(CodeQL ``py/polynomial-redos``), mirroring ``image_gen_intent``.
"""

from __future__ import annotations

# Verbs that signal "produce a deliverable" (vs. a question about HTML).
_PRODUCTION_VERBS = frozenset(
    {
        "build",
        "make",
        "create",
        "design",
        "code",
        "write",
        "generate",
        "develop",
        "mock",
        "prototype",
        "render",
        "show",
        "give",
        "want",
        "need",
    }
)

# Single-word nouns that unambiguously mean a web deliverable. Generic words
# (page/site/app/form/card/screen/ui/layout) are intentionally excluded here
# to avoid false positives on casual chat ("I want a page about cats"); they
# are still covered by the multi-word phrases below.
_WEB_NOUNS = frozenset(
    {
        "website",
        "webpage",
        "dashboard",
        "mockup",
        "html",
        "webapp",
    }
)

# Multi-word phrases that strongly indicate an HTML preview request.
_WEB_PHRASES = (
    "web page",
    "web ui",
    "web app",
    "web mockup",
    "landing page",
    "login screen",
    "signup form",
    "sign-up form",
    "portfolio site",
    "html page",
    "html preview",
    "html code",
    "html for",
    "css for",
    "interactive mockup",
)

# Image-gen verbs — these mean a raster image, NOT an HTML preview. The prompt
# explicitly says ```html is NOT for "draw me X" / "create an image of X".
_IMAGE_VERBS = frozenset({"draw", "paint", "illustrate"})


def _tokens(text: str) -> list[str]:
    return text.lower().split()


def is_html_preview_request(content: str) -> bool:
    """True when the user asks the model to produce an HTML/CSS/JS preview."""
    text = content.lower()
    if not text.strip():
        return False
    # Strong multi-word phrases take precedence.
    for phrase in _WEB_PHRASES:
        if phrase in text:
            # "draw me a web page" is image gen, not HTML.
            if not any(verb in text for verb in _IMAGE_VERBS):
                return True
    tokens = _tokens(content)
    if not tokens:
        return False
    has_verb = any(tok in _PRODUCTION_VERBS for tok in tokens)
    has_web_noun = any(tok in _WEB_NOUNS for tok in tokens)
    if has_verb and has_web_noun and not any(tok in _IMAGE_VERBS for tok in tokens):
        return True
    return False
