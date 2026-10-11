"""In-app visual fence hints (HTML, charts, places). Chemistry is gated."""

import re

_HTML_UI_TURN = re.compile(
    r"(?:"
    r"\b(?:html|css)\b|"
    r"\b(?:web\s+)?ui\b|"
    r"\blanding\s+page\b|"
    r"\blogin\s+(?:page|screen|form)\b|"
    r"\bdashboard\b|"
    r"\binteractive\s+mockup\b|"
    r"```html\b"
    r")",
    re.IGNORECASE,
)
_HTML_IMAGE_ASK = re.compile(
    r"\b(?:draw|create|generate|make)\s+(?:me\s+)?(?:an?\s+)?(?:image|picture|photo|png)\b",
    re.IGNORECASE,
)


def is_html_ui_question(text: str) -> bool:
    """True when the user asked for a web UI / page mockup, not a generated image."""
    cleaned = text.strip()
    if not cleaned or _HTML_IMAGE_ASK.search(cleaned):
        return False
    return bool(_HTML_UI_TURN.search(cleaned))


# Only injected when turn_prep actually has chemistry context (PubChem / SMILES).
# Teaching ```smiles on every rich turn made "create music" emit a molecule card.
CHEMISTRY_FENCE_HINT = (
    "This turn is chemistry. Molecular structures: ```smiles (alias ```chemistry) "
    "with a plain SMILES string — never geometry, graph, mermaid, HTML/SVG, "
    "`$...$`, or ```math. One molecule per fence; optional caption above the SMILES. "
    "Use verified SMILES from the system block verbatim when present. "
    "Do not emit ```molecule3d; do not mention attaching or 3D fences. "
    "Do not add 2D/3D section headings around the structure. "
    "Do not emit a molecule card unless this turn is actually about a chemical structure."
)


def attach_chemistry_fence_hint(block: str) -> str:
    """Teach ```smiles only when this turn actually has a verified structure."""
    if "Canonical SMILES" in block or "Verified molecular descriptors" in block:
        return f"{CHEMISTRY_FENCE_HINT}\n\n{block}"
    return block


VISUALIZATION_HINTS = (
    "In-app visuals (only when appropriate — not for image-generation requests):\n\n"
    "**Image generation** — Check User profile Plan (pro|free). "
    'Pro users can ask in chat (e.g. "create a cat", "draw me a cat", "create a sunset pic"); '
    "the app fulfills those requests outside the chat model — you cannot create PNG/JPG "
    "inside chat text. Never invent ```image fences, tool-call JSON, or "
    '{"prompt":"..."} blocks for generation — that is not an in-app visual format. '
    "If Plan is pro and they ask for an image, the mobile app normally intercepts "
    "that request before chat. If you still see it, answer in chat — do not tell "
    "them to send the same image request again. Never claim an image is attached "
    "and never invent ```image / prompt JSON. "
    "Never say Recall cannot generate images. Never send the user to DALL-E, "
    "Midjourney, Craiyon, Stable Diffusion, ChatGPT, or any other generator. "
    "Never write a copy-paste prompt for an external app. "
    "Do NOT say generation is Pro-only or ask them to upgrade. "
    "If Plan is free and they ask for image generation, mention that Pro unlocks it. "
    "If they want a photo/illustration and are NOT asking "
    "about an uploaded attachment or a math diagram, do NOT substitute ```html, "
    "SVG, or CSS art. Do not emit ```geometry or ```graph JSON. "
    "For uploaded images, describe what you see — do not redraw them in HTML.\n\n"
    "**HTML UI** (```html) — Use ONLY when the user wants a web UI, page, form, card, layout, "
    "login screen, dashboard, landing page, or interactive mockup — NOT for 'draw me X' or "
    "'create an image of X'. Prefer one self-contained ```html with a <style> block. "
    "For a real multi-file page you MAY also emit ```css styles.css and ```javascript app.js "
    "in the same reply (relative names only, no folders). The app inlines them for preview. "
    'Link with href="styles.css" / src="app.js" or omit the tags — leftover CSS/JS is '
    "appended. Do not invent other files or a build step.\n\n"
    "**Mermaid diagrams** (```mermaid) — Processes, workflows, architecture, relationships, "
    "decision trees. Prefer over bullet lists when showing connections. Lead with the "
    "```mermaid fence (one short sentence max, no joke setup). Match the steps they "
    "asked for. Not for molecules.\n\n"
    "**Charts** (```chart) — Vega-Lite JSON for numeric comparisons and trends. "
    "You CAN draw these in-app. NEVER say you cannot draw a chart. "
    "NEVER mermaid, a pipe table, or HTML for a bar/line/pie series. "
    'Always include `"$schema": "https://vega.github.io/schema/vega-lite/v5.json"` '
    "as the first key so the renderer picks Vega-Lite. Prefer Vega-Lite over Vega. "
    "Example:\n"
    "```chart\n"
    '{"$schema":"https://vega.github.io/schema/vega-lite/v5.json",'
    '"description":"A simple bar chart","data":{"values":['
    '{"a":"A","b":28},{"a":"B","b":55},{"a":"C","b":43}]},'
    '"mark":"bar","encoding":{"x":{"field":"a","type":"nominal"},'
    '"y":{"field":"b","type":"quantitative"}}}\n'
    "```\n\n"
    "**Geometry / graphs** — Do not emit ```geometry or ```graph JSON. Do not "
    "tell the user a diagram will be attached. "
    "Never invent measures. School shapes only — not molecules.\n\n"
    "**Places** (```places) — JSON array of {name, url, note?, address?, price?} for local "
    "venue recommendations (any nearby place). Use when the user asks for something "
    "near them — nearest/closest/nearby — regardless of category.\n\n"
    "For uploaded images, describe or answer about what you see — do not redraw them in HTML."
)

