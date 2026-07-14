# Recall maths pipeline

Server-side SymPy verifies and samples; the mobile app only renders. Do not add on-device solving.

## Default product path (`MCP_TOOL_LOOP_ENABLED=false`)

1. **Heuristic pre-stream** ([`math_tools.py`](../apps/api/app/services/math_tools.py)) — if `needs_symbolic_math`, SymPy runs off the event loop and a verified system block is injected (numbers + optional `canonical_fence` for ` ```geometry` / ` ```graph`).
2. **LLM stream** — model explains using those values and emits fences.
3. **Post-stream** ([`math_fence.py`](../apps/api/app/services/math_fence.py)) — replace matching geometry/graph JSON with the canonical fence when present; schema-validate otherwise; densify sparse continuous graphs.
4. **Mobile** — preprocess delimiters, then render: inline `$...$` → native `MathText`; display ` ```math` → KaTeX/MathJax WebView (dev build); diagrams → SVG.

Camera math is a specialization of step 1: fixed prompt → vision extract → same SymPy equation path.

## Tool-loop path (`MCP_TOOL_LOOP_ENABLED=true`)

Heuristic pre-solve and web-search injection are skipped. The model may call the `sympy` MCP tool. Tool results that include a `canonical_fence` in `ToolResult.data` are collected into `VerifiedMathBlock` so step 3 still rewrites fences. Treat this path as optional until you intentionally turn the loop on in production.

## Formula emit rule (prompts must agree)

- **Steps / intermediates:** inline `$...$` only (no backticks around `$`, no ` ```math` inside numbered steps).
- **Standalone display:** ` ```math` OK for a final equation on its own lines.
- **Diagrams:** ` ```geometry` / ` ```graph` JSON only — never freehand HTML/SVG/```json for math diagrams.

## Key files

| Layer | Path |
|-------|------|
| SymPy core | `apps/api/app/services/math_service.py` |
| Pre-stream inject | `apps/api/app/services/math_tools.py` |
| Post-stream fences | `apps/api/app/services/math_fence.py` |
| Camera OCR | `apps/api/app/services/math_image_extract.py` |
| MCP sympy | `apps/api/app/gateways/mcp/sympy_adapter.py` |
| Prompt hints | `apps/api/app/services/chat/prompt_constants.py` |
| Mobile preprocess | `apps/mobile/lib/markdownPreprocess.ts`, `normalizeImplicitMath.ts` |
| Render | `MathText`, `MathView` / `MathFormulaWebView`, `GeometryBlock`, `FunctionGraphBlock` |
