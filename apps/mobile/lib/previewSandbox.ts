/**
 * Content-Security-Policy for the sandboxed HTML/JS preview.
 *
 * The preview runs model/user-generated HTML+JS in an in-app WebView. It has no
 * app tokens (baseUrl about:blank, no cookies), but without a CSP the JS
 * could still make arbitrary network egress. This policy locks down the document:
 *  - default-src 'none': deny everything by default
 *  - script-src / style-src 'unsafe-inline' only — inline code runs (the
 *    preview's purpose). NO https:: a <script src="https://evil/?…"> is a
 *    working GET exfil channel that bypasses connect-src 'none'.
 *  - img/font/media: data/blob only — NO https:. An <img src="https://…"> (or
 *    font/media URL) is the same passive GET exfil class.
 *  - connect-src 'none': JS cannot fetch/XHR/WebSocket anywhere (no exfiltration)
 *  - base-uri 'none' / form-action 'none': no <base> hijack, no form submits
 *
 * Note: a meta CSP `sandbox` directive is NOT equivalent to an iframe `sandbox`
 * attribute (browsers ignore sandbox in meta CSP per the HTML spec). Opaque
 * origin / storage isolation come from the WebView config (`domStorageEnabled`
 * off, no shared cookies) — not from this meta tag. We still list
 * `sandbox allow-scripts` for environments that honor it; do not treat it as
 * a guarantee of iframe-style isolation.
 */
/** Egress-locked CSP without the meta `sandbox` token (charts/math/PDF). */
export const PREVIEW_CSP_INLINE = [
  "default-src 'none'",
  "style-src 'unsafe-inline'",
  "script-src 'unsafe-inline'",
  "img-src data: blob:",
  "font-src data:",
  "media-src data: blob:",
  "connect-src 'none'",
  "base-uri 'none'",
  "form-action 'none'",
].join("; ");

/**
 * Default preview CSP for trusted inlined bundles (charts/math/PDF).
 * Includes a meta `sandbox` token for environments that honor it.
 */
export const PREVIEW_CSP = `${PREVIEW_CSP_INLINE}; sandbox allow-scripts`;

/**
 * HTML Run tab — still isolated from the app (no shared cookies / tokens),
 * but allows http(s) subresources so CDN CSS/JS demos actually paint.
 * Top-level navigations away from the document are blocked in the WebView
 * nav guard, not here.
 */
export const PREVIEW_CSP_LIVE = [
  "default-src 'none'",
  "style-src 'unsafe-inline' https: http:",
  "script-src 'unsafe-inline' https: http:",
  "img-src data: blob: https: http:",
  "font-src data: https: http:",
  "media-src data: blob: https: http:",
  "connect-src https: http:",
  "frame-src https: http:",
  "worker-src blob: https: http:",
  "base-uri 'none'",
  "form-action https: http:",
].join("; ");

