type SignInLike = {
  data?: { serverAuthCode?: string | null } | null;
};

/** Pull serverAuthCode from sign-in / addScopes responses. */
export function readServerAuthCode(response: SignInLike | null | undefined): string | null {
  const code = response?.data?.serverAuthCode;
  return code?.trim() ? code : null;
}
