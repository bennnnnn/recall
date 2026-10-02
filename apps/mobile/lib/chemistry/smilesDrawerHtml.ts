/**
 * Self-contained SmilesDrawer page for the 2D structure WebView (same offline/CSP pattern as
 * Mermaid). Extracted so the escaping and the message contract are testable without the card.
 */
import { escapeForInlineJsTemplate, injectPreviewCsp, inlineScript } from "@/lib/previewSandbox";
import type { Theme } from "@/lib/theme";
import { SMILES_DRAWER_MIN_JS } from "@/lib/vendor/smilesDrawerMinJs";

export type SmilesDrawerTheme = Pick<Theme, "bg" | "isDark">;

/** Why the page could not draw. The native side owns the wording (i18n), not the page. */
export type SmilesDrawerError = "unavailable" | "render";

export const SMILES_DRAWER_ERROR_KIND = "chemistry-error";

export const DRAW_WIDTH = 240;
export const DRAW_HEIGHT = 140;

/**
 * A SMILES is a JS template literal in the page. On top of the shared escape, `<!--` is broken
 * up: followed by `<script`, it would put the HTML parser in a state where the real closing
 * tag no longer ends the script.
 */
function escapeSmiles(smiles: string): string {
  return escapeForInlineJsTemplate(smiles.trim()).replace(/<!--/g, "<\\!--");
}

export function buildSmilesDrawerHtml(smiles: string, theme: SmilesDrawerTheme): string {
  const themeName = theme.isDark ? "dark" : "light";
  // Concat (not template interpolate) so `${` inside the browserify bundle
  // cannot break this file. Bundle returns require(); entry id is 1.
  const loader = "var __sdReq = " + SMILES_DRAWER_MIN_JS + "\nvar SmilesDrawer = __sdReq(1);\n";
  // SmilesDrawer.Drawer.draw(..., infoOnly) incorrectly forwards infoOnly as
  // SvgDrawer weights (weights.every throws). Use SvgDrawer on an <svg> target
  // and omit weights/infoOnly so defaults apply.
  const run =
    "(function() {\n" +
    "  var smiles = `" +
    escapeSmiles(smiles) +
    "`;\n" +
    "  function reportError(code) {\n" +
    "    try { window.ReactNativeWebView && window.ReactNativeWebView.postMessage(JSON.stringify({ kind: '" +
    SMILES_DRAWER_ERROR_KIND +
    "', code: code })); } catch (e) {}\n" +
    "  }\n" +
    "  var root = document.getElementById('molecule');\n" +
    "  if (!SmilesDrawer || typeof SmilesDrawer.SvgDrawer !== 'function' || typeof SmilesDrawer.parse !== 'function') {\n" +
    "    reportError('unavailable');\n" +
    "    return;\n" +
    "  }\n" +
    "  try {\n" +
    "  var drawer = new SmilesDrawer.SvgDrawer({ width: " +
    DRAW_WIDTH +
    ", height: " +
    DRAW_HEIGHT +
    ", explicitHydrogens: true });\n" +
    // Skeletal mode hides hydrogens (H2 is blank) and chain carbons (CO2
    // looks like O=O). Mark every atom explicit so O2 and H2 both show.
    "  var _processGraph = drawer.preprocessor.processGraph.bind(drawer.preprocessor);\n" +
    "  drawer.preprocessor.processGraph = function() {\n" +
    "    _processGraph();\n" +
    "    var verts = drawer.preprocessor.graph.vertices;\n" +
    "    for (var i = 0; i < verts.length; i++) {\n" +
    "      if (verts[i].value) verts[i].value.drawExplicit = true;\n" +
    "    }\n" +
    "  };\n" +
    "  SmilesDrawer.parse(smiles, function(tree) {\n" +
    "    try { drawer.draw(tree, root, '" +
    themeName +
    "'); }\n" +
    "    catch (e) { reportError('render'); }\n" +
    "  }, function() { reportError('render'); });\n" +
    "  } catch (e) { reportError('render'); }\n" +
    "})();\n";
  return injectPreviewCsp(
    '<!DOCTYPE html>\n<html lang="en"><head><meta charset="UTF-8">' +
      '<meta name="viewport" content="width=device-width, initial-scale=1.0">' +
      "<style>body{margin:0;padding:4px;background:" +
      theme.bg +
      ";display:flex;flex-direction:column;align-items:center;justify-content:center;min-height:" +
      DRAW_HEIGHT +
      "px}svg{max-width:100%;height:auto;display:block}</style>" +
      "</head><body>" +
      '<svg id="molecule" xmlns="http://www.w3.org/2000/svg" width="' +
      DRAW_WIDTH +
      '" height="' +
      DRAW_HEIGHT +
      '"></svg>' +
      "<script>" +
      inlineScript(loader + run) +
      "</script></body></html>",
  );
}

/** What a WebView message means for the card: the page's error code, or null for anything else. */
export function readSmilesDrawerError(data: string | undefined): SmilesDrawerError | null {
  if (!data) return null;
  try {
    const message: unknown = JSON.parse(data);
    if (typeof message !== "object" || message === null) return null;
    const { kind, code } = message as { kind?: unknown; code?: unknown };
    if (kind !== SMILES_DRAWER_ERROR_KIND) return null;
    return code === "unavailable" ? "unavailable" : "render";
  } catch {
    return null;
  }
}
