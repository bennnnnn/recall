/**
 * Content-Security-Policy for the sandboxed HTML/JS preview.
 *
 * The preview runs model/user-generated HTML+JS in an in-app WebView. It has no
 * app tokens (baseUrl https://localhost/, no cookies), but without a CSP the JS
 * could still make arbitrary network egress. This policy makes it a true sandbox:
 *  - default-src 'none': deny everything by default
 *  - script-src 'unsafe-inline' https: / style-src 'unsafe-inline' https: inline
 *    code runs (the preview's purpose); https external scripts/styles load
 *  - img/font/media: data/blob/https only (passive rendering)
 *  - connect-src 'none': JS cannot fetch/XHR/WebSocket anywhere (no exfiltration)
 *  - base-uri 'none' / form-action 'none': no <base> hijack, no form submits
 *  - sandbox allow-scripts: iframe-style sandbox — opaque origin (no same-origin
 *    storage access), no top navigation, no popups, no plugins; scripts allowed
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

/** Inject the sandbox CSP meta into an HTML document (bare or full). */
export function injectPreviewCsp(html: string): string {
  const meta = `<meta http-equiv="Content-Security-Policy" content="${PREVIEW_CSP}">`;
  const headMatch = /<head(\s[^>]*)?>/i.exec(html);
  if (headMatch && headMatch.index != null) {
    const at = headMatch.index + headMatch[0].length;
    return html.slice(0, at) + meta + html.slice(at);
  }
  const htmlMatch = /<html(\s[^>]*)?>/i.exec(html);
  if (htmlMatch && htmlMatch.index != null) {
    const at = htmlMatch.index + htmlMatch[0].length;
    return html.slice(0, at) + `<head>${meta}</head>` + html.slice(at);
  }
  return `<!DOCTYPE html><html><head>${meta}</head><body>${html}</body></html>`;
}