# Compact/slim turns never get VISUALIZATION_HINTS (viz_intent is chart/mermaid/HTML
# only). A "Dog" / "Image" thread then invented "Recall can't generate" + DALL-E.
IMAGE_GEN_HONESTY_HINT = (
    "Recall generates pictures in this chat for Pro (the app intercepts clear asks). "
    "Never say Recall cannot generate images. Never send the user to DALL-E, "
    "Midjourney, Craiyon, Stable Diffusion, ChatGPT, or any other generator. "
    "Never write a copy-paste prompt for an external app. "
    "If this turn still reached you, answer in chat — do not tell them to send "
    "the same image request again, and do not claim an image is attached. "
    "If Plan is free, mention Pro unlocks in-chat generation."
)

# Intercept 404s when generation is off, then chat still runs. Do not tell them
# to resubmit a generate ask (that loops through the same disabled intercept).
IMAGE_GEN_UNAVAILABLE_HINT = (
    "In-chat image generation is not available. Do not tell the user to resubmit "
    'or to send "generate an image of …". Never send them to DALL-E, Midjourney, '
    "Craiyon, Stable Diffusion, ChatGPT, or any other generator. Answer in chat."
)

_IMAGE_GEN_MENTION_WORDS = (
    "image",
    "images",
    "picture",
    "pictures",
    "pic",
    "pics",
    "photo",
    "photos",
    "illustration",
    "illustrations",
    "artwork",
    "artworks",
    "portrait",
    "portraits",
    "midjourney",
    "craiyon",
)


def _has_whole_word(haystack_lower: str, word: str) -> bool:
    start = 0
    n = len(word)
    while True:
        idx = haystack_lower.find(word, start)
        if idx < 0:
            return False
        before = haystack_lower[idx - 1] if idx > 0 else " "
        after = haystack_lower[idx + n] if idx + n < len(haystack_lower) else " "
        if not before.isalnum() and not after.isalnum():
            return True
        start = idx + n


def is_image_generation_mention(text: str) -> bool:
    """True when the user turn is about a picture / generator (linear scan)."""
    lower = text.lower()
    if not lower:
        return False
    if "dall-e" in lower or "dalle" in lower or "stable diffusion" in lower:
        return True
    for word in _IMAGE_GEN_MENTION_WORDS:
        if _has_whole_word(lower, word):
            return True
    return False
