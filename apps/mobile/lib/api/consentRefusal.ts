/**
 * The server refuses a chat turn, voice and a photo read until the account agrees
 * to what goes to outside AI services: an error frame with `code: "consent_required"`,
 * or HTTP 403 `{"detail": {"code": "consent_required", …}}`. The auth context
 * registers the handler, and the root layout's gate shows the consent screen.
 */

export const CONSENT_REQUIRED_CODE = "consent_required";

let onConsentRequired: (() => void) | null = null;

export function setConsentRequiredHandler(fn: (() => void) | null): void {
  onConsentRequired = fn;
}

export function notifyConsentRequired(): void {
  onConsentRequired?.();
}

/** True for the 403 body `{"detail": {"code": "consent_required", …}}`. */
export function isConsentRequiredBody(body: string): boolean {
  try {
    const parsed: unknown = JSON.parse(body);
    const detail = (parsed as { detail?: unknown } | null)?.detail;
    return (detail as { code?: unknown } | null)?.code === CONSENT_REQUIRED_CODE;
  } catch {
    return false;
  }
}