/** True if the markup references http(s) assets. */
export function htmlDependsOnNetwork(html: string): boolean {
  return (
    /(?:src|href)\s*=\s*["']https?:\/\//i.test(html) ||
    /@import\s+["']https?:\/\//i.test(html) ||
    /url\(\s*["']?https?:\/\//i.test(html)
  );
}

/**
 * CSP for the math WebView (MathJax path).
 *
 * The math WebView renders a *trusted* template (our own LaTeX + a vendored,
 * inlined MathJax tex-svg bundle) — not model-generated HTML/JS. MathJax's
 * tex-svg output renders as inline SVG paths with no runtime font fetches,
 * and the ams/noerrors/noundefined tex extensions are pre-bundled, so the
 * loader never needs to reach the network. That lets us keep `connect-src
 * 'none'` — the same hard egress block as the user-HTML preview CSP. (The
 * bundle does contain dormant speech-rule-engine CDN URLs, but those only
 * execute under an a11y config we don't load, and `connect-src 'none'`
 * blocks them regardless.)
 */
export const MATH_PREVIEW_CSP = [
  "default-src 'none'",
  "style-src 'unsafe-inline'",
  "script-src 'unsafe-inline'",
  "img-src data: blob: https:",
  "font-src data: https:",
  "media-src data: blob: https:",
  "connect-src 'none'",
  "base-uri 'none'",
  "form-action 'none'",
  "sandbox allow-scripts",
].join("; ");

/**
 * CSP for the PDF preview WebView (pdf.js).
 *
 * pdf.js + its worker are vendored and inlined (the worker is built from a
 * Blob URL at runtime, hence `worker-src blob:`). The PDF bytes are inlined
 * as base64 — no fetch. With the worker no longer pulled from cdnjs, the PDF
 * preview needs zero network egress, so `connect-src 'none'` holds just like
 * the other sandbox CSPs. (CMap/standard-font fetches are not configured, so
 * pdf.js never reaches the network for the previews we render.)
 */
export const PDF_PREVIEW_CSP = [
  "default-src 'none'",
  "style-src 'unsafe-inline'",
  "script-src 'unsafe-inline'",
  "worker-src blob:",
  "img-src data: blob: https:",
  "font-src data: https:",
  "media-src data: blob: https:",
  "connect-src 'none'",
  "base-uri 'none'",
  "form-action 'none'",
  "sandbox allow-scripts",
].join("; ");

/**
 * End-tag pattern that accepts HTML5 junk before `>` (e.g. `</script\t\n bar>`).
 * CodeQL js/bad-tag-filter rejects `</script\s*>` which misses those shapes.
 */
const SCRIPT_END = String.raw`<\/script[^>]*>`;
const STYLE_END = String.raw`<\/style[^>]*>`;
const TEXTAREA_END = String.raw`<\/textarea[^>]*>`;
const TITLE_END = String.raw`<\/title[^>]*>`;

const RAW_TEXT_REGION_RE = new RegExp(
  [
    String.raw`<!--[\s\S]*?-->`,
    String.raw`<script\b[^>]*>[\s\S]*?${SCRIPT_END}`,
    String.raw`<style\b[^>]*>[\s\S]*?${STYLE_END}`,
    String.raw`<textarea\b[^>]*>[\s\S]*?${TEXTAREA_END}`,
    String.raw`<title\b[^>]*>[\s\S]*?${TITLE_END}`,
  ].join("|"),
  "gi",
);

const SCRIPT_BLOCK_RE = new RegExp(
  String.raw`<\s*script\b[^>]*>[\s\S]*?<\s*\/\s*script[^>]*>`,
  "gi",
);
const SCRIPT_SELF_CLOSE_RE = /<\s*script\b[^>]*\/>/gi;

/** Apply `replace` until the string stops changing (CodeQL multi-char sanitization). */
function replaceUntilStable(input: string, pattern: RegExp, replacement: string): string {
  let out = input;
  let prev = "";
  // Cap iterations — adversarial input should not hang the UI.
  for (let i = 0; i < 32 && out !== prev; i++) {
    prev = out;
    out = out.replace(pattern, replacement);
  }
  return out;
}

/**
 * Replace raw-text/CDATA-like regions (script, style, comments, textarea,
 * title) with equal-length whitespace, preserving the string's length so
 * indices found in the result stay valid against the original string.
 *
 * BUG FIX (was a confirmed sandbox escape): injectPreviewCsp() used to find
 * "the <head>" with a plain textual `.search()` — no HTML/JS-context
 * awareness. A document that puts a decoy `<head` inside a <script> comment
 * (or <style>/HTML comment/<textarea>/<title>) BEFORE the real <head> tag
 * got its CSP <meta> spliced into that inert block instead of the real
 * document — where it's never parsed as a tag — leaving the actual <head>
 * with no CSP at all.
 */
function maskRawTextRegions(html: string): string {
  return html.replace(RAW_TEXT_REGION_RE, (match) => " ".repeat(match.length));
}

function stripScriptBlocks(html: string): string {
  let out = replaceUntilStable(html, SCRIPT_BLOCK_RE, "");
  out = replaceUntilStable(out, SCRIPT_SELF_CLOSE_RE, "");
  return out;
}

/** Inject the sandbox CSP meta into an HTML document (bare or full). */
export function injectPreviewCsp(html: string, csp: string = PREVIEW_CSP): string {
  const meta = `<meta http-equiv="Content-Security-Policy" content="${csp}">`;
  const masked = maskRawTextRegions(html);

  const headMatch = /<head(\s[^>]*)?>/i.exec(masked);
  if (headMatch && headMatch.index != null) {
    const headIdx = headMatch.index;
    const headTag = html.slice(headIdx, headIdx + headMatch[0].length);
    // Meta CSP only constrains resources after it is parsed. Drop real
    // <script> blocks that appear before the (now decoy-proof) real <head>
    // so they cannot run unconstrained.
    const before = stripScriptBlocks(html.slice(0, headIdx));
    return before + headTag + meta + html.slice(headIdx + headMatch[0].length);
  }

  const htmlMatch = /<html(\s[^>]*)?>/i.exec(masked);
  if (htmlMatch && htmlMatch.index != null) {
    const at = htmlMatch.index + htmlMatch[0].length;
    return html.slice(0, at) + `<head>${meta}</head>` + html.slice(at);
  }
  return `<!DOCTYPE html><html><head>${meta}</head><body>${html}</body></html>`;
}

/** Escape a string embedded in a JS template literal inside a <script> block. */
export function escapeForInlineJsTemplate(value: string): string {
  return value
    .replace(/\\/g, "\\\\")
    .replace(/`/g, "\\`")
    .replace(/\${/g, "\\${")
    .replace(new RegExp(SCRIPT_END, "gi"), "<\\/script>");
}

/**
 * Make a raw JS source safe to inline inside a <script>...</script> block.
 */
export function inlineScript(source: string): string {
  return source.replace(new RegExp(SCRIPT_END, "gi"), "<\\/script>");
}

// Matches whitespace and C0 control characters, built via String.fromCharCode
// (not a literal char class) so no raw control bytes live in this source file.
const CONTROL_OR_WHITESPACE = new RegExp(
  "[\\s" + Array.from({ length: 0x20 }, (_, i) => String.fromCharCode(i)).join("") + "]",
  "g",
);

const ON_ATTR_DQ = /[\s/]on\w+\s*=\s*"[^"]*"/gi;
const ON_ATTR_SQ = /[\s/]on\w+\s*=\s*'[^']*'/gi;
const ON_ATTR_UQ = /[\s/]on\w+\s*=\s*[^\s>]+/gi;
const SRCDOC_DQ = /\ssrcdoc\s*=\s*"[^"]*"/gi;
const SRCDOC_SQ = /\ssrcdoc\s*=\s*'[^']*'/gi;
const META_REFRESH = /<\s*meta\b[^>]*\shttp-equiv\s*=\s*["']?refresh["']?[^>]*>/gi;

function isDangerousUrlScheme(cleaned: string): boolean {
  if (cleaned.startsWith("javascript:") || cleaned.startsWith("vbscript:")) {
    return true;
  }
  // Block data: except image payloads used by static <img src="data:image/...">.
  if (cleaned.startsWith("data:") && !cleaned.startsWith("data:image/")) {
    return true;
  }
  return false;
}

/**
 * Remove `<script>...</script>` blocks and inline event handlers from HTML.
 *
 * Used for the "Open in browser" / share paths, which hand model-generated HTML
 * to the system browser. The system browser runs `<script>` unsandboxed (no CSP,
 * same origin as the browser), so untrusted model JS must never reach it.
 */
export function stripScripts(html: string): string {
  let out = stripScriptBlocks(html);
  out = replaceUntilStable(out, ON_ATTR_DQ, "");
  out = replaceUntilStable(out, ON_ATTR_SQ, "");
  out = replaceUntilStable(out, ON_ATTR_UQ, "");
  out = replaceUntilStable(out, SRCDOC_DQ, "");
  out = replaceUntilStable(out, SRCDOC_SQ, "");
  out = replaceUntilStable(out, META_REFRESH, "");

  out = out.replace(
    /\s(href|src|action|formaction|data)\s*=\s*("[^"]*"|'[^']*'|[^\s>]+)/gi,
    (match, _attr: string, value: string) => {
      const unquoted = value.replace(/^["']|["']$/g, "");
      const cleaned = unquoted.replace(CONTROL_OR_WHITESPACE, "").toLowerCase();
      if (isDangerousUrlScheme(cleaned)) {
        return "";
      }
      return match;
    },
  );
  return out;
}
