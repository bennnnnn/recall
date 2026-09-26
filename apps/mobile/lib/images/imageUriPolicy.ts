/**
 * Guard for markdown `![alt](url)` image sources rendered in chat.
 *
 * React Native `<Image>` will fetch any URI it's given, including `http:` and
 * scheme-prefixed vectors. Model-emitted markdown can include arbitrary image
 * URLs, so without a scheme check a tracking pixel (or a large asset) loads
 * automatically when the message renders. We allow only schemes that can't be
 * used for insecure-protocol egress or local-file access:
 *  - `https:` — legitimate external images (Wikipedia, diagrams, the API/R2
 *    origin for attachments).
 *  - `data:` / `blob:` — inline images the renderer itself produces.
 *
 * `http:`, `file:`, `content:`, `ws:`, etc. are blocked. This intentionally
 * does NOT restrict by domain: the model legitimately references images on
 * many hosts, and an allowlist would regress that. No auth token is attached
 * to the image fetch, so the residual risk is limited to IP/UA exposure over
 * https — acceptable for a chat renderer.
 */
const ALLOWED_IMAGE_SCHEMES = new Set(["https:", "data:", "blob:"]);

export function isAllowedImageUri(src: string | undefined | null): src is string {
  if (!src || typeof src !== "string") return false;
  const trimmed = src.trim();
  if (!trimmed) return false;
  try {
    const { protocol } = new URL(trimmed);
    return ALLOWED_IMAGE_SCHEMES.has(protocol);
  } catch {
    // Bare relative paths (no scheme) aren't valid remote image sources here;
    // require an absolute URL with an allowed scheme.
    return false;
  }
}
