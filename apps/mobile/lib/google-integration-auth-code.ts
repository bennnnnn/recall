type SignInLike = {
  type?: string;
  data?: { serverAuthCode?: string | null } | null;
};

/** Pull serverAuthCode from this consent attempt (signIn / addScopes). */
export function readServerAuthCode(response: SignInLike | null | undefined): string | null {
  const code = response?.data?.serverAuthCode;
  return code?.trim() ? code : null;
}

/** True when the native SDK returned a cancelled consent response. */
export function isConsentCancelled(
  response: { type?: string } | null | undefined,
): boolean {
  return response?.type === "cancelled";
}
