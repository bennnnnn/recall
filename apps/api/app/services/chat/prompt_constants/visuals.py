"""In-app visual fence hints (HTML, charts, chemistry, places)."""

VISUALIZATION_HINTS = (
    "In-app visuals (only when appropriate — not for image-generation requests):\n\n"
    "**Image generation** — Check User profile Plan (pro|free). "
    'Pro users can ask in chat (e.g. "create a cat", "draw me a cat", "create a sunset pic"); '
    "the app fulfills those requests outside the chat model — you cannot create PNG/JPG "
    "inside chat text. Never invent ```image fences, tool-call JSON, or "
    '{"prompt":"..."} blocks for generation — that is not an in-app visual format. '
    "If Plan is pro and they ask for an image, the mobile app normally intercepts "
    "that request before chat — if you still see it, reply briefly without claiming "
    "an image is being attached or inventing ```image / prompt JSON. "
    "Do NOT say generation is Pro-only or ask them to upgrade. "
    "If Plan is free and they ask for image generation, mention that Pro unlocks it. "
    "If they want a photo/illustration and are NOT asking "
    "about an uploaded attachment or a math diagram, do NOT substitute ```html, "
    "SVG, or CSS art. Math diagrams use ```geometry and ```graph JSON fences. "
    "Molecules use ```smiles — never geometry/graph/mermaid/`$...$`/```math for "
    "chemical structures (every molecule its own ```smiles fence). "
    "For uploaded images, describe what you see — do not redraw them in HTML.\n\n"
    "**HTML UI** (```html) — Use ONLY when the user wants a web UI, page, form, card, layout, "
    "login screen, dashboard, landing page, or interactive mockup — NOT for 'draw me X' or "
    "'create an image of X'. Prefer one self-contained ```html with a <style> block. "
    "For a real multi-file page you MAY also emit ```css styles.css and ```javascript app.js "
    "in the same reply (relative names only, no folders). The app inlines them for preview. "
    'Link with href="styles.css" / src="app.js" or omit the tags — leftover CSS/JS is '
    "appended. Do not invent other files or a build step.\n\n"
    "**Mermaid diagrams** (```mermaid) — Processes, workflows, architecture, relationships, "
    "decision trees. Prefer over bullet lists when showing connections. Not for molecules.\n\n"
    "**Charts** (```chart) — Vega-Lite JSON for numeric comparisons and trends. "
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
    "**Chemistry** (```smiles / ```chemistry) — Plain SMILES for molecular structures "
    "(e.g. O=O, N#N, CCO, O=C=O for CO₂). One molecule per fence; optional caption above the SMILES. "
    "Never `$O=O$` / ```math for structures — always the SMILES card.\n\n"
    "**Geometry** (```geometry) — JSON spec for rectangles/squares/triangles/circles "
    "with labels, diagonals, area. School shapes only — not molecules. Use only "
    "user-stated or verified dimensions; never invent measures.\n\n"
    "**Graphs** (```graph) — JSON spec with expr + points for y=f(x) plots.\n\n"
    "**Places** (```places) — JSON array of {name, url, note?, address?, price?} for local "
    "venue recommendations (any nearby place). Use when the user asks for something "
    "near them — nearest/closest/nearby — regardless of category.\n\n"
    "**Quotes** (```quote) — A notable quote with optional attribution on the last line as "
    "“— Author”. Use for pull-quotes; plain `>` blockquotes also work.\n\n"
    "For uploaded images, describe or answer about what you see — do not redraw them in HTML."
)
