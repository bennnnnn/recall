export type SignInProvider = "google" | "apple";

/**
 * The email already has an account this sign-in may not join (the provider is
 * not the address's authority, or the account holds another id of it): sign in
 * the earlier way. The server answers 409 `account_exists`.
 */
export class AccountExistsError extends Error {
  constructor(readonly signInWith: SignInProvider) {
    super(`account_exists:${signInWith}`);
    this.name = "AccountExistsError";
  }
}

/** The provider named by a 409 `{"detail": {"code": "account_exists", "sign_in_with": …}}`. */
export function accountExistsProvider(status: number, body: string): SignInProvider | null {
  if (status !== 409) return null;
  try {
    const detail = (JSON.parse(body) as { detail?: unknown }).detail;
    if (!detail || typeof detail !== "object") return null;
    const { code, sign_in_with: provider } = detail as Record<string, unknown>;
    if (code !== "account_exists") return null;
    return provider === "apple" || provider === "google" ? provider : null;
  } catch {
    return null;
  }
}
